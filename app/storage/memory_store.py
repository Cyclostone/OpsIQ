"""Memory persistence — SQLite-backed store for self-improvement state.

Memory entries store learned thresholds, preferences, and patterns
that the triage/analyst agents use to improve over time.

Default memory is seeded on first access so the system has baseline values.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.storage.db import get_sqlite
from app.models.schemas import MemoryEntry

# Default memory entries — seeded on first access
_DEFAULTS: list[dict[str, Any]] = [
    {
        "key": "duplicate_refund_window_hours",
        "value": 2,
        "reason": "Initial default: flag refunds from same customer with same amount within 2 hours",
        "source": "system_default",
    },
    {
        "key": "underbilling_threshold",
        "value": 10.0,
        "reason": "Initial default: flag invoices where expected - billed > $10",
        "source": "system_default",
    },
    {
        "key": "refund_spike_multiplier",
        "value": 2.0,
        "reason": "Initial default: flag region/day refund count > 2x rolling average",
        "source": "system_default",
    },
    {
        "key": "manual_credit_threshold",
        "value": 200.0,
        "reason": "Initial default: flag manual credits above $200",
        "source": "system_default",
    },
    {
        "key": "explanation_style",
        "value": "detailed",
        "reason": "Initial default: provide detailed explanations in case summaries",
        "source": "system_default",
    },
    {
        "key": "false_positive_penalty",
        "value": 0.0,
        "reason": "Initial default: no confidence penalty for patterns with prior false positives",
        "source": "system_default",
    },
]


def _seed_defaults_if_empty() -> None:
    """Insert default memory entries if the table is empty."""
    conn = get_sqlite()
    count = conn.execute("SELECT count(*) FROM memory").fetchone()[0]
    if count == 0:
        now = datetime.utcnow().isoformat()
        for d in _DEFAULTS:
            mid = f"MEM-{uuid.uuid4().hex[:8]}"
            conn.execute(
                """INSERT INTO memory (memory_id, key, value, reason, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (mid, d["key"], json.dumps(d["value"]), d["reason"], d["source"], now),
            )
        conn.commit()


def get_memory(key: str) -> Any:
    """Get a memory value by key. Returns None if not found."""
    _seed_defaults_if_empty()
    conn = get_sqlite()
    row = conn.execute("SELECT value FROM memory WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return json.loads(row["value"])


def get_memory_entry(key: str) -> MemoryEntry | None:
    """Get full memory entry by key."""
    _seed_defaults_if_empty()
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM memory WHERE key = ?", (key,)).fetchone()
    return _row_to_entry(row) if row else None


def set_memory(key: str, value: Any, reason: str = "", source: str = "system") -> MemoryEntry:
    """Set or update a memory entry."""
    _seed_defaults_if_empty()
    conn = get_sqlite()
    now = datetime.utcnow().isoformat()

    existing = conn.execute("SELECT memory_id FROM memory WHERE key = ?", (key,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE memory SET value = ?, reason = ?, source = ?, updated_at = ? WHERE key = ?",
            (json.dumps(value), reason, source, now, key),
        )
        mid = existing["memory_id"]
    else:
        mid = f"MEM-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO memory (memory_id, key, value, reason, source, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mid, key, json.dumps(value), reason, source, now),
        )
    conn.commit()

    return MemoryEntry(
        memory_id=mid, key=key, value=value, reason=reason, source=source,
        updated_at=datetime.fromisoformat(now),
    )


def get_all_memory() -> list[MemoryEntry]:
    """Return all memory entries."""
    _seed_defaults_if_empty()
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM memory ORDER BY updated_at DESC").fetchall()
    return [_row_to_entry(r) for r in rows]


def clear_memory() -> None:
    """Delete all memory (used by demo reset). Defaults will re-seed on next access."""
    conn = get_sqlite()
    conn.execute("DELETE FROM memory")
    conn.commit()


def _row_to_entry(row) -> MemoryEntry:
    return MemoryEntry(
        memory_id=row["memory_id"],
        key=row["key"],
        value=json.loads(row["value"]),
        reason=row["reason"],
        source=row["source"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
