"""Trace persistence — SQLite-backed store for autonomous run traces / observability."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.storage.db import get_sqlite
from app.models.schemas import TraceRecord


def save_trace(trace: TraceRecord) -> TraceRecord:
    """Insert or replace a trace record."""
    conn = get_sqlite()
    conn.execute(
        """INSERT OR REPLACE INTO traces
           (run_id, timestamp, trigger_source, steps, tools_called,
            cases_generated, actions_created, eval_summary, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trace.run_id,
            trace.timestamp.isoformat(),
            trace.trigger_source,
            json.dumps(trace.steps),
            json.dumps(trace.tools_called),
            trace.cases_generated,
            trace.actions_created,
            json.dumps(trace.eval_summary) if trace.eval_summary else "{}",
            trace.duration_ms,
        ),
    )
    conn.commit()
    return trace


def get_latest_trace() -> TraceRecord | None:
    """Return the most recent trace."""
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM traces ORDER BY timestamp DESC LIMIT 1").fetchone()
    return _row_to_trace(row) if row else None


def get_all_traces() -> list[TraceRecord]:
    """Return all traces, newest first."""
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM traces ORDER BY timestamp DESC").fetchall()
    return [_row_to_trace(r) for r in rows]


def get_trace_by_run(run_id: str) -> TraceRecord | None:
    """Return trace for a specific run."""
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM traces WHERE run_id = ?", (run_id,)).fetchone()
    return _row_to_trace(row) if row else None


def clear_traces() -> None:
    """Delete all traces (used by demo reset)."""
    conn = get_sqlite()
    conn.execute("DELETE FROM traces")
    conn.commit()


def _row_to_trace(row) -> TraceRecord:
    return TraceRecord(
        run_id=row["run_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        trigger_source=row["trigger_source"],
        steps=json.loads(row["steps"]),
        tools_called=json.loads(row["tools_called"]),
        cases_generated=row["cases_generated"],
        actions_created=row["actions_created"],
        eval_summary=json.loads(row["eval_summary"]) if row["eval_summary"] else None,
        duration_ms=row["duration_ms"],
    )
