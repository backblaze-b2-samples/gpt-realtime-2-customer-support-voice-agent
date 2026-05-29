"""Dispatch model-issued tool calls to the configured CrmAdapter.

This module owns the lifecycle of a single tool invocation:
  validate args -> call adapter -> record event -> return wire response.

It does NOT hold cross-call state. The orchestrator (`call_orchestrator.py`)
owns the in-flight trace per `call_id`.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from app.repo import default_adapter
from app.repo.helpdesk_adapter import CrmAdapter
from app.types import (
    ToolCallRequest,
    ToolCallResponse,
    ToolEvent,
)

logger = logging.getLogger(__name__)


class ToolDispatchError(Exception):
    """Raised when a tool call is structurally invalid (unknown tool, bad args)."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _get_adapter() -> CrmAdapter:
    """Adapter selection seam.

    Today: always the mock. To plug in a real CRM, add the impl in
    `app/repo/`, import it here, and switch behind a config flag. The
    service layer must never import a vendor SDK directly.
    """
    return default_adapter


def _invoke(
    adapter: CrmAdapter, tool: str, args: dict
) -> tuple[bool, dict | None, str | None]:
    try:
        if tool == "account_lookup":
            email = args.get("email")
            if not isinstance(email, str):
                raise ToolDispatchError("`email` must be a string")
            result = adapter.account_lookup(email)
            return True, (result.model_dump() if result else None), None
        if tool == "order_status":
            order_id = args.get("order_id")
            if not isinstance(order_id, str):
                raise ToolDispatchError("`order_id` must be a string")
            result = adapter.order_status(order_id)
            return True, (result.model_dump() if result else None), None
        if tool == "create_ticket":
            account_id = args.get("account_id")
            subject = args.get("subject")
            body = args.get("body")
            if not all(isinstance(v, str) for v in (account_id, subject, body)):
                raise ToolDispatchError(
                    "`account_id`, `subject`, `body` are required strings"
                )
            ticket = adapter.create_ticket(account_id, subject, body)
            return True, ticket.model_dump(), None
        if tool == "escalate":
            reason = args.get("reason")
            account_id = args.get("account_id")
            if not isinstance(reason, str):
                raise ToolDispatchError("`reason` must be a string")
            result = adapter.escalate(reason, account_id if isinstance(account_id, str) else None)
            return True, result, None
        raise ToolDispatchError(f"unknown tool: {tool}")
    except ToolDispatchError:
        raise
    except Exception as exc:
        # Adapter raised — we surface as ok=false so the model can apologise
        # and continue speaking naturally. NOT a 5xx.
        logger.warning("Tool '%s' adapter raised: %s", tool, exc)
        return False, None, str(exc)


def dispatch(request: ToolCallRequest) -> tuple[ToolCallResponse, ToolEvent]:
    """Execute one tool call. Returns (wire response, audit event).

    The runtime layer hands both back: the wire response is returned to
    the browser, which replays it into the Realtime data channel; the
    audit event is appended to the in-flight trace for the call.
    """
    adapter = _get_adapter()
    started = time.perf_counter()
    ok, result, error = _invoke(adapter, request.tool_name, request.args)
    latency_ms = (time.perf_counter() - started) * 1000

    response = ToolCallResponse(
        tool_call_id=request.tool_call_id,
        ok=ok,
        result=result,
        error=error,
        latency_ms=latency_ms,
    )
    event = ToolEvent(
        tool_call_id=request.tool_call_id,
        tool=request.tool_name,
        args=request.args,
        ok=ok,
        result=result,
        error=error,
        latency_ms=latency_ms,
        timestamp=datetime.now(UTC),
        status="ok" if ok else "error",
    )
    return response, event
