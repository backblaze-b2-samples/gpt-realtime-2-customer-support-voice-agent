import base64
import binascii
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.types.tools import ToolEvent

MAX_CALL_AUDIO_BYTES = 64 * 1024 * 1024
CALL_AUDIO_INVALID_DETAIL = "Invalid audio_base64"


def _max_call_audio_base64_chars() -> int:
    return ((MAX_CALL_AUDIO_BYTES + 2) // 3) * 4


def _call_audio_too_large_detail() -> str:
    return f"audio_base64 decoded audio must be <= {MAX_CALL_AUDIO_BYTES} bytes"


class CallAudioValidationError(ValueError):
    """Raised when end-of-call audio fails the request contract."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class CallAudioInvalidError(CallAudioValidationError):
    """Raised when audio_base64 is not syntactically valid base64."""


class CallAudioTooLargeError(CallAudioValidationError):
    """Raised when audio_base64 would decode above the configured limit."""


def decode_call_audio_base64(audio_base64: str) -> bytes:
    """Validate and decode POST /calls audio without decoding obvious oversize input."""
    if not audio_base64:
        return b""
    if len(audio_base64) > _max_call_audio_base64_chars():
        raise CallAudioTooLargeError(_call_audio_too_large_detail())
    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CallAudioInvalidError(CALL_AUDIO_INVALID_DETAIL) from exc
    if len(audio_bytes) > MAX_CALL_AUDIO_BYTES:
        raise CallAudioTooLargeError(_call_audio_too_large_detail())
    return audio_bytes


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
