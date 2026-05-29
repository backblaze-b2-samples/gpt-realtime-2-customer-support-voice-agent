"""Unit test for /realtime/session — mocks the OpenAI mint call."""

from datetime import UTC, datetime, timedelta

import pytest

from app.types import RealtimeSessionToken


class _FakeSecret:
    """Stand-in for the object returned by client_secrets.create()."""

    def __init__(self) -> None:
        self._raw = {
            "value": "ek_fake",
            "expires_at": int(datetime.now(UTC).timestamp()) + 60,
            "session": {"model": "gpt-realtime-2"},
        }

    def model_dump(self) -> dict:
        return self._raw


def _patch_fake_openai(monkeypatch) -> dict:
    """Patch openai.OpenAI with a fake that records the session payload.

    Returns a dict the test can inspect after calling
    mint_realtime_session() — `captured["session"]` holds the exact
    payload sent to OpenAI's client_secrets.create().
    """
    captured: dict = {}

    class _FakeClientSecrets:
        def create(self, *, session):
            captured["session"] = session
            return _FakeSecret()

    class _FakeRealtime:
        client_secrets = _FakeClientSecrets()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.realtime = _FakeRealtime()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)
    return captured


def test_mint_session_payload_uses_single_audio_modality(monkeypatch):
    """Guards the 400 bug: output_modalities must be exactly one
    supported combination — ['text'] OR ['audio'], never both. OpenAI
    rejects ['audio', 'text'] with invalid_value. For a voice agent we
    send ['audio']."""
    from app.repo.openai_client import mint_realtime_session

    captured = _patch_fake_openai(monkeypatch)
    token = mint_realtime_session()

    assert token.client_secret == "ek_fake"
    modalities = captured["session"]["output_modalities"]
    assert modalities in (["text"], ["audio"]), (
        f"output_modalities must be a single supported combination, got {modalities}"
    )
    assert modalities == ["audio"]


def test_mint_session_sets_persona_and_voice(monkeypatch):
    """The session must ship a support-agent persona and a configured
    voice, otherwise the live agent has no instructions and demos as a
    generic assistant."""
    from app.repo.openai_client import mint_realtime_session

    captured = _patch_fake_openai(monkeypatch)
    mint_realtime_session()
    session = captured["session"]

    instructions = session.get("instructions", "")
    assert isinstance(instructions, str) and len(instructions) > 50
    assert "support" in instructions.lower()
    # Voice nested under audio.output per the GA Realtime session schema.
    assert session["audio"]["output"]["voice"]


@pytest.mark.asyncio
async def test_mint_session_happy_path(client, monkeypatch):
    fake = RealtimeSessionToken(
        session_id="sess_fake",
        client_secret="ek_fake",
        model="gpt-realtime-2",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
        ice_servers=[],
    )
    # Patch where it is used. Both the runtime module and the repo
    # package re-export the function, so we patch the call site.
    monkeypatch.setattr(
        "app.runtime.realtime.mint_realtime_session",
        lambda: fake,
    )
    response = await client.post("/realtime/session")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "sess_fake"
    assert body["client_secret"] == "ek_fake"


@pytest.mark.asyncio
async def test_mint_session_upstream_failure(client, monkeypatch):
    def boom():
        raise RuntimeError("OpenAI is down")

    monkeypatch.setattr("app.runtime.realtime.mint_realtime_session", boom)
    response = await client.post("/realtime/session")
    assert response.status_code == 502
    assert "down" in response.json()["detail"]
