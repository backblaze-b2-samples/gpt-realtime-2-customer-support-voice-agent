from datetime import datetime

from pydantic import BaseModel, Field


class IceServer(BaseModel):
    urls: list[str]
    username: str | None = None
    credential: str | None = None


class RealtimeSessionToken(BaseModel):
    """Ephemeral token returned to the browser for a single Realtime session.

    The browser uses `client_secret` as a bearer token when negotiating the
    WebRTC connection directly with OpenAI. The token is short-lived; if
    `expires_at` passes before negotiation finishes, the client should request
    a fresh one rather than retry with the stale value.
    """

    session_id: str
    client_secret: str
    model: str
    expires_at: datetime
    ice_servers: list[IceServer] = Field(default_factory=list)


class RealtimeSessionRequest(BaseModel):
    """Body of POST /realtime/session.

    Empty in v1 — the server picks the model, voice, and tool set. Future
    flags (language, voice override, custom tool subset) plug in here.
    """

    pass
