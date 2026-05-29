from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.types.tools import ToolEvent


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
    audio_base64: str
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
