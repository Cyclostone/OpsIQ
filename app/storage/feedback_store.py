"""Feedback persistence — SQLite-backed store for user feedback on cases and analyst outputs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from app.storage.db import get_sqlite
from app.models.schemas import FeedbackItem, FeedbackType


def save_feedback(item: FeedbackItem) -> FeedbackItem:
    """Insert a feedback record. Auto-generates feedback_id if empty."""
    if not item.feedback_id:
        item.feedback_id = f"FB-{uuid.uuid4().hex[:8]}"

    conn = get_sqlite()
    conn.execute(
        """INSERT OR REPLACE INTO feedback
           (feedback_id, target_type, target_id, feedback_type, comment, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            item.feedback_id,
            item.target_type,
            item.target_id,
            item.feedback_type.value,
            item.comment,
            item.timestamp.isoformat(),
        ),
    )
    conn.commit()
    return item


def get_all_feedback() -> list[FeedbackItem]:
    """Return all feedback records, newest first."""
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT * FROM feedback ORDER BY timestamp DESC"
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def get_feedback_for_target(target_type: str, target_id: str) -> list[FeedbackItem]:
    """Return feedback for a specific target (case or analyst query)."""
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT * FROM feedback WHERE target_type = ? AND target_id = ? ORDER BY timestamp DESC",
        (target_type, target_id),
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def get_false_positive_case_ids() -> list[str]:
    """Return case_ids that have been marked as false positives."""
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT DISTINCT target_id FROM feedback WHERE target_type = 'case' AND feedback_type = 'false_positive'"
    ).fetchall()
    return [r["target_id"] for r in rows]


def get_feedback_counts() -> dict[str, int]:
    """Return counts by feedback_type."""
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT feedback_type, count(*) as cnt FROM feedback GROUP BY feedback_type"
    ).fetchall()
    return {r["feedback_type"]: r["cnt"] for r in rows}


def clear_feedback() -> None:
    """Delete all feedback (used by demo reset)."""
    conn = get_sqlite()
    conn.execute("DELETE FROM feedback")
    conn.commit()


def _row_to_item(row) -> FeedbackItem:
    return FeedbackItem(
        feedback_id=row["feedback_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        feedback_type=FeedbackType(row["feedback_type"]),
        comment=row["comment"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
    )
