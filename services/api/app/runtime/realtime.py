import logging

from fastapi import APIRouter, HTTPException

from app.repo import mint_realtime_session
from app.types import RealtimeSessionToken

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/realtime/session", response_model=RealtimeSessionToken)
async def create_realtime_session():
    """Mint an ephemeral OpenAI Realtime session token.

    The browser uses the returned `client_secret` as a bearer credential
    when opening the WebRTC peer connection **directly to OpenAI**. This
    server never proxies audio bytes.
    """
    try:
        token = mint_realtime_session()
    except RuntimeError as exc:
        logger.warning("Realtime session mint failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return token
