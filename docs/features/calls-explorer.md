<!-- last_verified: 2026-05-28 -->
# Feature: Calls Explorer

## Purpose
A sample-specific Library view at `/calls` that lets operators browse, play, inspect, and delete per-call bundles stored under the `calls/` prefix in B2. This is the read side of the system; the write side is documented in [Call Bundles](call-bundles.md).

This view is **scoped to call bundles**. The full bucket explorer at `/files` is unchanged and still shows every object in the bucket.

## Used By
- UI: `/calls` page (list), `/calls/[id]` detail pane
- API: `GET /calls`, `GET /calls/{id}`, `GET /calls/{id}/audio`, `DELETE /calls/{id}`

## Core Functions
- `apps/web/src/components/calls/CallsList.tsx` — table of calls (summary, duration, tool count, timestamp); newest first
- `apps/web/src/components/calls/CallDetail.tsx` — detail layout with audio player, transcript, tool trace, summary
- `apps/web/src/components/calls/CallAudioPlayer.tsx` — `<audio>` element fed by the presigned URL
- `apps/web/src/components/calls/TranscriptViewer.tsx` — renders `transcript.jsonl` with timestamps and speaker labels
- `apps/web/src/components/calls/SummaryCard.tsx` — renders `summary.md`
- `services/api/app/runtime/calls.py` — list/get/audio/delete routes
- `services/api/app/service/call_orchestrator.py` — `get_call_detail()` aggregates manifest + transcript + tools + summary into a single payload

## Canonical Files
- Calls list: `apps/web/src/components/calls/CallsList.tsx`
- Calls detail: `apps/web/src/components/calls/CallDetail.tsx`
- Backend aggregation: `services/api/app/service/call_orchestrator.py::get_call_detail()`

## Inputs
- `GET /calls?limit=100` — optional `limit` (1-1000, default 100)
- `GET /calls/{id}` — `id` is the ULID from the bundle prefix
- `GET /calls/{id}/audio` — same `id`
- `DELETE /calls/{id}` — same `id`

## Outputs
- `GET /calls` → `Call[]` (manifest summaries, sorted newest-first by `started_at`)
- `GET /calls/{id}` → `CallDetail` (`{ manifest, transcript, tools, summary_markdown }`)
- `GET /calls/{id}/audio` → `{ url: string }` — 10-min presigned `get_object` URL with `response-content-disposition=inline`
- `DELETE /calls/{id}` → `{ deleted: true, call_id, keys_removed: number }`

## Flow (list)
1. User navigates to `/calls`.
2. Page calls `useCalls()` → `GET /calls`.
3. Each row renders summary + duration + tool count + timestamp; click expands detail.

## Flow (detail)
1. User clicks a row → `useCallDetail(call_id)` → `GET /calls/{id}`.
2. Detail pane renders manifest header, audio player, transcript viewer, tool-trace timeline, summary card.
3. Audio player calls `useCallAudioUrl(call_id)` → `GET /calls/{id}/audio` → audio element points at the presigned URL.

## Flow (delete)
1. User clicks Delete → confirm dialog → `useDeleteCall().mutate(call_id)`.
2. API deletes every object under `calls/<id>/`, returns count.
3. TanStack Query invalidates the calls list; row disappears from the table.

## Edge Cases
- Incomplete bundle (missing `manifest.json`) → row still shown with badge "incomplete" and a delete affordance; detail pane shows only the artifacts that exist
- Missing `audio.wav` → audio player shows "Audio unavailable"
- Presigned URL expired → browser shows browser-level audio error; user can refresh the page to mint a new one
- Empty `calls/` prefix → "No calls yet — start your first call from the Call screen"
- `call_id` not found → 404 from API, UI shows ErrorState
- B2 unreachable → 502, ErrorState with retry

## UX States
- Loading: skeleton rows
- Empty: friendly empty-state with link to `/call`
- Error: ErrorState with retry
- Loaded: table with inline expand, audio player ready

## Verification
- Test files: none yet — calls-explorer list/detail/delete tests are tracked as an open item in [tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md).
- Required cases (planned): list happy path, list with incomplete bundle, detail happy path, audio URL presign happy path, delete success, delete of nonexistent id (404), B2 down (502)
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Call Bundles](call-bundles.md)
- [File Browser](file-browser.md) — coexists with this view for the full-bucket operator perspective
