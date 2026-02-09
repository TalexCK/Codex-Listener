"""Parse Codex session JSONL files to extract summary information."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path.home() / ".codex" / "sessions"


@dataclass
class SessionSummary:
    """Extracted summary from a Codex session JSONL file."""

    session_id: str
    last_assistant_message: str | None = None
    total_tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    completed_at: str | None = None


def find_session_file(
    task_created_at: datetime,
    task_completed_at: datetime | None = None,
) -> Path | None:
    """Locate the Codex session JSONL file for a task by file mtime.

    Strategy: scan date directories (±1 day for timezone edge cases),
    find JSONL files whose mtime falls within the task's lifetime
    (created_at - 5s … completed_at + 5s).  Among candidates, pick
    the one whose mtime is closest to completed_at.

    The filename timestamp is in local time while task timestamps are
    UTC, so we avoid comparing them directly and rely on mtime instead.
    """
    end = task_completed_at or datetime.now(timezone.utc)
    window_start = (task_created_at - timedelta(seconds=5)).timestamp()
    window_end = (end + timedelta(seconds=5)).timestamp()

    logger.info(
        "find_session_file: created=%s completed=%s "
        "window=[%.0f, %.0f] sessions_dir=%s",
        task_created_at, task_completed_at,
        window_start, window_end, SESSIONS_DIR,
    )

    candidates: list[tuple[float, Path]] = []

    for delta in (0, -1, 1):
        dt = task_created_at + timedelta(days=delta)
        day_dir = SESSIONS_DIR / f"{dt.year}" / f"{dt.month:02d}" / f"{dt.day:02d}"
        if not day_dir.is_dir():
            logger.info("find_session_file: dir not found: %s", day_dir)
            continue
        files = list(day_dir.glob("rollout-*.jsonl"))
        logger.info(
            "find_session_file: scanning %s — %d files", day_dir, len(files),
        )
        for f in files:
            mtime = f.stat().st_mtime
            in_window = window_start <= mtime <= window_end
            logger.info(
                "find_session_file:   %s mtime=%.0f in_window=%s",
                f.name, mtime, in_window,
            )
            if in_window:
                candidates.append((mtime, f))

    if not candidates:
        logger.warning("find_session_file: no candidates found in window")
        return None

    # Pick the file closest to task completion (most likely the right one)
    target = end.timestamp()
    candidates.sort(key=lambda c: abs(c[0] - target))
    return candidates[0][1]


def parse_session(session_path: Path) -> SessionSummary | None:
    """Parse a session JSONL file and extract summary data.

    Reads line by line to handle large files without loading everything.
    """
    session_id: str | None = None
    last_assistant_msg: str | None = None
    token_usage: dict | None = None
    last_timestamp: str | None = None

    try:
        with open(session_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                last_timestamp = event.get("timestamp")
                etype = event.get("type")
                payload = event.get("payload", {})

                # Capture session ID from first event
                if etype == "session_meta" and session_id is None:
                    session_id = payload.get("id", "")

                # Track last assistant message
                if (
                    etype == "response_item"
                    and isinstance(payload, dict)
                    and payload.get("type") == "message"
                    and payload.get("role") == "assistant"
                ):
                    content = payload.get("content", [])
                    texts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "output_text"
                    ]
                    msg = "\n".join(texts).strip()
                    if msg:
                        last_assistant_msg = msg

                # Track last token count (cumulative)
                if (
                    etype == "event_msg"
                    and isinstance(payload, dict)
                    and payload.get("type") == "token_count"
                ):
                    info = payload.get("info")
                    if isinstance(info, dict):
                        usage = info.get("total_token_usage")
                        if isinstance(usage, dict):
                            token_usage = usage

    except OSError as e:
        logger.warning("Failed to read session file %s: %s", session_path, e)
        return None

    logger.info(
        "parse_session: session_id=%s has_assistant_msg=%s "
        "has_tokens=%s last_ts=%s",
        session_id,
        last_assistant_msg is not None and len(last_assistant_msg) > 0,
        token_usage is not None,
        last_timestamp,
    )

    if session_id is None:
        logger.warning("parse_session: no session_meta found in %s", session_path)
        return None

    summary = SessionSummary(
        session_id=session_id,
        last_assistant_message=last_assistant_msg,
        total_tokens=token_usage.get("total_tokens") if token_usage else None,
        input_tokens=token_usage.get("input_tokens") if token_usage else None,
        output_tokens=token_usage.get("output_tokens") if token_usage else None,
        reasoning_tokens=(
            token_usage.get("reasoning_output_tokens") if token_usage else None
        ),
        completed_at=last_timestamp,
    )
    logger.info(
        "parse_session: result — msg_len=%s total_tokens=%s",
        len(last_assistant_msg) if last_assistant_msg else 0,
        summary.total_tokens,
    )
    return summary


def get_session_summary(
    task_created_at: datetime,
    task_completed_at: datetime | None = None,
) -> SessionSummary | None:
    """Find session file and parse it. Returns None on failure."""
    path = find_session_file(task_created_at, task_completed_at)
    if path is None:
        logger.warning(
            "Session file not found for task created=%s",
            task_created_at,
        )
        return None

    logger.info("Parsing session file: %s", path)
    summary = parse_session(path)
    if summary is None:
        logger.warning("Failed to parse session file: %s", path)
    return summary
