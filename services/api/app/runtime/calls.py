import logging
import re

from fastapi import APIRouter, HTTPException

from app.service.call_orchestrator import (
    InvalidCallAudioError,
    audio_url,
    call_volume_activity,
    finalize_call,
    get_call_detail,
    get_call_stats,
    list_calls,
    remove_call,
)
from app.types import (
    Call,
    CallDetail,
    CallFinalizeRequest,
    CallStats,
    DailyCallCount,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# call_ids are ULIDs minted browser-side. Allow Crockford base32 charset.
_CALL_ID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$", re.IGNORECASE)


def _validate_call_id(call_id: str) -> None:
    if not _CALL_ID_RE.match(call_id):
        raise HTTPException(status_code=400, detail="Invalid call_id")


@router.post("/calls", response_model=Call)
async def finalize_call_endpoint(request: CallFinalizeRequest):
    _validate_call_id(request.call_id)
    try:
        call = finalize_call(request)
    except InvalidCallAudioError as exc:
        logger.warning("Invalid finalize payload for call_id=%s: %s", request.call_id, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except RuntimeError as exc:
        logger.error("Bundle write failed for call_id=%s: %s", request.call_id, exc)
        raise HTTPException(status_code=502, detail="Failed to persist call bundle") from None
    logger.info(
        "Call finalized: call_id=%s duration=%.1fs tools=%d deflected=%s",
        call.call_id,
        call.duration_seconds,
        call.tool_count,
        call.deflected,
    )
    return call


@router.get("/calls", response_model=list[Call])
async def list_calls_endpoint(limit: int = 100):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")
    return list_calls(limit=limit)


@router.get("/calls/stats", response_model=CallStats)
async def call_stats_endpoint():
    return get_call_stats()


@router.get("/calls/stats/activity", response_model=list[DailyCallCount])
async def call_activity_endpoint(days: int = 7):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 90")
    return call_volume_activity(days=days)


@router.get("/calls/{call_id}/audio")
async def call_audio_endpoint(call_id: str):
    _validate_call_id(call_id)
    try:
        url = audio_url(call_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return {"url": url}


@router.get("/calls/{call_id}", response_model=CallDetail)
async def get_call_endpoint(call_id: str):
    _validate_call_id(call_id)
    detail = get_call_detail(call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return detail


@router.delete("/calls/{call_id}")
async def delete_call_endpoint(call_id: str):
    _validate_call_id(call_id)
    try:
        removed = remove_call(call_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    logger.info("Call deleted: call_id=%s keys_removed=%d", call_id, removed)
    return {"deleted": True, "call_id": call_id, "keys_removed": removed}
