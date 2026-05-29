"use client";

import { useCallback, useRef, useState } from "react";
import { createRealtimeSession, finalizeCall } from "@/lib/api-client";
import { startMixedRecording, uint8ToBase64 } from "@/lib/audio-recorder";
import { handleRealtimeEvent } from "@/lib/realtime-events";
import type {
  Call,
  CallFinalizeRequest,
  RealtimeSessionToken,
  ToolEvent,
  TranscriptTurn,
} from "@gpt-realtime-2-customer-support-voice-agent/shared";

export type CallState =
  | "idle"
  | "connecting"
  | "connected"
  | "ending"
  | "ended"
  | "error";

interface UseRealtimeCallResult {
  state: CallState;
  callId: string | null;
  error: string | null;
  transcript: TranscriptTurn[];
  tools: ToolEvent[];
  muted: boolean;
  finalized: Call | null;
  start: () => Promise<void>;
  end: () => Promise<void>;
  toggleMute: () => void;
}

interface ActiveRecorder {
  stop: () => Promise<Uint8Array>;
}

// Crockford base32 alphabet — note it excludes I, L, O, U. The server
// validator in services/api/app/runtime/calls.py is `^[0-9A-HJKMNP-TV-Z]{26}$`,
// so the id MUST be drawn from exactly this alphabet. (A previous version
// used `toString(36)`, i.e. base36 `0-9a-z`, which emits i/l/o/u and was
// rejected with "Invalid call_id" on End Call.)
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

function newCallId(): string {
  // Crockford base32 ULID minted browser-side: 48-bit millisecond timestamp
  // (10 chars, time-sortable) + 80 bits of randomness (16 chars). 256 is an
  // exact multiple of 32, so `byte % 32` is an unbiased index. The fixed
  // 26-char length lets the server-side regex validator stay simple.
  let ts = Date.now();
  const time = new Array<string>(10);
  for (let i = 9; i >= 0; i--) {
    time[i] = CROCKFORD[ts % 32];
    ts = Math.floor(ts / 32);
  }
  const rnd = Array.from(crypto.getRandomValues(new Uint8Array(16)))
    .map((b) => CROCKFORD[b % 32])
    .join("");
  return time.join("") + rnd;
}

/**
 * Lifecycle of a single Realtime voice call.
 *
 * The peer connection is opened **directly** to OpenAI using the
 * ephemeral session token minted by our backend. We forward
 * model-issued tool calls to `POST /tools/invoke`, replay the result
 * back into the data channel, accumulate transcript turns and tool
 * events client-side, and on End Call POST the whole package to
 * `/calls` so the bundle is persisted to B2.
 *
 * Audio capture taps **both** sides of the conversation via the Web
 * Audio API — local mic track + remote agent track off the same
 * `RTCPeerConnection` — and encodes the mixed stream to a real 24 kHz
 * 16-bit mono WAV on End Call. See `lib/audio-recorder.ts`.
 *
 * Data-channel event interpretation lives in `lib/realtime-events.ts`
 * to keep this hook focused on lifecycle. Both helpers stay in `lib/`
 * per the structural convention.
 *
 * This hook is intentionally NOT a TanStack Query hook — WebRTC
 * lifecycle does not fit a Query model. It is the documented exception
 * to the "every API call is a Query hook" rule (see AGENTS.md §3).
 */
export function useRealtimeCall(): UseRealtimeCallResult {
  const [state, setState] = useState<CallState>("idle");
  const [callId, setCallId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [tools, setTools] = useState<ToolEvent[]>([]);
  const [muted, setMuted] = useState(false);
  const [finalized, setFinalized] = useState<Call | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<ActiveRecorder | null>(null);
  const startedAtRef = useRef<string | null>(null);
  const modelRef = useRef<string>("gpt-realtime-2");
  // The data-channel handler is wired to `dc.onmessage` exactly once in
  // `start()`, before React has re-rendered with the new `callId` state.
  // Reading `callId` from the closure there would capture the stale `null`,
  // so `handleToolCall` would early-return and NO tool calls would ever
  // dispatch. Mirror the id into a ref (like the other lifecycle refs) and
  // read that inside the handler so it always sees the live call id.
  const callIdRef = useRef<string | null>(null);

  const handleDataChannelEvent = useCallback(
    async (raw: MessageEvent) => {
      await handleRealtimeEvent(raw, callIdRef.current, {
        appendTool: (evt) => setTools((prev) => [...prev, evt]),
        appendTurn: (turn) => setTranscript((prev) => [...prev, turn]),
        setError,
        sendDataChannel: (payload) =>
          dcRef.current?.send(JSON.stringify(payload)),
      });
    },
    [],
  );

  const start = useCallback(async () => {
    setError(null);
    setState("connecting");
    setTranscript([]);
    setTools([]);
    setFinalized(null);

    const id = newCallId();
    setCallId(id);
    callIdRef.current = id;
    startedAtRef.current = new Date().toISOString();

    try {
      const token: RealtimeSessionToken = await createRealtimeSession();
      modelRef.current = token.model;
      const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = mic;

      const pc = new RTCPeerConnection({
        iceServers: token.ice_servers.length > 0 ? token.ice_servers : undefined,
      });
      pcRef.current = pc;
      mic.getTracks().forEach((track) => pc.addTrack(track, mic));

      // Set up playback + tap the remote stream for the mixed recorder.
      // We wait for `ontrack` before starting the recorder because we
      // need both the local and remote MediaStreams in hand to wire the
      // mix graph in `audio-recorder.ts`.
      const audioEl = new Audio();
      audioEl.autoplay = true;
      pc.ontrack = (e) => {
        audioEl.srcObject = e.streams[0];
        if (!recorderRef.current) {
          startMixedRecording(mic, e.streams[0])
            .then((handle) => {
              recorderRef.current = handle;
            })
            .catch((err) => {
              // Recording failure is non-fatal — the call still proceeds,
              // we just won't have audio in the bundle. Surface via setError
              // so the UI can warn the operator.
              setError(
                err instanceof Error
                  ? `Audio capture failed: ${err.message}`
                  : "Audio capture failed",
              );
            });
        }
      };

      const dc = pc.createDataChannel("oai-events");
      dcRef.current = dc;
      dc.onmessage = handleDataChannelEvent;
      dc.onopen = () => setState("connected");

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      // GA Realtime WebRTC: POST the SDP offer to /v1/realtime/calls. The
      // model is fixed by the ephemeral client secret (minted server-side),
      // so it's no longer passed as a query param. This replaced the beta
      // `/v1/realtime?model=...` endpoint, which now 404s.
      const sdpResponse = await fetch(
        "https://api.openai.com/v1/realtime/calls",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token.client_secret}`,
            "Content-Type": "application/sdp",
          },
          body: offer.sdp,
        },
      );
      if (!sdpResponse.ok) {
        throw new Error(`Realtime negotiation failed: ${sdpResponse.status}`);
      }
      const answer = { type: "answer" as const, sdp: await sdpResponse.text() };
      await pc.setRemoteDescription(answer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start call");
      setState("error");
    }
  }, [handleDataChannelEvent]);

  const end = useCallback(async () => {
    if (!callId || !startedAtRef.current) return;
    setState("ending");
    try {
      // Stop recorder first so we capture the trailing tail of audio
      // before the peer connection tears down.
      let wavBytes: Uint8Array = new Uint8Array(0);
      if (recorderRef.current) {
        try {
          wavBytes = await recorderRef.current.stop();
        } catch (err) {
          // Recorder stop failure is non-fatal — log via setError but
          // still finalize the call so the transcript/tool trace land
          // in the bundle.
          setError(
            err instanceof Error
              ? `Failed to encode audio: ${err.message}`
              : "Failed to encode audio",
          );
        }
      }
      const audio_base64 = wavBytes.length > 0 ? uint8ToBase64(wavBytes) : "";

      const request: CallFinalizeRequest = {
        call_id: callId,
        started_at: startedAtRef.current,
        ended_at: new Date().toISOString(),
        transcript,
        tools,
        audio_base64,
        model: modelRef.current,
      };
      const call = await finalizeCall(request);
      setFinalized(call);
      setState("ended");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finalize call");
      setState("error");
    } finally {
      pcRef.current?.close();
      pcRef.current = null;
      dcRef.current = null;
      recorderRef.current = null;
      micStreamRef.current?.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
  }, [callId, transcript, tools]);

  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      micStreamRef.current?.getAudioTracks().forEach((t) => {
        t.enabled = !next;
      });
      return next;
    });
  }, []);

  return { state, callId, error, transcript, tools, muted, finalized, start, end, toggleMute };
}
