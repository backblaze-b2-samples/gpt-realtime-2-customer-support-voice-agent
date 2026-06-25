"""Assemble and persist per-call bundles.

A "bundle" is the set of objects under `calls/<call_id>/`:
  audio.wav, transcript.jsonl, tools.jsonl, summary.md, manifest.json.

`manifest.json` is written LAST and is the durability signal for
completeness. See docs/features/call-bundles.md.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

from app.repo import (
    ARTIFACT_AUDIO,
    ARTIFACT_MANIFEST,
    ARTIFACT_SUMMARY,
    ARTIFACT_TOOLS,
    ARTIFACT_TRANSCRIPT,
    delete_call,
    generate_summary,
    get_bundle_artifact,
    get_call_manifest,
    get_presigned_audio_url,
    jsonl_dumps,
    list_call_ids,
    put_call_artifact,
)
from app.service.call_audio import decode_call_audio_base64
from app.types import (
    Call,
    CallDetail,
    CallFinalizeRequest,
    CallManifest,
    CallStats,
    DailyCallCount,
    ToolEvent,
    TranscriptTurn,
)

logger = logging.getLogger(__name__)

MAX_PUT_RETRIES = 3
RETRY_BASE_DELAY = 0.5  # seconds


def _put_with_retry(call_id: str, artifact: str, body: bytes, ct: str) -> None:
    for attempt in range(1, MAX_PUT_RETRIES + 1):
        try:
            put_call_artifact(call_id, artifact, body, ct)
            return
        except RuntimeError:
            if attempt == MAX_PUT_RETRIES:
                logger.error(
                    "Failed to write %s for call %s after %d attempts",
                    artifact,
                    call_id,
                    MAX_PUT_RETRIES,
                )
                raise
            time.sleep(RETRY_BASE_DELAY * attempt)


def _summary_line(summary: str) -> str:
    """Pick the first non-heading, non-empty line for the row preview."""
    for raw in summary.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            return line[:200]
    return summary.strip()[:200] or "(no summary)"


def finalize_call(request: CallFinalizeRequest, audio_bytes: bytes | None = None) -> Call:
    """Persist a complete call bundle to B2. Returns the summary Call row."""
    duration = (request.ended_at - request.started_at).total_seconds()
    if audio_bytes is None:
        audio_bytes = decode_call_audio_base64(request.audio_base64)
    tickets_created = sum(1 for t in request.tools if t.tool == "create_ticket" and t.ok)
    deflected = tickets_created == 0 and bool(request.transcript)

    # 1. audio.wav
    _put_with_retry(request.call_id, ARTIFACT_AUDIO, audio_bytes, "audio/wav")

    # 2. transcript.jsonl
    transcript_bytes = jsonl_dumps([turn.model_dump(mode="json") for turn in request.transcript])
    _put_with_retry(
        request.call_id, ARTIFACT_TRANSCRIPT, transcript_bytes, "application/jsonl"
    )

    # 3. tools.jsonl
    tools_bytes = jsonl_dumps([t.model_dump(mode="json") for t in request.tools])
    _put_with_retry(request.call_id, ARTIFACT_TOOLS, tools_bytes, "application/jsonl")

    # 4. summary.md (best-effort — repo guarantees a placeholder on failure)
    summary_text = generate_summary(request.transcript, request.tools)
    _put_with_retry(
        request.call_id, ARTIFACT_SUMMARY, summary_text.encode("utf-8"), "text/markdown"
    )

    # 5. manifest.json — written LAST
    manifest = CallManifest(
        call_id=request.call_id,
        started_at=request.started_at,
        ended_at=request.ended_at,
        duration_seconds=duration,
        tool_count=len(request.tools),
        deflected=deflected,
        audio_bytes=len(audio_bytes),
        model=request.model,
    )
    _put_with_retry(
        request.call_id,
        ARTIFACT_MANIFEST,
        manifest.model_dump_json().encode("utf-8"),
        "application/json",
    )

    return Call(
        call_id=request.call_id,
        started_at=request.started_at,
        ended_at=request.ended_at,
        duration_seconds=duration,
        tool_count=len(request.tools),
        deflected=deflected,
        summary_line=_summary_line(summary_text),
        complete=True,
    )


def list_calls(limit: int = 100) -> list[Call]:
    """List bundles under the `calls/` prefix, newest first."""
    ids = list_call_ids()
    rows: list[Call] = []
    for call_id in ids:
        manifest = get_call_manifest(call_id)
        if manifest is None:
            # Incomplete bundle (manifest not yet written). Still surface it
            # so operators can clean it up.
            rows.append(
                Call(
                    call_id=call_id,
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                    duration_seconds=0.0,
                    tool_count=0,
                    deflected=False,
                    summary_line="(incomplete bundle)",
                    complete=False,
                )
            )
            continue
        summary_raw = get_bundle_artifact(call_id, ARTIFACT_SUMMARY) or b""
        summary_line = _summary_line(summary_raw.decode("utf-8", errors="replace"))
        rows.append(
            Call(
                call_id=call_id,
                started_at=manifest.started_at,
                ended_at=manifest.ended_at,
                duration_seconds=manifest.duration_seconds,
                tool_count=manifest.tool_count,
                deflected=manifest.deflected,
                summary_line=summary_line,
                complete=True,
            )
        )
    rows.sort(key=lambda c: c.started_at, reverse=True)
    return rows[:limit]


def get_call_detail(call_id: str) -> CallDetail | None:
    manifest = get_call_manifest(call_id)
    if manifest is None:
        return None
    transcript = _read_jsonl(call_id, ARTIFACT_TRANSCRIPT, TranscriptTurn)
    tools = _read_jsonl(call_id, ARTIFACT_TOOLS, ToolEvent)
    summary_raw = get_bundle_artifact(call_id, ARTIFACT_SUMMARY) or b""
    return CallDetail(
        manifest=manifest,
        transcript=transcript,
        tools=tools,
        summary_markdown=summary_raw.decode("utf-8", errors="replace"),
    )


def _read_jsonl(call_id: str, artifact: str, model):
    raw = get_bundle_artifact(call_id, artifact)
    if not raw:
        return []
    out = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(model.model_validate_json(line))
    return out


def audio_url(call_id: str) -> str:
    return get_presigned_audio_url(call_id)


def remove_call(call_id: str) -> int:
    return delete_call(call_id)


def get_call_stats() -> CallStats:
    """Aggregate stats for the dashboard."""
    calls = list_calls(limit=1000)
    complete = [c for c in calls if c.complete]
    today = datetime.now(UTC).date()
    week_ago = today - timedelta(days=6)
    calls_today = sum(1 for c in complete if c.started_at.date() == today)
    calls_this_week = sum(1 for c in complete if c.started_at.date() >= week_ago)
    avg_duration = (
        sum(c.duration_seconds for c in complete) / len(complete) if complete else 0.0
    )
    tool_counts: Counter[str] = Counter()
    tickets_created = 0
    for c in complete:
        detail = get_call_detail(c.call_id)
        if not detail:
            continue
        for t in detail.tools:
            tool_counts[t.tool] += 1
            if t.tool == "create_ticket" and t.ok:
                tickets_created += 1
    total_tool_calls = sum(tool_counts.values())
    deflection_rate = (
        (len(complete) - sum(1 for c in complete if not c.deflected)) / len(complete)
        if complete
        else 0.0
    )
    return CallStats(
        calls_today=calls_today,
        calls_this_week=calls_this_week,
        avg_duration_seconds=avg_duration,
        total_tool_calls=total_tool_calls,
        tickets_created=tickets_created,
        deflection_rate=deflection_rate,
        tool_breakdown=dict(tool_counts),
    )


def call_volume_activity(days: int = 7) -> list[DailyCallCount]:
    today = datetime.now(UTC).date()
    cutoff = today - timedelta(days=days - 1)
    counts: dict[str, int] = {}
    for c in list_calls(limit=1000):
        d = c.started_at.date()
        if d >= cutoff and c.complete:
            counts[d.isoformat()] = counts.get(d.isoformat(), 0) + 1
    return [
        DailyCallCount(
            date=(cutoff + timedelta(days=i)).isoformat(),
            calls=counts.get((cutoff + timedelta(days=i)).isoformat(), 0),
        )
        for i in range(days)
    ]
