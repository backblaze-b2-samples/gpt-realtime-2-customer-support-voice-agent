"""Wraps the `openai` SDK for non-realtime calls.

Realtime sessions are negotiated by the browser directly with OpenAI
using an ephemeral session token; this module mints those tokens and
also handles the post-call summary generation (Chat Completions).

Per architectural invariant, this is the only module allowed to import
`openai`. Everything above this layer talks to it through plain Python
function signatures and returns Pydantic models.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import settings
from app.types import RealtimeSessionToken, ToolEvent, TranscriptTurn

logger = logging.getLogger(__name__)


def _tool_specs() -> list[dict[str, Any]]:
    """JSON-Schema specs for every tool the Realtime model can invoke.

    Kept here (the repo layer) because the OpenAI Realtime session
    config is the only place these are consumed. The service layer
    uses the canonical Pydantic models in `app/types/tools.py` for
    validation.
    """
    return [
        {
            "type": "function",
            "name": "account_lookup",
            "description": "Look up a customer account by email.",
            "parameters": {
                "type": "object",
                "properties": {"email": {"type": "string", "description": "Customer email address."}},
                "required": ["email"],
            },
        },
        {
            "type": "function",
            "name": "order_status",
            "description": "Get the status of an order by its ID.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
        {
            "type": "function",
            "name": "create_ticket",
            "description": "Create a support ticket on behalf of an account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["account_id", "subject", "body"],
            },
        },
        {
            "type": "function",
            "name": "escalate",
            "description": "Escalate the case to a human supervisor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "account_id": {"type": "string"},
                },
                "required": ["reason"],
            },
        },
    ]


# Voice for the agent's spoken responses. OpenAI recommends `marin` and
# `cedar` for best quality on the GA Realtime models.
_AGENT_VOICE = "marin"

# System instructions ("persona") prepended to the Realtime session. Kept
# here in the repo layer alongside `_tool_specs()` because the session
# config is the only place it is consumed. Written for voice: short turns,
# no markdown, confirm identifiers before acting, lean on tools over guesses.
_SUPPORT_AGENT_INSTRUCTIONS = (
    "You are a warm, efficient customer-support voice agent for an online "
    "retailer. You are speaking with a caller out loud, so keep replies short "
    "and conversational — one or two sentences — and never use markdown, "
    "bullet points, or emoji.\n\n"
    "Open the call by greeting the caller and asking how you can help. "
    "To look up an account, ask for and confirm the caller's email address. "
    "To check an order, ask for and confirm the order number. Repeat back the "
    "key detail you heard before calling a tool so the caller can correct you.\n\n"
    "Use your tools confidently rather than guessing: look up accounts and "
    "orders, create a support ticket when an issue needs follow-up, and "
    "escalate to a human when the caller is frustrated, asks for one, or you "
    "cannot resolve the request. If a lookup returns nothing, say so plainly "
    "and offer to create a ticket or escalate — do not invent account details, "
    "order statuses, prices, or policies. When you finish helping, briefly "
    "confirm what you did and ask if there is anything else."
)


def mint_realtime_session() -> RealtimeSessionToken:
    """Create an ephemeral OpenAI Realtime client secret and return it.

    Raises RuntimeError on OpenAI failure. The browser uses the returned
    `client_secret` as a bearer token when opening the WebRTC peer
    connection directly with OpenAI — the server never proxies audio.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("openai package not installed") from e

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        # GA Realtime API: ephemeral tokens are minted via
        # `client.realtime.client_secrets.create(...)` (POST
        # /v1/realtime/client_secrets). This replaced the removed beta
        # `client.beta.realtime.sessions.create(...)` (POST
        # /v1/realtime/sessions — now returns 404) and renamed the
        # `modalities` kwarg to `output_modalities`, nested under a
        # `session` object. Verified against openai==1.109.1.
        #
        # `output_modalities` accepts exactly one combination: ["text"] OR
        # ["audio"] — never both (the API rejects ["audio", "text"] with a
        # 400 invalid_value). For a voice agent we want ["audio"]; the text
        # transcript still arrives over the data channel via the
        # `response.audio_transcript.done` (agent) and
        # `conversation.item.input_audio_transcription.completed` (caller)
        # events, which are byproducts of the audio modality.
        secret = client.realtime.client_secrets.create(
            session={
                "type": "realtime",
                "model": settings.openai_realtime_model,
                "instructions": _SUPPORT_AGENT_INSTRUCTIONS,
                "tools": _tool_specs(),
                "output_modalities": ["audio"],
                "audio": {"output": {"voice": _AGENT_VOICE}},
            },
        )
    except Exception as e:
        logger.exception("OpenAI realtime session mint failed")
        raise RuntimeError(f"OpenAI realtime session failed: {e}") from e

    raw = secret.model_dump() if hasattr(secret, "model_dump") else dict(secret)
    client_secret = raw.get("value", "")
    # `expires_at` is a unix timestamp per the OpenAI docs.
    expires_unix = raw.get("expires_at")
    expires_at = (
        datetime.fromtimestamp(expires_unix, tz=UTC)
        if isinstance(expires_unix, (int, float))
        else datetime.now(UTC) + timedelta(minutes=1)
    )
    session_obj = raw.get("session")
    model = (
        session_obj.get("model", settings.openai_realtime_model)
        if isinstance(session_obj, dict)
        else settings.openai_realtime_model
    )
    # The GA client-secret response carries no session id and no ICE
    # servers: `session_id` is informational only (the browser needs just
    # `client_secret` + `model`), and the browser negotiates against
    # OpenAI's public WebRTC endpoint without STUN config. Both fields stay
    # on the model for API stability; they're left empty here.
    return RealtimeSessionToken(
        session_id="",
        client_secret=client_secret,
        model=model,
        expires_at=expires_at,
        ice_servers=[],
    )


def generate_summary(
    transcript: list[TranscriptTurn], tools: list[ToolEvent]
) -> str:
    """Generate a Markdown summary of a finished call.

    Returns the summary text. On failure, returns a placeholder string
    starting with `# Summary unavailable` so the bundle can still be
    completed with `manifest.json` (see docs/features/call-bundles.md).
    """
    try:
        from openai import OpenAI
    except ImportError:
        return "# Summary unavailable\n\nopenai package not installed."

    transcript_text = "\n".join(
        f"{turn.speaker}: {turn.text}" for turn in transcript
    )
    tool_text = "\n".join(
        f"- {t.tool}({json.dumps(t.args)}) -> ok={t.ok}"
        for t in tools
    ) or "(no tools invoked)"

    prompt = (
        "Summarize this customer support call. Output Markdown with three "
        "sections: '## Caller intent', '## What the agent did', "
        "'## Resolution'. Keep it under 200 words.\n\n"
        f"## Transcript\n{transcript_text}\n\n"
        f"## Tool calls\n{tool_text}\n"
    )

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.chat.completions.create(
            model=settings.openai_summary_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
    except Exception as e:
        logger.exception("OpenAI summary generation failed")
        return f"# Summary unavailable\n\n{e}"

    return response.choices[0].message.content or "# Summary unavailable\n\n(empty)"
