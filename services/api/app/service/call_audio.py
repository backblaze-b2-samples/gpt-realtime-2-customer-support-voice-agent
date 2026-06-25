import base64
import binascii
import re

from app.types import calls as call_types

CALL_AUDIO_INVALID_DETAIL = "Invalid audio_base64"

_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


def _call_audio_too_large_detail() -> str:
    return (
        "audio_base64 decoded audio must be <= "
        f"{call_types.MAX_CALL_AUDIO_BYTES} bytes"
    )


class CallAudioValidationError(ValueError):
    """Raised when end-of-call audio fails the request contract."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class CallAudioInvalidError(CallAudioValidationError):
    """Raised when audio_base64 is not syntactically valid base64."""


class CallAudioTooLargeError(CallAudioValidationError):
    """Raised when audio_base64 would decode above the configured limit."""


def _has_base64_shape(audio_base64: str) -> bool:
    if len(audio_base64) % 4 != 0:
        return False
    return bool(_BASE64_RE.fullmatch(audio_base64))


def decode_call_audio_base64(audio_base64: str) -> bytes:
    """Validate and decode POST /calls audio without decoding obvious oversize input."""
    if not audio_base64:
        return b""
    if not _has_base64_shape(audio_base64):
        raise CallAudioInvalidError(CALL_AUDIO_INVALID_DETAIL)
    if len(audio_base64) > call_types.max_call_audio_base64_chars():
        raise CallAudioTooLargeError(_call_audio_too_large_detail())
    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CallAudioInvalidError(CALL_AUDIO_INVALID_DETAIL) from exc
    if len(audio_bytes) > call_types.MAX_CALL_AUDIO_BYTES:
        raise CallAudioTooLargeError(_call_audio_too_large_detail())
    return audio_bytes
