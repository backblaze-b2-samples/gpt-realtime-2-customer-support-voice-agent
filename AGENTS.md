<!-- last_verified: 2026-05-28 -->
# AGENTS.md

This is the authoritative control surface for all coding agents. Read this first.

## 1. Repository Map

```
apps/web/                                     Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  src/app/call/                               Live voice-agent console (Start/End/Mute, transcript, tool trace)
  src/app/calls/                              Sample-specific Library view (browse `calls/` prefix in B2)
  src/app/files/                              Full-bucket explorer (kept from starter kit — operator view)
  src/app/upload/                             Reference upload surface (kept from starter kit)
  src/app/page.tsx                            Support dashboard (call volume, duration, tool breakdown, deflection)
  src/components/call/                        CallConsole, LiveTranscript, ToolTracePanel, MicLevelIndicator, EndCallSummary
  src/components/calls/                       CallsList, CallDetail, CallAudioPlayer, TranscriptViewer, SummaryCard
  src/components/files/                       (kept) file browser primitives
  src/components/upload/                      (kept) dropzone / form / progress
  src/components/dashboard/                   stats-cards, call-volume chart, recent-calls table
  src/hooks/use-realtime-call.ts              WebRTC + data-channel lifecycle, audio capture, playback, interrupts

services/api/                                 FastAPI backend (layered: types/config/repo/service/runtime)
  app/runtime/realtime.py                     POST /realtime/session — mints ephemeral OpenAI Realtime token
  app/runtime/tools.py                        POST /tools/invoke — dispatches model-issued tool calls
  app/runtime/calls.py                        POST/GET/DELETE /calls — bundle lifecycle
  app/runtime/{files,upload,health,metrics}.py  (kept from starter kit)
  app/service/call_orchestrator.py            Assemble + persist call bundle, generate summary
  app/service/tool_executor.py                Dispatch tool calls via CrmAdapter, record trace
  app/repo/b2_client.py                       (kept from starter) generic file-level S3 ops
  app/repo/b2_calls.py                        (new) per-call bundle ops: put_call_artifact, list_call_ids, get_presigned_audio_url, delete_call
  app/repo/openai_client.py                   Wraps `openai` SDK for non-realtime calls (summary)
  app/repo/helpdesk_adapter.py                CrmAdapter Protocol + MockCrmAdapter (in-memory fixtures)
  app/types/{calls,tools,realtime}.py         New Pydantic models
  app/types/{files,upload,stats,formatting}.py  (kept)

packages/shared/                              Shared TypeScript types (Call, ToolEvent, TranscriptTurn, …)
docs/                                         System of record (features, workflows, security, reliability)
docs/exec-plans/                              Execution plans and tech debt tracker
infra/railway/                                Deployment config
```

## 2. Building on This Sample

This is the **`gpt-realtime-2-customer-support-voice-agent` sample**, derived from the upstream B2 starter kit. The starter-kit contract still applies: the UI primitives, design tokens, full bucket explorer (`/files`), and reference upload route (`/upload`) are non-negotiable keeps. On top of those, this sample adds the voice-agent surface area.

**Non-negotiable keeps (do not strip, rename, or replace)**
- **UI kit / design system.** `apps/web/src/components/ui/` (shadcn primitives), the design tokens in `apps/web/src/app/globals.css`, and the `/design` reference page. Build new screens with these primitives; never edit the generated `components/ui/` files directly. Restyling happens through tokens in `globals.css`.
- **Full bucket explorer.** `/files` route, `apps/web/src/app/files/`, and `apps/web/src/components/files/` stay verbatim. The Files sidebar entry stays.
- **Reference upload.** `/upload` route, `apps/web/src/app/upload/`, and `apps/web/src/components/upload/` stay. The Upload sidebar entry stays.

**Sample-specific surface (extend, don't remove)**
- **Call.** `/call` route + `components/call/*` — primary entry point. The voice loop, transcript stream, and tool-trace UI live here. The Realtime session is opened **client to OpenAI directly** via an ephemeral token from `POST /realtime/session` — the API server never sees audio bytes.
- **Calls (sample-specific Library view).** `/calls` route + `components/calls/*` — scoped to the `calls/` prefix in B2. List, play audio, view transcript + summary + tool trace, delete bundle.
- **Helpdesk adapter pattern.** All tool execution goes through `CrmAdapter` (Protocol) in `app/repo/helpdesk_adapter.py`. v1 ships `MockCrmAdapter` only. Real Zendesk/Intercom/Salesforce impls are an explicit extension point — add a new impl in `repo/` and switch via config; do not pull SDK calls into the service layer.
- **Dashboard.** Rewritten for support metrics (call volume, average duration, tool-call breakdown, deflection rate). Same `runtime -> service -> repo` data flow, same TanStack Query hook pattern.

**Why this contract exists**
- The starter-kit pieces are the reusable B2-backed scaffolding that makes this sample comparable across the program. The sample-specific surface is what makes this particular sample about voice agents instead of file management.

## 3. Architectural Invariants

**Backend layering**: `types` -> `config` -> `repo` -> `service` -> `runtime`

- No backward imports across layers
- No `boto3` outside `repo/`
- No `openai` outside `repo/`
- No business logic in route handlers (`runtime/`)
- All external APIs wrapped in `repo/` adapters (B2 client, OpenAI client, helpdesk adapter)
- All request/response data validated at boundary (Pydantic models)
- No shared mutable state across layers

**Frontend**: shadcn/ui components in `src/components/ui/` are generated — never modify them.

**Data fetching**: every API call flows through TanStack Query hooks in `apps/web/src/lib/queries.ts`. No bare `useEffect + fetch` patterns. New endpoints touch three files: `runtime/<router>.py`, `lib/api-client.ts`, `lib/queries.ts`. (The Realtime peer connection in `use-realtime-call.ts` is the documented exception — WebRTC lifecycle does not fit a Query model.)

**OpenAI API key**: never exposed to the browser. The browser only ever receives ephemeral Realtime session tokens.

## 4. Quality Expectations

- **DRY** — do not duplicate logic, types, or constants. Extract shared code only when used in 2+ places.
- Structured JSON logging only — no `print()` statements
- No raw SDK calls outside `repo/` layer
- Files stay under 300 lines
- Tests added or updated for every behavior change
- Docs updated in same PR as code changes
- Lint clean before merge
- Prefer boring, composable libraries over clever abstractions
- No implicit type assumptions — use typed models

## 5. Mechanical Enforcement

| Rule | Enforced by |
|------|-------------|
| No backward imports | `tests/test_structure.py::test_no_backward_imports` |
| No boto3 outside repo/ | `tests/test_structure.py::test_boto3_only_in_repo` |
| No openai outside repo/ | `tests/test_structure.py::test_openai_only_in_repo` |
| File size < 300 lines | `tests/test_structure.py::test_file_size_limits` |
| All layers exist | `tests/test_structure.py::test_all_layers_exist` |
| No bare print() | `ruff` rule T20 |
| Import ordering | `ruff` rule I001 |
| Frontend strict equality | `eslint` rule eqeqeq |
| No unused vars | `eslint` + `ruff` rules |

## 6. Commands

```bash
# Run
pnpm dev               # start both frontend and backend
pnpm dev:web           # frontend only
pnpm dev:api           # backend only

# Test & Lint
pnpm lint              # frontend lint (eslint)
pnpm build             # frontend type check + build
pnpm lint:api          # backend lint (ruff)
pnpm test:api          # backend tests (pytest)
pnpm check:structure   # structural boundary tests
pnpm test:e2e          # Playwright e2e tests
```

## 7. Agent Workflow

1. Read this file first.
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) before structural changes.
3. For non-trivial changes, create a plan in `docs/exec-plans/active/`.
4. Implement the smallest coherent change.
5. Run: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
6. Update docs in the same PR (see §9).
7. Move completed plans to `docs/exec-plans/completed/`.
8. Only change files relevant to the task. No drive-by improvements.

## 8. Frontend Conventions

See [docs/dev-workflows.md](docs/dev-workflows.md) for full details, including how to mock the OpenAI Realtime API in tests.

## 9. Doc Update Mapping

| Change Type | Update Location |
|-------------|-----------------|
| Feature logic, inputs, outputs, tests | `docs/features/<feature>.md` |
| User journeys | `docs/app-workflows.md` |
| System layout, deployments | `ARCHITECTURE.md` |
| Dev or testing process | `docs/dev-workflows.md` |
| Setup or scope changes | `README.md` |
| Security changes | `docs/SECURITY.md` |
| Reliability changes | `docs/RELIABILITY.md` |
| Active work plans | `docs/exec-plans/active/` |
| Known tech debt | `docs/exec-plans/tech-debt-tracker.md` |

If documentation and implementation conflict, update docs in the same PR. Documentation rot destroys agent reliability.

## 10. Doc Map

| Topic | Location |
|-------|----------|
| System layout, data flows, boundaries | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Feature docs | [docs/features/](docs/features/) |
| User journeys | [docs/app-workflows.md](docs/app-workflows.md) |
| Engineering workflows and testing | [docs/dev-workflows.md](docs/dev-workflows.md) |
| Security principles | [docs/SECURITY.md](docs/SECURITY.md) |
| Reliability expectations | [docs/RELIABILITY.md](docs/RELIABILITY.md) |
| Execution plans | [docs/exec-plans/](docs/exec-plans/) |
| Tech debt | [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) |

## 11. When Unsure

- Prefer boring, stable libraries
- Prefer small PRs over large changes
- Add tests with every change
- Never bypass lint rules without explicit instruction
- Ask before making destructive or irreversible changes
