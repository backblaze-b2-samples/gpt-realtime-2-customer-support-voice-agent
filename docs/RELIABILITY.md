<!-- last_verified: 2026-05-28 -->
# Reliability

Reliability expectations and practices for this project.

## Health Checks

- `GET /health` verifies B2 connectivity and returns `healthy` or `degraded`
- Health endpoint is always available, even when B2 is down

## Error Handling

- HTTP handlers return structured error responses with appropriate status codes
- External service failures (B2, OpenAI) are caught and surfaced as 500/503 responses
- No unhandled exceptions leak stack traces to clients

## Logging

- Structured JSON logging via Python stdlib
- Every request gets a `request_id` for tracing
- Log levels: ERROR for failures, WARNING for degraded state, INFO for requests

## Observability

- Request timing middleware logs duration for every request
- `/metrics` endpoint exposes basic Prometheus-format counters
- Tool-call success/failure and call-bundle write success/failure are tracked

## Call Bundle Write Semantics

A "call bundle" is the set of objects written under `calls/<call_id>/` at end-of-call: `audio.wav`, `transcript.jsonl`, `tools.jsonl`, `summary.md`, `manifest.json`. The orchestrator writes them in that order; `manifest.json` is written **last** so its presence is a durable signal that the bundle is complete.

Partial-failure semantics:

- If any individual `PutObject` fails, the orchestrator retries the operation up to three times with exponential backoff.
- If retries exhaust, the bundle is left in whatever partial state was reached and an ERROR log is emitted with the `call_id` and the failed key.
- The Calls explorer surfaces bundles that lack `manifest.json` as "incomplete" so operators can investigate or delete them.
- `DELETE /calls/{id}` deletes every object under the prefix, including partial bundles.

## Graceful Degradation

- File listing returns empty list (not error) when B2 has no objects
- Metadata extraction failures don't block upload (return partial metadata)
- If the OpenAI summary call fails post-call, the bundle is still written with `summary.md` containing an error notice — audio, transcript, and tools are preserved.
- Frontend shows skeleton states while loading, error states on failure

## Deployment

- Railway health checks on `/health`
- Zero-downtime deploys via rolling updates
- Environment-specific configuration via env vars (no config files in prod)
