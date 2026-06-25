from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.types.tools import ToolEvent

MAX_CALL_AUDIO_BYTES = 64 * 1024 * 1024
CALL_FINALIZE_BODY_OVERHEAD_BYTES = 40 * 1024 * 1024
CALL_FINALIZE_BODY_TOO_LARGE_DETAIL = "Call finalize request body too large"


def _max_call_audio_base64_chars() -> int:
    return ((MAX_CALL_AUDIO_BYTES + 2) // 3) * 4


def max_call_audio_base64_chars() -> int:
    return _max_call_audio_base64_chars()


MAX_CALL_AUDIO_BASE64_CHARS = _max_call_audio_base64_chars()
MAX_CALL_FINALIZE_BODY_BYTES = (
    MAX_CALL_AUDIO_BASE64_CHARS + CALL_FINALIZE_BODY_OVERHEAD_BYTES
)


def max_call_finalize_body_bytes() -> int:
    return MAX_CALL_FINALIZE_BODY_BYTES


class TranscriptTurn(BaseModel):
    """One conversational turn in `transcript.jsonl`."""

    speaker: Literal["caller", "agent"]
    text: str
    started_at: datetime
    ended_at: datetime


class CallManifest(BaseModel):
    """`manifest.json` payload. Written last; presence == bundle is complete."""

    call_id: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    tool_count: int
    deflected: bool
    audio_bytes: int
    model: str


class Call(BaseModel):
    """Summary row returned by GET /calls."""

    call_id: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    tool_count: int
    deflected: bool
    summary_line: str
    complete: bool


class CallDetail(BaseModel):
    """Detail payload for GET /calls/{id}: everything needed to render /calls/<id>."""

    manifest: CallManifest
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    tools: list[ToolEvent] = Field(default_factory=list)
    summary_markdown: str


class CallFinalizeRequest(BaseModel):
    """Body of POST /calls — what the browser sends at end-of-call."""

    call_id: str
    started_at: datetime
    ended_at: datetime
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    tools: list[ToolEvent] = Field(default_factory=list)
    audio_base64: str = Field(
        max_length=MAX_CALL_FINALIZE_BODY_BYTES,
        description=(
            "Base64-encoded WAV audio. Empty string is allowed when capture fails; "
            f"decoded audio is limited to {MAX_CALL_AUDIO_BYTES} bytes."
        )
    )
    model: str


class DailyCallCount(BaseModel):
    date: str
    calls: int


class CallStats(BaseModel):
    calls_today: int
    calls_this_week: int
    avg_duration_seconds: float
    total_tool_calls: int
    tickets_created: int
    deflection_rate: float
    tool_breakdown: dict[str, int] = Field(default_factory=dict)
