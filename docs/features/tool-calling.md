<!-- last_verified: 2026-05-28 -->
# Feature: Tool Calling

## Purpose
Let the Realtime agent actually resolve support requests by invoking helpdesk tools (look up an account, check an order, create a ticket, escalate). v1 backs these tools with an in-memory `MockCrmAdapter`; the `CrmAdapter` Protocol is the seam where real Zendesk / Intercom / Salesforce impls plug in later.

## Used By
- UI: `/call` page (ToolTracePanel)
- API: `POST /tools/invoke`

## Core Functions
- `services/api/app/repo/helpdesk_adapter.py` — `CrmAdapter` Protocol + `MockCrmAdapter` impl with in-memory fixtures (accounts, orders, tickets)
- `services/api/app/repo/openai_client.py::_tool_specs()` — the JSON-Schema tool specs sent to OpenAI as part of the Realtime session config (single source of truth for the schemas the model sees)
- `services/api/app/service/tool_executor.py` — dispatches model-issued tool calls, records each to the in-flight trace
- `services/api/app/runtime/tools.py` — `POST /tools/invoke` route
- `services/api/app/types/tools.py` — Pydantic models for the HTTP layer and the trace: `ToolCallRequest` and `ToolCallResponse` (request/response for `POST /tools/invoke`), `ToolEvent` (one row written to `tools.jsonl`), and the helpdesk-fixture shapes `CrmAccount`, `OrderItem`, `Order`, `Ticket`
- `apps/web/src/components/call/ToolTracePanel.tsx` — timeline of tool events with latency, args, result
- `apps/web/src/hooks/use-realtime-call.ts` — forwards model-issued tool-call events to `/tools/invoke` and feeds the result back into the data channel

## Canonical Files
- Adapter Protocol + mock impl: `services/api/app/repo/helpdesk_adapter.py`
- Tool dispatch pattern: `services/api/app/service/tool_executor.py`

## Registered Tools

| Tool | Args | Result |
|---|---|---|
| `account_lookup` | `email: str` | `CrmAccount \| None` (id, name, tier, contact) |
| `order_status` | `order_id: str` | `Order \| None` (id, status, eta, items) |
| `create_ticket` | `account_id: str, subject: str, body: str` | `Ticket` (id, status="open", created_at) |
| `escalate` | `reason: str, account_id: str \| None` | `{ escalation_id, accepted: bool }` |

`MockCrmAdapter.order_status` normalizes the incoming `order_id` (lowercase, strip non-alphanumerics, fall back to unambiguous digits) so a voice caller's phrasing — `ord_1001`, `ORD-1001`, `order 1001`, `1001`, `#1001` — all resolve to the same fixture. A genuinely unknown id still returns `None`.

The JSON-Schema spec for each tool — the shape the OpenAI Realtime model sees — is declared in `services/api/app/repo/openai_client.py::_tool_specs()` and passed to `client.realtime.client_secrets.create(...)` (the GA endpoint) by `mint_realtime_session`. That is the single source of truth for the schemas that go on the wire.

The Pydantic models in `services/api/app/types/tools.py` are a different, complementary layer: they validate the HTTP request/response for `POST /tools/invoke` (`ToolCallRequest`, `ToolCallResponse`), define the trace row written to `tools.jsonl` (`ToolEvent`), and carry the helpdesk fixture shapes (`CrmAccount`, `Order`, `Ticket`). They do not flow to OpenAI.

### Adding a new tool — checklist

Touch both files together, plus the adapter:

1. `repo/openai_client.py::_tool_specs()` — append a new function spec (name, description, JSON-Schema `parameters`).
2. `types/tools.py` — add the tool name to the `ToolName` literal so `ToolCallRequest`/`ToolEvent` will accept it.
3. `repo/helpdesk_adapter.py` — add the new method to the `CrmAdapter` Protocol and implement it on `MockCrmAdapter`.
4. `service/tool_executor.py::dispatch(...)` — add a branch that calls the adapter method.
5. Tests in `services/api/tests/` — cover the happy path and the unknown-name 400.

## Inputs
- `POST /tools/invoke` body: `ToolCallRequest` (`{ call_id, tool_name, args, tool_call_id }`)

## Outputs
- `POST /tools/invoke` → `ToolCallResponse` (`{ tool_call_id, ok, result, error, latency_ms }`)
- Side effects: appends a `ToolEvent` to the in-memory trace keyed by `call_id`; on end-of-call this is flushed to `calls/<call_id>/tools.jsonl`

## Flow
1. OpenAI model decides to invoke a tool; emits a `function_call` event on the Realtime data channel.
2. Browser intercepts the event, POSTs `{ call_id, tool_name, args, tool_call_id }` to `/tools/invoke`.
3. Runtime hands off to `tool_executor.dispatch(...)`.
4. Tool executor calls the corresponding `CrmAdapter` method (`account_lookup`, `order_status`, …).
5. Tool executor records a `ToolEvent` (`{ tool, args, result, ok, latency_ms, timestamp }`) into the in-flight trace.
6. Browser replays the response into the data channel as a `function_call_output` event so the model can continue speaking.

## Tool-Call Lifecycle States
- `requested` — event received from the data channel
- `dispatched` — adapter invoked
- `ok` — adapter returned a value
- `error` — adapter raised; error message is returned to the model so it can apologize / try a different approach
- `interrupted` — caller spoke over the model mid-tool-call; event still recorded with status `interrupted`

## Edge Cases
- Unknown tool name → 400 with `{ ok: false, error: "unknown_tool" }`; tool executor records the event with `ok=false`
- Args fail validation → 400 with field-level errors
- Adapter raises → response is `{ ok: false, error: <message> }` (not a 5xx — the model needs to see the error and respond naturally)
- Same `tool_call_id` POSTed twice → idempotent; second response is the cached first result
- Call has ended before tool result arrives → result still recorded to the trace if the bundle hasn't been finalized

## Verification
- Current automated coverage: structural containment tests (`services/api/tests/test_structure.py`) and the `/calls` route-validation suite. Dispatch-level and adapter-level tests (account_lookup hit + miss, order_status hit + miss, create_ticket success, escalate, unknown tool 400, adapter exception, idempotent tool_call_id) are not yet in the suite — see `docs/exec-plans/tech-debt-tracker.md`.
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations, structural tests confirm `openai`/`boto3` containment

## Extension Point: Real CRM Adapters

`CrmAdapter` is a `typing.Protocol`. To add a real Zendesk adapter:

1. Add `app/repo/zendesk_adapter.py` with a class that implements every `CrmAdapter` method.
2. Add `ZENDESK_SUBDOMAIN` / `ZENDESK_API_TOKEN` to `Settings`.
3. Switch impls behind a config flag in `tool_executor.py::_get_adapter()`.

Do not import the Zendesk SDK from the service layer; the structural test will fail.

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Realtime Voice](realtime-voice.md)
- [Call Bundles](call-bundles.md)
