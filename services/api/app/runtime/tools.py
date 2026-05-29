import logging

from fastapi import APIRouter, HTTPException

from app.service.tool_executor import ToolDispatchError, dispatch
from app.types import ToolCallRequest, ToolCallResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/tools/invoke", response_model=ToolCallResponse)
async def invoke_tool(request: ToolCallRequest):
    """Dispatch a Realtime-model-issued tool call.

    The browser forwards every `function_call` event from the OpenAI
    Realtime data channel to this endpoint, replays the response back
    into the channel as a `function_call_output`, and the model
    continues speaking.

    The audit event is currently returned to the caller for inclusion
    in the in-flight trace assembled client-side. The orchestrator
    persists the full trace at end-of-call.
    """
    try:
        response, _event = dispatch(request)
    except ToolDispatchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    logger.info(
        "Tool dispatched: call_id=%s tool=%s ok=%s latency_ms=%.1f",
        request.call_id,
        request.tool_name,
        response.ok,
        response.latency_ms,
    )
    return response
