/**
 * Browser-side audio capture helper for the Realtime voice call.
 *
 * The Realtime API streams 24 kHz 16-bit PCM mono on the model side.
 * We tap both the **local mic track** and the **remote agent track**
 * off the same `RTCPeerConnection`, mix them down to a single mono
 * stream via the Web Audio API, capture PCM samples through an
 * `AudioWorklet` (with a `ScriptProcessorNode` fallback for older
 * browsers), then encode the captured Int16 buffer to a real
 * RIFF/WAVE file at 24 kHz on stop.
 *
 * The resulting WAV bytes are uploaded base64-encoded to the existing
 * `POST /calls` route, which already labels the artifact `audio.wav`
 * with `Content-Type: audio/wav`. See docs/features/call-bundles.md.
 *
 * Kept in `lib/` (not `hooks/`) per the structural convention: the
 * realtime hook composes this helper, the helper holds no React state.
 */

// Canonical sample rate for the bundled WAV. The Realtime API delivers
// 24 kHz audio; the browser's default `AudioContext` may run at 44.1 kHz
// or 48 kHz, so we ask for 24 kHz explicitly. The worklet downsamples
// (very minimal — usually just resamples within a single octave) when
// the actual context rate differs from this target.
export const TARGET_SAMPLE_RATE = 24_000;

const WORKLET_PROCESSOR_NAME = "b2-pcm-capture";

// Inline worklet source so callers don't have to ship an extra asset.
// The worklet pulls float32 samples off port 0 (the only input), packs
// them into a transferable Float32Array, and posts them back to the
// main thread. Mixing happens upstream via a GainNode + AudioNode.connect()
// graph — by the time samples arrive here they're already mono and mixed.
const WORKLET_SOURCE = `
class B2PcmCapture extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input.length > 0 && input[0].length > 0) {
      // Copy: AudioWorklet reuses the underlying buffer between calls.
      const copy = new Float32Array(input[0].length);
      copy.set(input[0]);
      this.port.postMessage(copy, [copy.buffer]);
    }
    return true;
  }
}
registerProcessor('${WORKLET_PROCESSOR_NAME}', B2PcmCapture);
`;

interface RecorderHandle {
  stop: () => Promise<Uint8Array>;
}

/**
 * Start capturing both sides of a WebRTC call as a mixed mono PCM stream.
 *
 * Pass the local mic stream and the remote agent stream (as it lands on
 * `pc.ontrack`). Returns a handle whose `stop()` resolves with a WAV
 * file (`audio/wav`, 24 kHz, 16-bit, mono).
 *
 * The graph wired up here:
 *
 *   MediaStreamSource(localMic) ─┐
 *                                 ├─> GainNode(0.7 each) ─> AudioWorklet ─> port.message
 *   MediaStreamSource(remote)   ─┘
 *
 * Both inputs are summed and lightly attenuated (0.7 each) to avoid
 * clipping when both speakers are talking at peak volume. The worklet
 * captures Float32 samples; we convert + concatenate to Int16 on stop.
 */
export async function startMixedRecording(
  localStream: MediaStream,
  remoteStream: MediaStream,
): Promise<RecorderHandle> {
  // Some browsers (Safari) don't honor `sampleRate` exactly; we resample
  // ourselves on stop if the actual rate differs.
  const AudioCtor: typeof AudioContext =
    window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new AudioCtor({ sampleRate: TARGET_SAMPLE_RATE });

  const localSrc = ctx.createMediaStreamSource(localStream);
  const remoteSrc = ctx.createMediaStreamSource(remoteStream);
  const localGain = ctx.createGain();
  const remoteGain = ctx.createGain();
  localGain.gain.value = 0.7;
  remoteGain.gain.value = 0.7;
  localSrc.connect(localGain);
  remoteSrc.connect(remoteGain);

  // Force-mono sink: the worklet processor only inspects channel 0, but
  // a GainNode mixer downstream gives us a single-channel summed signal.
  const mixer = ctx.createGain();
  mixer.gain.value = 1.0;
  mixer.channelCount = 1;
  mixer.channelCountMode = "explicit";
  mixer.channelInterpretation = "speakers";
  localGain.connect(mixer);
  remoteGain.connect(mixer);

  const chunks: Float32Array[] = [];
  let cleanup: () => void = () => {};

  // Feature-detect on the global constructor rather than `"audioWorklet" in
  // ctx`: the latter is a type guard that narrows the `else` branch's `ctx`
  // to `never` (AudioContext.audioWorklet is always present in the DOM lib
  // types), which breaks the ScriptProcessorNode fallback below.
  const supportsAudioWorklet = typeof AudioWorkletNode !== "undefined";

  if (supportsAudioWorklet) {
    const blob = new Blob([WORKLET_SOURCE], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    try {
      await ctx.audioWorklet.addModule(url);
    } finally {
      URL.revokeObjectURL(url);
    }
    const worklet = new AudioWorkletNode(ctx, WORKLET_PROCESSOR_NAME, {
      numberOfInputs: 1,
      numberOfOutputs: 0,
      channelCount: 1,
    });
    worklet.port.onmessage = (e: MessageEvent<Float32Array>) => {
      if (e.data instanceof Float32Array) chunks.push(e.data);
    };
    mixer.connect(worklet);
    cleanup = () => {
      worklet.port.onmessage = null;
      try {
        worklet.disconnect();
      } catch {
        /* already disconnected */
      }
    };
  } else {
    // Fallback for browsers that haven't shipped AudioWorklet
    // (older Safari). ScriptProcessorNode is deprecated but still
    // functions; the buffer-size hint of 4096 is the historical default.
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (e: AudioProcessingEvent) => {
      const channel = e.inputBuffer.getChannelData(0);
      const copy = new Float32Array(channel.length);
      copy.set(channel);
      chunks.push(copy);
    };
    mixer.connect(processor);
    // ScriptProcessor requires a connection to the destination to run.
    // We route through a muted gain so the user never actually hears
    // duplicated playback through this graph.
    const silentSink = ctx.createGain();
    silentSink.gain.value = 0.0;
    processor.connect(silentSink);
    silentSink.connect(ctx.destination);
    cleanup = () => {
      processor.onaudioprocess = null;
      try {
        processor.disconnect();
        silentSink.disconnect();
      } catch {
        /* already disconnected */
      }
    };
  }

  const stop = async (): Promise<Uint8Array> => {
    cleanup();
    try {
      mixer.disconnect();
      localGain.disconnect();
      remoteGain.disconnect();
      localSrc.disconnect();
      remoteSrc.disconnect();
    } catch {
      /* ignore */
    }
    const actualRate = ctx.sampleRate;
    await ctx.close().catch(() => {});

    const float32 = concatFloat32(chunks);
    const resampled =
      actualRate === TARGET_SAMPLE_RATE
        ? float32
        : resampleLinear(float32, actualRate, TARGET_SAMPLE_RATE);
    const int16 = floatToInt16(resampled);
    return encodeWav(int16, TARGET_SAMPLE_RATE);
  };

  return { stop };
}

function concatFloat32(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Float32Array(total);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.length;
  }
  return out;
}

// Crude linear resampler. Quality is fine for speech-band content; if you
// ever pipe music through here, replace with a proper polyphase resampler.
function resampleLinear(
  input: Float32Array,
  fromRate: number,
  toRate: number,
): Float32Array {
  if (input.length === 0) return input;
  const ratio = fromRate / toRate;
  const outLen = Math.floor(input.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const srcIdx = i * ratio;
    const lo = Math.floor(srcIdx);
    const hi = Math.min(lo + 1, input.length - 1);
    const frac = srcIdx - lo;
    out[i] = input[lo] * (1 - frac) + input[hi] * frac;
  }
  return out;
}

function floatToInt16(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

/**
 * Write a minimal RIFF/WAVE header + PCM body. Mono, 16-bit, no list chunk.
 *
 * The header layout (44 bytes) is the canonical one — see
 * https://docs.fileformat.com/audio/wav/ for the field reference.
 */
function encodeWav(samples: Int16Array, sampleRate: number): Uint8Array {
  const numChannels = 1;
  const bytesPerSample = 2;
  const byteRate = sampleRate * numChannels * bytesPerSample;
  const blockAlign = numChannels * bytesPerSample;
  const dataSize = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  // "RIFF" chunk descriptor
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeAscii(view, 8, "WAVE");
  // "fmt " sub-chunk
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true); // PCM header size
  view.setUint16(20, 1, true); // AudioFormat = PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bytesPerSample * 8, true);
  // "data" sub-chunk
  writeAscii(view, 36, "data");
  view.setUint32(40, dataSize, true);
  // PCM samples
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    view.setInt16(offset, samples[i], true);
  }
  return new Uint8Array(buffer);
}

function writeAscii(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

/** Base64-encode a Uint8Array — used by the hook to push WAV bytes over JSON. */
export function uint8ToBase64(bytes: Uint8Array): string {
  // Chunked encoding to avoid the call-stack overflow you get with
  // `String.fromCharCode(...bytes)` on multi-megabyte buffers.
  const CHUNK = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += CHUNK) {
    const slice = bytes.subarray(i, i + CHUNK);
    binary += String.fromCharCode(...slice);
  }
  return btoa(binary);
}
