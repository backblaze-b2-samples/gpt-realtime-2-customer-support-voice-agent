<!-- last_verified: 2026-05-28 -->
# App Workflows

User journeys inside the application.

## Primary journey: Handle a Support Call

1. Caller opens the app and lands on `/call` (the primary CTA in the sidebar).
2. Click **Start Call**. The browser:
   - Requests microphone permission.
   - Calls `POST /realtime/session` on the API.
   - The API mints an **ephemeral OpenAI Realtime session token** and returns it.
   - The browser opens a WebRTC peer connection **directly to OpenAI** using the token. Audio bytes do not pass through our backend.
3. The agent greets the caller and answers in natural full-duplex voice. The caller can interrupt at any time (barge-in handled by the model).
4. As the model invokes tools (`account_lookup`, `order_status`, `create_ticket`, `escalate`), the browser forwards each call to `POST /tools/invoke`. The API dispatches via `CrmAdapter` (the v1 build ships `MockCrmAdapter` with in-memory fixtures) and returns the result, which is replayed into the Realtime session.
5. The UI shows three live panels: a mic-level indicator, a streaming transcript, and a tool-trace timeline. Each tool call is rendered with its name, args, latency, and result.
6. Click **End Call**. The browser sends the in-flight session state to `POST /calls`. The orchestrator:
   - Writes `calls/<call_id>/audio.wav`, `transcript.jsonl`, `tools.jsonl` to B2.
   - Generates a Markdown summary via the non-realtime OpenAI model and writes `summary.md`.
   - Writes `manifest.json` last (presence of `manifest.json` = bundle is complete).
7. The end-of-call card shows summary line + duration + tool count + a link to the bundle in `/calls`.

See: [Realtime Voice](features/realtime-voice.md), [Tool Calling](features/tool-calling.md), [Call Bundles](features/call-bundles.md).

## Browse Call Bundles (sample-specific Library view)

- User navigates to `/calls`.
- Page lists every call (`calls/` prefix in B2), newest first. Each row shows summary, duration, tool count, timestamp.
- Click a row to open the detail pane: inline audio player (presigned URL), transcript viewer, tool-trace timeline, full summary.
- Delete a call via the row action: removes every object under `calls/<id>/`.
- See: [Calls Explorer](features/calls-explorer.md).

## View Dashboard

- User navigates to `/` (home).
- Stats cards show: calls today, calls this week, average duration, tool-call breakdown, deflection rate (resolved-in-call vs ticket-created).
- Activity chart shows last 7 days of call volume as a bar chart.
- Recent-calls table shows the last 10 bundles with summary, duration, tool count, date.
- See: [Dashboard](features/dashboard.md).

## Browse the Full Bucket (operator view)

- User navigates to `/files` — this is the unchanged starter-kit file explorer scoped to the **whole** bucket.
- Used by operators who need to inspect or clean up arbitrary objects (not just call bundles).
- See: [File Browser](features/file-browser.md).

## Upload Reference Documents (operator view)

- User navigates to `/upload` — also kept from the starter kit.
- Drag-and-drop upload for reference materials (knowledge-base docs, policy PDFs, etc.) that you want available in the bucket alongside call bundles.
- See: [File Upload](features/file-upload.md).
