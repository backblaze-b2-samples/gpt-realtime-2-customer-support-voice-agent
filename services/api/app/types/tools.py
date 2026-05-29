from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# --- Helpdesk fixtures ---


class CrmAccount(BaseModel):
    id: str
    name: str
    email: str
    tier: Literal["free", "pro", "enterprise"]
    contact_phone: str | None = None


class OrderItem(BaseModel):
    sku: str
    name: str
    qty: int


class Order(BaseModel):
    id: str
    account_id: str
    status: Literal["pending", "shipped", "delivered", "cancelled", "returned"]
    placed_at: datetime
    eta: datetime | None = None
    items: list[OrderItem] = Field(default_factory=list)


class Ticket(BaseModel):
    id: str
    account_id: str
    subject: str
    body: str
    status: Literal["open", "in_progress", "resolved", "escalated"] = "open"
    created_at: datetime


# --- Tool call wire shapes ---


ToolName = Literal["account_lookup", "order_status", "create_ticket", "escalate"]


class ToolCallRequest(BaseModel):
    """Browser → /tools/invoke. Mirrors the OpenAI Realtime function_call event."""

    call_id: str
    tool_call_id: str
    tool_name: ToolName
    args: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    """/tools/invoke → browser. Browser replays this back into the data channel."""

    tool_call_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float


class ToolEvent(BaseModel):
    """One entry in `tools.jsonl`. Captures everything needed to audit a tool call."""

    tool_call_id: str
    tool: ToolName
    args: dict[str, Any]
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float
    timestamp: datetime
    status: Literal["ok", "error", "interrupted"] = "ok"
