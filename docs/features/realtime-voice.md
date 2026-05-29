<!-- last_verified: 2026-05-29 -->
# Feature: Realtime Voice

## Purpose
Open a full-duplex audio connection between the caller's browser and the OpenAI Realtime API so the agent can hear and respond in natural speech, interrupting and being interrupted freely.

## Used By
- UI: `/call` page (CallConsole)
- API: `POST /realtime/session`

## Core Functions
- `apps/web/src/hooks/use-realtime-call.ts` — opens the WebRTC peer connection, manages mic capture, audio playback, data-channel events, and lifecycle (idle / connecting / connected / interrupted / ended)
- `apps/web/src/lib/audio-recorder.ts` — captures **both sides** of the conversation (local mic track + remote agent track from the `RTCPeerConnection`), mixes them down to mono via the Web Audio API + an `AudioWorklet` (`ScriptProcessorNode` fallback), and encodes the result as a 24 kHz 16-bit WAV on End Call
- `apps/web/src/lib/realtime-events.ts` — pure helpers that interpret OpenAI Realtime data-channel events (tool calls, transcript turns) so the hook stays focused on lifecycle
- `apps/web/src/components/call/CallConsole.tsx` — Start/End/Mute controls, mic-level indicator
- `apps/web/src/components/call/LiveTranscript.tsx` — streams transcript turns from the data channel
- `apps/web/src/components/call/MicLevelIndicator.tsx` — visualizes mic input RMS
- `services/api/app/runtime/realtime.py` — `POST /realtime/session` route
- `services/api/app/repo/openai_client.py::mint_realtime_session()` — calls OpenAI to create an ephemeral session and returns a `RealtimeSessionToken`

## Canonical Files
- Browser-side Realtime lifecycle: `apps/web/src/hooks/use-realtime-call.ts`
- Server-side token mint: `services/api/app/repo/openai_client.py`

## Inputs
- `POST /realtime/session` body — none in v1. The server fixes the session config: model, tool specs, a customer-support **system prompt** (`_SUPPORT_AGENT_INSTRUCTIONS`), `output_modalities: ["audio"]`, and the agent **voice** (`_AGENT_VOICE`, default `marin`). All live in `openai_client.py` alongside `_tool_specs()`. Future: accept `{ language, voice }` overrides in the body.
- Browser: microphone stream via `getUserMedia({ audio: true })`

## Outputs
- `POST /realtime/session` → `RealtimeSessionToken` (`{ session_id, client_secret, model, expires_at, ice_servers }`)
- WebRTC peer connection: outbound audio frames + inbound audio frames + bidirectional data channel for events (transcript deltas, tool calls, model state)
- Locally captured WAV: a 24 kHz 16-bit mono RIFF/WAVE that mixes both the caller mic and the agent's incoming audio track. Persisted to B2 as `audio.wav` when the call ends (see [Call Bundles](call-bundles.md)).
- Side effects: none on the server beyond minting the token; OpenAI bills the API key

## Flow
1. User clicks **Start Call** in `/call`.
2. Browser requests mic permission via `getUserMedia`.
3. Browser `POST /realtime/session` → API mints an ephemeral client secret via the GA Realtime endpoint (`client.realtime.client_secrets.create` → `POST /v1/realtime/client_secrets`) with the support-agent instructions, tool specs, `output_modalities: ["audio"]`, and voice baked into the session, and returns it as a `RealtimeSessionToken`. (`output_modalities` accepts exactly one of `["text"]` or `["audio"]` — never both.)
4. Browser opens `RTCPeerConnection`, adds the mic track, creates a data channel for events, and POSTs its SDP offer directly to OpenAI's GA WebRTC endpoint (`POST https://api.openai.com/v1/realtime/calls`, `client_secret` as the bearer token). The model is fixed by the client secret, so it is no longer a query param.
5. Audio frames flow client → OpenAI and OpenAI → client. The model's tool-call events arrive on the data channel.
6. UI streams transcript turns into `LiveTranscript`.
7. User clicks **End Call** → browser closes the peer connection and POSTs accumulated session state to `/calls` (see [Call Bundles](call-bundles.md)).

> **`call_id` format contract.** The `call_id` is a 26-char **Crockford base32** ULID minted browser-side (`useRealtimeCall`'s `newCallId`). The server validates it against `^[0-9A-HJKMNP-TV-Z]{26}$` (Crockford alphabet — excludes `I`, `L`, `O`, `U`) in `runtime/calls.py`. The client mint and server validator **must agree on the alphabet**: a base36 mint (`0-9a-z`) emits `i/l/o/u` and is rejected with `400 Invalid call_id` on End Call.

## Edge Cases
- Mic permission denied → UI shows actionable error, no API call made
- `POST /realtime/session` fails (auth, quota) → UI surfaces the error from `ApiError.detail`
- WebRTC negotiation fails (ICE, network) → UI shows "Connection failed", user can retry. v1 does NOT implement a WebSocket fallback (out of scope, see plan §8).
- Model interrupts mid-tool-call → tool-call event is recorded in the trace with `status: "interrupted"`
- Tab loses focus during call → call continues (audio kept open), UI marks state as "background"
- Token expires before negotiation completes → UI retries `/realtime/session` once, then surfaces error
- Audio capture / WAV encoding fails → UI surfaces the error, but the call is still finalized: the transcript + tool trace + summary land in B2 with an empty `audio.wav` and `audio_bytes: 0` in `manifest.json`. Failure is non-fatal by design — we never want to lose the structured artifacts because the recorder hiccupped.

## UX States
- Idle: Start Call button
- Connecting: Spinner, "Setting up call…"
- Connected: Live transcript streaming, mic indicator, End Call button
- Ended: End-of-call summary card with link to bundle in `/calls`
- Error: ErrorState with retry

## Verification
- Test files: `services/api/tests/test_realtime_session.py` (mocks `repo.openai_client.mint_realtime_session`), `apps/web/e2e/call-smoke.spec.ts`
- Required cases: token mint happy path, mint failure surfaces 502/503, mic permission denied UI path, peer-connection failure UI path
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure && pnpm test:e2e`
- Pass criteria: all pytest tests green, e2e smoke passes with mocked OpenAI

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — "Realtime Audio Flow" diagram
- [Tool Calling](tool-calling.md)
- [Call Bundles](call-bundles.md)
- [SECURITY.md](../SECURITY.md) — ephemeral token lifetime, audio data residency
