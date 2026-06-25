import logging
import re

from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse

from app.service.call_audio import (
    CallAudioTooLargeError,
    CallAudioValidationError,
    decode_call_audio_base64,
)
from app.service.call_orchestrator import (
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
from app.types import calls as call_types

logger = logging.getLogger(__name__)

router = APIRouter()

# call_ids are ULIDs minted browser-side. Allow Crockford base32 charset.
_CALL_ID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$", re.IGNORECASE)


def _validate_call_id(call_id: str) -> None:
    if not _CALL_ID_RE.match(call_id):
        raise HTTPException(status_code=400, detail="Invalid call_id")


def _audio_validation_status(exc: CallAudioValidationError) -> int:
    return 413 if isinstance(exc, CallAudioTooLargeError) else 400


class _BodyTooLargeError(Exception):
    pass


class CallFinalizeBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/calls"
        ):
            await self.app(scope, receive, send)
            return

        limit = call_types.max_call_finalize_body_bytes()
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        content_length = headers.get("content-length")
        try:
            content_length_too_large = (
                content_length is not None and int(content_length) > limit
            )
        except ValueError:
            content_length_too_large = False
        if content_length_too_large:
            response = JSONResponse(
                {"detail": call_types.CALL_FINALIZE_BODY_TOO_LARGE_DETAIL},
                status_code=413,
            )
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLargeError:
            response = JSONResponse(
                {"detail": call_types.CALL_FINALIZE_BODY_TOO_LARGE_DETAIL},
                status_code=413,
            )
            await response(scope, receive, send)


@router.post("/calls", response_model=Call)
async def finalize_call_endpoint(request: CallFinalizeRequest):
    _validate_call_id(request.call_id)
    try:
        audio_bytes = decode_call_audio_base64(request.audio_base64)
        call = finalize_call(request, audio_bytes=audio_bytes)
    except CallAudioTooLargeError as exc:
        logger.warning(
            "Call audio too large for call_id=%s; preserving bundle without audio: %s",
            request.call_id,
            exc.detail,
        )
        try:
            finalize_call(request, audio_bytes=b"")
        except RuntimeError as persist_exc:
            logger.error(
                "Bundle write failed for call_id=%s after audio limit: %s",
                request.call_id,
                persist_exc,
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to persist call bundle",
            ) from None
        raise HTTPException(status_code=413, detail=exc.detail) from None
    except CallAudioValidationError as exc:
        logger.warning(
            "Invalid finalize payload for call_id=%s: %s",
            request.call_id,
            exc.detail,
        )
        raise HTTPException(
            status_code=_audio_validation_status(exc),
            detail=exc.detail,
        ) from None
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
