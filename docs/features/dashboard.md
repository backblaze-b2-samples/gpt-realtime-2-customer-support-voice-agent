<!-- last_verified: 2026-05-28 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance view of voice-agent activity: how many calls were handled, average duration, what tools the agent used most, and how often the agent resolved the issue without creating a ticket (deflection rate).

## Used By
- UI: `/` page (dashboard home)
- API: `GET /calls`, `GET /calls/stats`, `GET /calls/stats/activity`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx` — 4 stat cards (calls today, calls this week, average duration, deflection rate)
- `apps/web/src/components/dashboard/recent-calls-table.tsx` — last 10 calls (replaces the starter-kit recent-uploads table)
- `apps/web/src/components/dashboard/call-volume-chart.tsx` — bar chart of calls per day (same shape as the starter's upload chart)
- `apps/web/src/lib/api-client.ts` — `getCallStats()`, `getCalls()`, `getCallVolumeActivity()`
- `services/api/app/runtime/calls.py` — `GET /calls/stats` handler
- `services/api/app/service/call_orchestrator.py` — stats aggregation
- `services/api/app/repo/b2_calls.py` — `list_call_ids()` data access (paginates the `calls/` prefix with `Delimiter="/"`)
- `services/api/app/service/call_orchestrator.py` — `list_calls()` aggregates per-call manifests on top of `list_call_ids()`

## Canonical Files
- Stats cards: `apps/web/src/components/dashboard/stats-cards.tsx`
- Stats service logic: `services/api/app/service/call_orchestrator.py`

## Inputs
- None (dashboard loads data automatically)

## Outputs
- `GET /calls/stats` → `CallStats` (calls_today, calls_this_week, avg_duration_seconds, total_tool_calls, tickets_created, deflection_rate)
- `GET /calls?limit=10` → `Call[]` for recent-calls table (sorted newest-first)
- `GET /calls/stats/activity?days=7` → `DailyCallCount[]` for the chart (server-side aggregation)

## Flow
- Page loads → three parallel API calls (stats, recent calls, call-volume activity)
- Stats cards display calls today, calls this week, average duration, deflection rate
- Tool-call breakdown is computed server-side from each bundle's `tools.jsonl` and shown alongside the chart
- Recent-calls table shows last 10 calls with summary, duration, tool count, timestamp

## Edge Cases
- API unavailable → stats default to zeros, table shows empty state, chart shows "No data"
- No calls yet → all stats are 0, table empty, chart empty
- Large call count → stats endpoint paginates through the `calls/` prefix with `ContinuationToken`
- Bundles missing `manifest.json` (incomplete writes) → excluded from stats, surfaced as a warning row

## UX States
- Loading: skeleton placeholders for cards, chart, and table
- Empty: "No calls yet — start your first call from the Call screen"
- Loaded: populated cards, chart, table

## Verification
- Test files: none yet — dashboard stats and recent-calls tests are tracked as an open item in [tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md).
- Required cases (planned): stats with calls, stats with empty bucket, partial bundle excluded, API error fallback
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
- [Call Bundles](call-bundles.md)
