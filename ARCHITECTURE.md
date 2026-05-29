<!-- last_verified: 2026-05-28 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - `/call` — live voice-agent console: Start/End/Mute, mic-level indicator, live transcript, tool-trace panel, end-of-call summary card
  - `/calls` — sample-specific Library view, scoped to the `calls/` prefix in B2: list, play audio, view transcript + summary + tool trace, delete bundle
  - `/` — support dashboard (call volume, average duration, tool-call breakdown, deflection rate)
  - `/files` — full bucket explorer, kept verbatim from the starter kit (operator view)
  - `/upload` — reference upload surface, kept from the starter kit
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - `POST /realtime/session` — mints an ephemeral OpenAI Realtime session token; client opens WebRTC directly to OpenAI
  - `POST /tools/invoke` — dispatches model-issued tool calls through `CrmAdapter` (`MockCrmAdapter` in v1)
  - `POST /calls` — finalizes a call: assembles bundle, generates summary, writes to B2
  - `GET /calls`, `GET /calls/{id}`, `GET /calls/{id}/audio` (presigned), `DELETE /calls/{id}`
  - `/files`, `/upload`, `/health`, `/metrics` — kept from the starter kit
  - B2 S3 integration via boto3 in `app/repo/`
  - OpenAI SDK calls (non-realtime: summary generation) in `app/repo/`
  - Structured JSON logging with request tracing
  - Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API (`Call`, `TranscriptTurn`, `ToolEvent`, `RealtimeSessionToken`, etc.)
  - Consumed by `apps/web/` as workspace dependency

## Realtime Audio Flow

```
Browser ── WebRTC peer connection (audio frames, model events) ──> OpenAI Realtime
   ▲                                                                     │
   │  POST /realtime/session                                              │
   │  (returns ephemeral session token)                                   │
   │                                                                     │
   └──── FastAPI backend ◄──── tool-call events ─────────────────────────┘
              │
              │  POST /tools/invoke (dispatch to CrmAdapter)
              ▼
        MockCrmAdapter (in-memory accounts/orders/tickets)
```

**The API never proxies audio bytes.** Its role is (1) mint short-lived session tokens, (2) execute tool calls dispatched via the Realtime data channel, and (3) persist the per-call bundle at end-of-call.

## Backend Layering

The API follows a strict layered architecture (unchanged from the starter kit):

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2 client, openai SDK) — no business logic
  |
service/   Business logic (orchestration, tool dispatch, bundle assembly)
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer (enforced by `tests/test_structure.py`)
4. `openai` only allowed in `repo/` layer (enforced by `tests/test_structure.py`)
5. All boundary data uses Pydantic models (no raw dicts across layers)
6. Each file stays under 300 lines (enforced by `tests/test_structure.py`)

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models
      files.py, upload.py, stats.py, formatting.py   (kept from starter)
      calls.py, tools.py, realtime.py                (new)
    config/                Settings loaded from environment
    repo/                  Data access layer
      b2_client.py         (kept from starter — generic file-level S3 ops)
      b2_calls.py          (new — per-call bundle ops: put_call_artifact,
                           list_call_ids, get_call_manifest, get_bundle_artifact,
                           get_presigned_audio_url, delete_call;
                           shares the boto3 client via b2_client.get_s3_client)
      openai_client.py     (new — non-realtime SDK usage, summary gen)
      helpdesk_adapter.py  (new — CrmAdapter Protocol + MockCrmAdapter)
    service/               Business logic
      files.py, upload.py, metadata.py (light trim — no EXIF/PDF for this sample)
      call_orchestrator.py (new — assemble + persist bundle)
      tool_executor.py     (new — dispatch tool calls, record trace)
    runtime/               FastAPI route handlers
      files.py, upload.py, health.py, metrics.py   (kept)
      realtime.py, tools.py, calls.py              (new)
  tests/                   pytest tests (structural + integration)
```

## Boundary Invariants

- **No external SDK leakage**: `boto3` and `openai` are only imported in `app/repo/`. All other layers interact with B2/OpenAI through the repo interface.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No mutable globals**: Configuration is read-only after init. No module-level mutable state shared between layers.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. All file keys validated against prefix allowlist.
- **Ephemeral OpenAI session tokens only**: `OPENAI_API_KEY` lives only in the API process. The browser never sees it.

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repo
  - See `infra/railway/README.md` for configuration (incl. `OPENAI_API_KEY`)

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API)
  - All call bundles stored under `calls/<call_id>/` (one prefix per call)
  - Operator uploads stored under `uploads/`
  - File listing and metadata via S3 `list_objects_v2` / `head_object`
  - No application database — B2 is the sole data store
  - No in-memory state survives a process restart (except the mock CRM fixtures, which are seeded fresh each boot)

## External Services

- **Backblaze B2 S3 API** — file storage, retrieval, deletion, presigned URLs
- **OpenAI Realtime API** — speech-to-speech model with tool calling (client-direct via WebRTC)
- **OpenAI Chat Completions** — post-call summary generation (server-side, via `repo/openai_client.py`)

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins
- **API -> B2** — authenticated via application keys, signature v4
- **API -> OpenAI** — authenticated via `OPENAI_API_KEY` (never exposed to browser)
- **Client -> OpenAI Realtime** — ephemeral session token (short-lived, scoped to one session)
- **Client -> B2** — presigned URLs for audio playback (10-min expiry, `Content-Disposition: inline`)

## Data Flows

- **Start call**: Browser -> `POST /realtime/session` -> API mints ephemeral token via `repo/openai_client.py` -> Browser opens WebRTC to OpenAI directly.
- **Tool call** (model-initiated): OpenAI emits a tool-call event on the data channel -> Browser forwards to `POST /tools/invoke` -> service dispatches via `CrmAdapter` (`MockCrmAdapter`) -> service records the event for the trace -> response replayed into the Realtime session.
- **End call**: Browser -> `POST /calls` (with in-flight transcript + tool trace + recorded audio) -> `call_orchestrator` writes `audio.wav`, `transcript.jsonl`, `tools.jsonl`, then calls OpenAI for the summary, then writes `summary.md` and finally `manifest.json` (signals "bundle complete").
- **List calls**: Browser -> `GET /calls` -> `service/call_orchestrator.py::list_calls()` calls `repo/b2_calls.py::list_call_ids()` (scoped to `calls/` prefix) and hydrates each id with its manifest -> returns metadata.
- **Audio playback**: Browser -> `GET /calls/{id}/audio` -> service generates 10-min presigned URL with `response-content-disposition=inline`.
- **Delete call**: Browser -> `DELETE /calls/{id}` -> service deletes every key under `calls/<id>/`.

The `/files`, `/upload`, `/health`, `/metrics` flows are unchanged from the starter kit.

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count, calls handled)
- `/health` endpoint (B2 connectivity check)

## Canonical Files

- Realtime route: `services/api/app/runtime/realtime.py`
- Tool dispatch route: `services/api/app/runtime/tools.py`
- Calls route: `services/api/app/runtime/calls.py`
- Call orchestrator: `services/api/app/service/call_orchestrator.py`
- Tool executor: `services/api/app/service/tool_executor.py`
- B2 generic file-level data access: `services/api/app/repo/b2_client.py`
- B2 per-call bundle data access: `services/api/app/repo/b2_calls.py`
- OpenAI repo: `services/api/app/repo/openai_client.py`
- Helpdesk adapter Protocol + mock impl: `services/api/app/repo/helpdesk_adapter.py`
- Pydantic models: `services/api/app/types/` (`calls.py`, `tools.py`, `realtime.py`, plus the unchanged starter-kit types)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Frontend Realtime hook: `apps/web/src/hooks/use-realtime-call.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Realtime Voice](docs/features/realtime-voice.md)
- [Tool Calling](docs/features/tool-calling.md)
- [Call Bundles](docs/features/call-bundles.md)
- [Calls Explorer](docs/features/calls-explorer.md)
- [Dashboard](docs/features/dashboard.md)
- [File Browser](docs/features/file-browser.md)
- [File Upload](docs/features/file-upload.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability + bundle write semantics
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
