"""B2 access for per-call bundles.

Kept in its own module so `b2_client.py` stays focused on the generic
file-level operations the starter kit ships with. Both modules share the
same boto3 client via `b2_client.get_s3_client()`.
"""

import io
import json
import logging
from urllib.parse import quote

from botocore.exceptions import ClientError

from app.config import settings
from app.repo.b2_client import get_s3_client
from app.types import CallManifest

logger = logging.getLogger(__name__)

CALLS_PREFIX = "calls/"

# Bundle artifact names (relative to `calls/<call_id>/`). Order matters:
# manifest.json is written LAST so its presence is the durability signal
# that the bundle is complete. See docs/features/call-bundles.md.
ARTIFACT_AUDIO = "audio.wav"
ARTIFACT_TRANSCRIPT = "transcript.jsonl"
ARTIFACT_TOOLS = "tools.jsonl"
ARTIFACT_SUMMARY = "summary.md"
ARTIFACT_MANIFEST = "manifest.json"


def _bundle_key(call_id: str, artifact: str) -> str:
    return f"{CALLS_PREFIX}{call_id}/{artifact}"


def put_call_artifact(
    call_id: str, artifact: str, body: bytes, content_type: str
) -> None:
    """Write a single artifact under `calls/<call_id>/`.

    Raises RuntimeError on S3 failure. The orchestrator wraps this in a
    retry loop; this layer is intentionally dumb about retries.
    """
    client = get_s3_client()
    key = _bundle_key(call_id, artifact)
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=io.BytesIO(body),
            ContentType=content_type,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 PutObject failed for '{key}': {e}") from e


def get_object_bytes(key: str) -> bytes | None:
    """Fetch the raw bytes of an object. Returns None if the key is absent."""
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise RuntimeError(f"B2 GetObject failed for '{key}': {e}") from e
    return response["Body"].read()


def get_bundle_artifact(call_id: str, artifact: str) -> bytes | None:
    return get_object_bytes(_bundle_key(call_id, artifact))


def get_call_manifest(call_id: str) -> CallManifest | None:
    """Read and parse `calls/<id>/manifest.json`. Returns None if absent."""
    raw = get_bundle_artifact(call_id, ARTIFACT_MANIFEST)
    if raw is None:
        return None
    return CallManifest.model_validate_json(raw)


def list_call_ids() -> list[str]:
    """Return the set of call_ids that have any object under their prefix.

    A call_id is "complete" iff `manifest.json` exists; this function
    returns *all* ids (complete and incomplete) so the orchestrator can
    decide how to render incomplete bundles.
    """
    client = get_s3_client()
    ids: set[str] = set()
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": CALLS_PREFIX,
        "Delimiter": "/",
        "MaxKeys": 1000,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            for cp in response.get("CommonPrefixes", []) or []:
                # cp["Prefix"] looks like "calls/<id>/"
                prefix = cp.get("Prefix", "")
                trimmed = prefix.removeprefix(CALLS_PREFIX).rstrip("/")
                if trimmed:
                    ids.add(trimmed)
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list_calls failed: {e}") from e
    return sorted(ids)


def delete_call(call_id: str) -> int:
    """Delete every object under `calls/<call_id>/`. Returns the count removed."""
    client = get_s3_client()
    prefix = f"{CALLS_PREFIX}{call_id}/"
    keys: list[str] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": 1000,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                keys.append(obj["Key"])
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list-for-delete failed: {e}") from e

    for key in keys:
        try:
            client.delete_object(Bucket=settings.b2_bucket_name, Key=key)
        except ClientError as e:
            raise RuntimeError(f"B2 DeleteObject failed for '{key}': {e}") from e
    return len(keys)


def get_presigned_audio_url(call_id: str, expires_in: int = 600) -> str:
    """Generate a presigned, inline-disposition URL for `audio.wav`."""
    client = get_s3_client()
    key = _bundle_key(call_id, ARTIFACT_AUDIO)
    params = {
        "Bucket": settings.b2_bucket_name,
        "Key": key,
        # `inline` lets <audio> stream directly; the WAV bytes are not user-uploaded
        # arbitrary content (they're produced by the Realtime API), so this is safe.
        "ResponseContentDisposition": f'inline; filename="{quote(call_id, safe="")}.wav"',
        "ResponseContentType": "audio/wav",
    }
    try:
        return client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign audio failed for '{key}': {e}") from e


def jsonl_dumps(events: list[dict]) -> bytes:
    """Serialize a list of dicts as newline-delimited JSON for `.jsonl` artifacts."""
    return ("\n".join(json.dumps(e, default=str) for e in events) + "\n").encode("utf-8")
