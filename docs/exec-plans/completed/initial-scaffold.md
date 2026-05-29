# gpt-realtime-2-customer-support-voice-agent — Initial Scaffold Plan

> **Source of truth:** `.claude/scratch/vcsk-ca1e4768-ef16-40ec-b5fe-90527aa11527/` (vibe-coding-starter-kit clone). All keep/trim/add deltas are computed against that tree.

---

## 1. Purpose

A browser-based customer-support voice agent powered by **OpenAI's GPT-Realtime-2** model. A user clicks **Start Call**, talks to the agent in natural full-duplex audio (interrupt freely), and the agent calls mock helpdesk/CRM tools — `account_lookup`, `order_status`, `create_ticket`, `escalate` — to actually resolve the request. The moment the call ends, the app persists a complete **call bundle** to B2: WAV audio, transcript JSONL, tool-trace JSONL, and a Markdown summary written by the model. The dashboard surfaces aggregate stats (calls handled, average duration, tool-call counts, deflection rate); a sample-specific **Calls** explorer drills into any single bundle and plays back the audio.

Target audience: developers evaluating OpenAI's Realtime API for production support workflows, and B2 prospects who need a credible "audio + AI artifacts pile up fast in object storage" reference app.

SEO targets: "GPT-Realtime-2 voice agent", "customer support voice AI", "OpenAI Realtime API sample app".

---

## 2. Architecture delta from vibe-coding-starter-kit

| Keep (as-is) | Trim (remove from starter) | Add (new for this sample) |
|---|---|---|
| `apps/web/src/components/ui/` (shadcn primitives) | `apps/web/src/components/dashboard/` — replace defaults; structure stays, contents change | `apps/web/src/app/call/page.tsx` — live call UI (Start/End/Mute, waveform, live transcript, tool-trace panel) |
| `apps/web/src/app/globals.css` design tokens | `apps/web/src/components/dashboard/upload-chart.tsx` — replaced with call-volume chart of same shape | `apps/web/src/app/calls/page.tsx` — **sample-specific Calls explorer** (browse `calls/` prefix in B2, play audio, view transcript/summary/tool trace) |
| `apps/web/src/app/design/page.tsx` + `components/design/*` | Default dashboard `stats-cards.tsx` contents (kept as component, contents rewritten) | `apps/web/src/components/call/*` — `CallConsole`, `LiveTranscript`, `ToolTracePanel`, `MicLevelIndicator`, `EndCallSummary` |
| `apps/web/src/app/files/page.tsx` + `components/files/*` — **full-bucket explorer (non-negotiable keep)** | `apps/web/src/components/dashboard/recent-uploads-table.tsx` — replaced by `recent-calls-table.tsx` | `apps/web/src/components/calls/*` — `CallsList`, `CallDetail`, `CallAudioPlayer`, `TranscriptViewer`, `SummaryCard` |
| `apps/web/src/app/upload/page.tsx` + `components/upload/*` | `services/api/app/runtime/upload.py` size limits stay, but the route is **kept** (operators may still upload reference docs to the bucket) | `apps/web/src/hooks/use-realtime-call.ts` — WebRTC + WS lifecycle, audio capture, playback, interrupt handling |
| `apps/web/src/components/layout/app-sidebar.tsx` (extend, don't rewrite) | `services/api/app/service/metadata.py` — keep file exists, but trim image/PDF extraction; this sample doesn't need EXIF | `services/api/app/runtime/realtime.py` — POST `/realtime/session` returns ephemeral OpenAI Realtime session token (client opens WebRTC directly to OpenAI; server never proxies audio bytes) |
| `apps/web/src/lib/api-client.ts`, `lib/queries.ts` patterns (extend with new endpoints) | `services/api/tests/test_structure.py` — keep, just update layer/file list | `services/api/app/runtime/calls.py` — POST `/calls` (finalize bundle), GET `/calls`, GET `/calls/{id}`, GET `/calls/{id}/audio` (presigned), DELETE `/calls/{id}` |
| `packages/shared/src/types.ts` shape (extend with `Call`, `ToolEvent`, `TranscriptTurn`) | `docs/features/metadata-extraction.md` — **delete**, replaced by `tool-calling.md` | `services/api/app/runtime/tools.py` — POST `/tools/invoke` (server-side tool execution; called via OpenAI Realtime tool-calling) |
| `services/api/app/repo/b2_client.py` (S3, signature v4, custom user agent) — extend with `put_call_bundle`, `list_calls`, `get_presigned_audio_url` | Default `B2_KEY_ID` env var name — **rename** to `B2_APPLICATION_KEY_ID` per parent CLAUDE.md standard | `services/api/app/repo/openai_client.py` — wraps `openai` SDK calls for **non-realtime** uses (summary generation post-call, transcription fallback if needed). Realtime API stays client↔OpenAI direct |
| `services/api/app/runtime/health.py`, `metrics.py` | | `services/api/app/repo/helpdesk_adapter.py` — **adapter interface**: `CrmAdapter` Protocol + `MockCrmAdapter` impl with in-memory fixtures (`accounts`, `orders`, `tickets`). Real Zendesk/Intercom impls are an explicit extension point, not in v1 |
| Layered architecture (`types → config → repo → service → runtime`) — **strict** | | `services/api/app/service/call_orchestrator.py` — assembles bundle from in-flight session state, posts to B2, generates summary |
| Structural tests (`pnpm check:structure`) — extend coverage to new layers | | `services/api/app/service/tool_executor.py` — dispatches realtime tool calls to `CrmAdapter`, records each to the trace |
| TanStack Query data layer (`lib/queries.ts`) | | `services/api/app/types/calls.py`, `tools.py`, `realtime.py` — Pydantic models for `Call`, `TranscriptTurn`, `ToolEvent`, `RealtimeSessionToken`, `CrmAccount`, `Order`, `Ticket` |
| Doctor preflight (`scripts/doctor.mjs`) — extend to check `OPENAI_API_KEY` | | E2E test stub: `apps/web/e2e/call-smoke.spec.ts` (mock the OpenAI session, verify UI flow) |
| `infra/railway/` deploy config | | `docs/features/{realtime-voice,tool-calling,call-bundles,calls-explorer}.md` |
| `.pre-commit-config.yaml`, lint, ruff configs | | `OPENAI_*` env block in `.env.example` |

### Non-negotiable keep + add (per skill contract)

- **Bucket explorer kept**: `/files` route and `components/files/*` stay verbatim. Operators can still browse the whole bucket.
- **Sample-specific asset explorer added**: `/calls` route + `components/calls/*` provide a **Calls** view scoped to the `calls/` prefix in B2 — list, play audio, view transcript/summary/tool trace, delete bundle. This is the per-app "Library" view called out in the skill contract.

### Why this delta shape

The starter kit gives us essentially everything **except** the realtime audio loop, the tool-calling plumbing, and the per-call bundle layout. We're additive in the API (new routes, new repo methods, new service modules) and subtractive only on the **dashboard content** (different stats) and **metadata-extraction** (irrelevant). The layered architecture, structural tests, file-size limits, TanStack Query data layer, design system, and full-bucket file explorer all carry forward unchanged.

---

## 3. B2 surface (S3 operations exercised)

**S3 API only — no b2-native calls.** Per parent CLAUDE.md standard #1.

| Operation | Where | Purpose |
|---|---|---|
| `PutObject` | `repo/b2_client.py::put_call_bundle()` | Write `calls/<call_id>/audio.wav`, `transcript.jsonl`, `tools.jsonl`, `summary.md`, `manifest.json` |
| `ListObjectsV2` | `repo/b2_client.py::list_calls()`, `list_objects()` | Calls explorer (prefix `calls/`); full-bucket explorer (no prefix) |
| `HeadObject` | `repo/b2_client.py::get_call_manifest()` | Read per-call `manifest.json` metadata cheaply |
| `GetObject` | `repo/b2_client.py::get_object()` | Fetch transcript/summary/manifest for display |
| `DeleteObject` (loop) | `repo/b2_client.py::delete_call()` | Delete entire `calls/<id>/` prefix |
| `GeneratePresignedUrl` (`get_object`) | `repo/b2_client.py::get_presigned_audio_url()` | 10-minute presigned URL for audio playback, `response-content-disposition=inline` |

**Custom user agent (standard #2):** `boto3` `Config` `user_agent_extra="gpt-realtime-2-customer-support-voice-agent/0.1.0"` set in `b2_client.py::_make_client()`. The exact UA tag will come from the Tier 1 sub-issue's `user_agent_extra` field if/when this sample gets one; placeholder until then.

**Env vars (standard #3):** `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_ENDPOINT` — renamed from starter kit's `B2_KEY_ID`. Optional `B2_REGION` for clients that need it explicit. The doctor script and `settings.py` will be updated together.

No b2-native API usage. If any future feature wants b2-native (e.g. file locks, application-key creation), it must be justified per parent CLAUDE.md.

---

## 4. Key features (seed for README + `docs/features/`)

1. **Realtime voice loop** — Browser captures mic via WebRTC, opens a peer connection directly to OpenAI Realtime (ephemeral token from our backend). Interruption (barge-in) handled by the model; UI shows speaker-state indicator. → `docs/features/realtime-voice.md`
2. **Mock helpdesk tool calling** — Four tools registered with the Realtime session: `account_lookup(email)`, `order_status(order_id)`, `create_ticket(account_id, subject, body)`, `escalate(reason)`. Backed by `MockCrmAdapter` with in-memory fixtures; adapter interface ready for real Zendesk/Intercom impls. → `docs/features/tool-calling.md`
3. **Per-call B2 bundles** — Every call writes `audio.wav` + `transcript.jsonl` + `tools.jsonl` + `summary.md` + `manifest.json` under `calls/<call_id>/`. Bundle generation is idempotent and survives partial failures. → `docs/features/call-bundles.md`
4. **Calls explorer (sample-specific Library view)** — Scoped to `calls/` prefix. Each row shows summary line, duration, tool count, timestamp; clicking opens detail with inline audio player, transcript viewer, tool-trace timeline. → `docs/features/calls-explorer.md`
5. **Support dashboard** — Replaces starter's upload metrics with: calls today / week, average duration, tool-call breakdown, deflection rate (tickets created vs resolved in-call). Same chart/card components, different aggregations. → `docs/features/dashboard.md` (rewritten)
6. **Full bucket explorer (kept from starter)** — `/files` route still browses the whole bucket for operators. Documented as "ops view". → `docs/features/file-browser.md` (light edits to mention coexistence with `/calls`)

---

## 5. Doc transforms

| Doc | Action |
|---|---|
| `README.md` | **Rewrite** — new hero, screenshots placeholder, quickstart includes `OPENAI_API_KEY`, feature list points at the six new/edited features above. Replace `vibe-coding-starter-kit` references throughout. |
| `AGENTS.md` | **Rewrite §1 repo map + §2 building-on-this-kit** — call out the realtime/calls routes and the adapter pattern. **Keep** §3 invariants, §4 quality expectations, §5 mechanical enforcement, §7 workflow verbatim. |
| `ARCHITECTURE.md` | **Rewrite** components/data-flows for the realtime + tools + call-bundle pipeline. Layered diagram unchanged; **add** "Realtime audio flow: client↔OpenAI direct; server only mints tokens and executes tool calls" callout. |
| `docs/features/file-upload.md` | **Keep**, light edit to note this is a "reference upload" surface, not the primary capture path |
| `docs/features/file-browser.md` | **Keep**, light edit to disambiguate from `/calls` |
| `docs/features/dashboard.md` | **Rewrite** — new stats, new chart, new recent-calls table |
| `docs/features/metadata-extraction.md` | **Delete** — not used here |
| `docs/features/realtime-voice.md` | **New** stub (inputs: mic + ephemeral token; outputs: audio frames + transcript events; edge cases: mic permission denied, dropped WS, model interruption mid-tool-call) |
| `docs/features/tool-calling.md` | **New** stub (registered tools, adapter interface, tool-call lifecycle, error semantics) |
| `docs/features/call-bundles.md` | **New** stub (bundle layout, write semantics, idempotency, retention) |
| `docs/features/calls-explorer.md` | **New** stub (UI, presigned URL flow, delete semantics) |
| `docs/app-workflows.md` | **Rewrite** primary user journey: "Caller starts call → talks → agent uses tools → call ends → bundle in B2 → operator reviews in Calls explorer" |
| `docs/dev-workflows.md` | **Light edit** — add a "Mocking OpenAI Realtime in tests" section, otherwise keep |
| `docs/SECURITY.md` | **Light edit** — note OpenAI API key handling, ephemeral session-token lifetime, audio data residency |
| `docs/RELIABILITY.md` | **Light edit** — note partial-failure semantics for bundle writes |
| `docs/design-system.md` | **Keep verbatim** |
| `docs/exec-plans/completed/` | Plan file lands here at Phase 5 finalize |

---

## 6. Rename table

Every identifier that changes from the starter to this sample:

| From | To |
|---|---|
| `vibe-coding-starter-kit` (kebab) | `gpt-realtime-2-customer-support-voice-agent` |
| `Vibe Coding Starter Kit` (Title) | `GPT-Realtime-2 Customer Support Voice Agent` |
| `vibe_coding_starter_kit` (snake, where used) | `gpt_realtime_2_customer_support_voice_agent` |
| `OSS Starter Kit` (sidebar header) | `GPT-Realtime-2 Voice Agent` |
| package `@vibe-coding-starter-kit/web` | `@gpt-realtime-2-customer-support-voice-agent/web` |
| package `@vibe-coding-starter-kit/shared` | `@gpt-realtime-2-customer-support-voice-agent/shared` |
| GitHub Actions workflow slug (if any) | `gpt-realtime-2-customer-support-voice-agent-ci` |
| Image / container tag (if any) | `gpt-realtime-2-customer-support-voice-agent` |
| UTM `utm_content=b2ai-oss-start` | `utm_content=b2ai-gpt-realtime-voice-agent` |
| boto3 `user_agent_extra="vibe-coding-starter-kit/x.y.z"` | `user_agent_extra="gpt-realtime-2-customer-support-voice-agent/0.1.0"` |
| `B2_KEY_ID` (env var) | `B2_APPLICATION_KEY_ID` (parent CLAUDE.md standard) |
| `b2_key_id` (settings field) | `b2_application_key_id` |
| README screenshots `b2-starterkit-*.png` | placeholders `voice-agent-*.png` (binary creation deferred per skill rules) |
| Sidebar entry `Upload` | **kept** (ops upload) |
| Sidebar entry `Files` | **kept** (full-bucket ops view) |
| New sidebar entries | `Call` (primary CTA, top of nav), `Calls` (bundle explorer) |
| Dashboard route `/` content | new stats |
| Default OpenAI realtime model id | `gpt-realtime-2` (configurable via `OPENAI_REALTIME_MODEL`) |

---

## 7. Resolved open questions

| Question | Decision | Rationale |
|---|---|---|
| Mock helpdesk only, or include Zendesk/Intercom adapters? | **Mock-only with adapter interface** | Keeps v1 scope tight; adapter Protocol leaves a clean extension seam for real CRMs without bringing in extra SDKs/secrets. |
| Full audio by default, or transcript-only privacy default? | **Always full audio, no toggle** (user choice) | Maximises the "B2 bundles accumulate" story. No environment toggle — if a user wants transcript-only they fork the call orchestrator. |

---

## 8. Out of scope for v1

- Multi-tenant auth / per-user call history
- Real Zendesk/Intercom/Salesforce adapters (interface is ready; impls aren't)
- Sentiment analysis, agent QA scoring
- Live supervisor handoff
- Storage lifecycle rules (B2 retention policies) — documented as a future enhancement
- WebSocket fallback if WebRTC negotiation fails — surface the error and ask user to retry
- Audio compression beyond what the Realtime API ships (we persist what we receive)
- Production-grade rate limiting beyond per-IP

---

## 9. Environment variables (final `.env.example`)

```
# Backblaze B2 (required) — uses parent CLAUDE.md canonical names
B2_ENDPOINT=https://s3.us-west-004.backblazeb2.com
B2_APPLICATION_KEY_ID=
B2_APPLICATION_KEY=
B2_BUCKET_NAME=
B2_REGION=us-west-004

# OpenAI (required)
OPENAI_API_KEY=
OPENAI_REALTIME_MODEL=gpt-realtime-2
OPENAI_SUMMARY_MODEL=gpt-4.1-mini

# App
API_PORT=8000
API_CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

---

## 10. Acceptance criteria for builder + reviewer

The scaffolded tree is "done" when:
- [ ] `pnpm install` and the Python `pip install -r requirements.txt` both succeed against a fresh checkout
- [ ] `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure` passes
- [ ] No `boto3` imports outside `services/api/app/repo/`
- [ ] No `openai` imports outside `services/api/app/repo/`
- [ ] Every Python file <300 lines
- [ ] Custom user agent set on the S3 client
- [ ] Env vars match parent CLAUDE.md canonical names exactly
- [ ] `/files` route + `components/files/*` present unchanged in structure
- [ ] `/calls` route + `components/calls/*` present (sample-specific explorer)
- [ ] README, AGENTS.md, ARCHITECTURE.md updated; new feature docs stubbed; obsolete docs removed
- [ ] No references to `vibe-coding-starter-kit` remain (except in initial-scaffold commit history attribution if any)
- [ ] No real secrets committed; `.env.example` is placeholder-only
