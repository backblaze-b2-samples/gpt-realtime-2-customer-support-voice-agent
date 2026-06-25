"""Smoke tests for /calls route input validation.

These tests don't touch B2 — they verify only the runtime-level
guards (call_id format, limit range, days range). End-to-end bundle
write tests are tracked in docs/exec-plans/tech-debt-tracker.md.
"""

import pytest


@pytest.mark.asyncio
async def test_invalid_call_id_rejected(client):
    response = await client.get("/calls/not-a-ulid")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_calls_list_limit_validation(client, monkeypatch):
    monkeypatch.setattr("app.runtime.calls.list_calls", lambda limit: [])
    response = await client.get("/calls?limit=0")
    assert response.status_code == 400
    response = await client.get("/calls?limit=1001")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_calls_activity_days_validation(client, monkeypatch):
    monkeypatch.setattr("app.runtime.calls.call_volume_activity", lambda days: [])
    response = await client.get("/calls/stats/activity?days=0")
    assert response.status_code == 400
    response = await client.get("/calls/stats/activity?days=91")
    assert response.status_code == 400


def test_call_id_alphabet_is_crockford():
    """Pin the call_id alphabet contract: Crockford base32 (excludes I/L/O/U).

    The browser mints the id (`useRealtimeCall.newCallId`); the server is the
    validator of record. A 26-char Crockford ULID must pass, but an id that
    is base36-legal yet Crockford-illegal (contains `L`) must be rejected —
    the exact drift that produced "Invalid call_id" on End Call in the demo.
    Tested against the validator directly so it stays hermetic (no B2).
    """
    from fastapi import HTTPException

    from app.runtime.calls import _validate_call_id

    # Valid Crockford base32 ULID — no raise.
    _validate_call_id("01KSTJVEA7T0QS8YQ694ZKVRSZ")

    # Same length, but contains `L` (legal in base36, illegal in Crockford).
    with pytest.raises(HTTPException) as exc:
        _validate_call_id("0000000000000L0000000000ZZ")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_finalize_validates_call_id(client):
    bad_body = {
        "call_id": "x",
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:00:00Z",
        "transcript": [],
        "tools": [],
        "audio_base64": "",
        "model": "gpt-realtime-2",
    }
    response = await client.post("/calls", json=bad_body)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_finalize_rejects_malformed_audio_base64(client):
    body = {
        "call_id": "01KSTJVEA7T0QS8YQ694ZKVRSZ",
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:00:00Z",
        "transcript": [],
        "tools": [],
        "audio_base64": "not-base64!",
        "model": "gpt-realtime-2",
    }

    response = await client.post("/calls", json=body)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid audio_base64"
