<!-- last_verified: 2026-03-10 -->
# Tech Debt Tracker

Known tech debt items. Agents update this when they discover or create tech debt.

| Description | Impact | Proposed Resolution | Priority | Status |
|---|---|---|---|---|
| `datetime.utcnow()` deprecated in Python 3.12+ | Naive datetimes, future breakage | Replace with `datetime.now(UTC)` in `repo/b2_client.py`, `service/metadata.py` | High | Resolved |
| S3 client recreated on every API call | Connection pool wasted, added latency | Cache client as module-level singleton via `lru_cache` | High | Resolved |
| `get_upload_stats()` pagination broken at 1000 objects | Stats silently wrong for large buckets | Check `IsTruncated` + use `ContinuationToken` | High | Resolved |
| `record_upload()` never called | `/metrics` always reports 0 uploads | Call from `runtime/upload.py` after successful upload | Medium | Resolved |
| Metrics counters not thread-safe | Race conditions under concurrent requests | Use `threading.Lock` (matches `service/files.py` pattern) | Medium | Resolved |
| `_humanize_bytes` duplicated in Python (repo + service) | DRY violation, drift risk | Extract to `app/types/formatting.py` shared util | Medium | Resolved |
| `humanizeBytes` duplicated in TypeScript | DRY violation | Extract to `lib/utils.ts` | Low | Open |
| `formatDate` duplicated in TypeScript | DRY violation | Extract to `lib/utils.ts` | Low | Open |
| No test harness for feature specs | No automated verification | Add pytest fixtures + test files per feature | Medium | Resolved (partial — tests added for upload, files, activity, errors) |
| No end-to-end call-bundle write tests | Bundle write order + retry semantics unverified | Add tests covering happy path (5 objects in order), summary-fail fallback, retry overwrites partial bundle, delete removes whole prefix | Medium | Open |
| No tool-dispatch / mock-adapter tests | Tool executor + `MockCrmAdapter` paths unverified | Add tests covering account_lookup hit + miss, order_status hit + miss, create_ticket success, escalate, unknown tool 400, adapter exception, idempotent tool_call_id | Medium | Open |
| No calls-explorer route tests | `/calls` list/detail/audio/delete paths unverified | Add `services/api/tests/test_calls_list.py`, `test_calls_detail.py`, `test_calls_delete.py` covering list happy path, list with incomplete bundle, detail happy path, audio presign happy path, delete success, delete of nonexistent id (404), B2 down (502) | Medium | Open |
| No dashboard stats tests | `/calls/stats` + recent-calls aggregation unverified | Add `services/api/tests/test_call_stats.py` and `test_recent_calls.py` covering stats with calls, stats with empty bucket, partial bundle excluded, API error fallback | Medium | Open |
