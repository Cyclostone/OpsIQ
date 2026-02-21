"""Evaluation persistence — SQLite-backed store for eval scores per run."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.storage.db import get_sqlite
from app.models.schemas import EvalScore


def save_eval(score: EvalScore) -> EvalScore:
    """Insert or replace an eval record."""
    if not score.eval_id:
        score.eval_id = f"EVAL-{uuid.uuid4().hex[:8]}"

    conn = get_sqlite()
    conn.execute(
        """INSERT OR REPLACE INTO evals
           (eval_id, run_id, actionability, correctness, specificity,
            calibration_note, total_cases, false_positive_count, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            score.eval_id,
            score.run_id,
            score.actionability,
            score.correctness,
            score.specificity,
            score.calibration_note,
            score.total_cases,
            score.false_positive_count,
            score.timestamp.isoformat(),
        ),
    )
    conn.commit()
    return score


def get_all_evals() -> list[EvalScore]:
    """Return all eval records, newest first."""
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM evals ORDER BY timestamp DESC").fetchall()
    return [_row_to_eval(r) for r in rows]


def get_latest_eval() -> EvalScore | None:
    """Return the most recent eval record."""
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM evals ORDER BY timestamp DESC LIMIT 1").fetchone()
    return _row_to_eval(row) if row else None


def get_eval_by_run(run_id: str) -> EvalScore | None:
    """Return eval for a specific run."""
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM evals WHERE run_id = ?", (run_id,)).fetchone()
    return _row_to_eval(row) if row else None


def clear_evals() -> None:
    """Delete all evals (used by demo reset)."""
    conn = get_sqlite()
    conn.execute("DELETE FROM evals")
    conn.commit()


def _row_to_eval(row) -> EvalScore:
    return EvalScore(
        eval_id=row["eval_id"],
        run_id=row["run_id"],
        actionability=row["actionability"],
        correctness=row["correctness"],
        specificity=row["specificity"],
        calibration_note=row["calibration_note"],
        total_cases=row["total_cases"],
        false_positive_count=row["false_positive_count"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
    )
