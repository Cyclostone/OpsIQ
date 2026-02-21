"""Shared SQLite connection and table initialization for OpsIQ persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import STORAGE_DIR

DB_PATH = STORAGE_DIR / "opsiq.db"

_conn: sqlite3.Connection | None = None


def get_sqlite() -> sqlite3.Connection:
    """Return the singleton SQLite connection, creating tables if needed."""
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _create_tables(_conn)
    return _conn


def reset_sqlite() -> None:
    """Drop and recreate all tables (used by demo reset)."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
    if DB_PATH.exists():
        DB_PATH.unlink()


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id   TEXT NOT NULL,
            feedback_type TEXT NOT NULL,
            comment     TEXT DEFAULT '',
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS evals (
            eval_id     TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL,
            actionability INTEGER DEFAULT 3,
            correctness   INTEGER DEFAULT 3,
            specificity   INTEGER DEFAULT 3,
            calibration_note TEXT DEFAULT '',
            total_cases  INTEGER DEFAULT 0,
            false_positive_count INTEGER DEFAULT 0,
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory (
            memory_id   TEXT PRIMARY KEY,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            reason      TEXT DEFAULT '',
            source      TEXT DEFAULT '',
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS traces (
            run_id      TEXT PRIMARY KEY,
            timestamp   TEXT NOT NULL,
            trigger_source TEXT DEFAULT '',
            steps       TEXT DEFAULT '[]',
            tools_called TEXT DEFAULT '[]',
            cases_generated INTEGER DEFAULT 0,
            actions_created INTEGER DEFAULT 0,
            eval_summary TEXT DEFAULT '{}',
            duration_ms INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS cases (
            case_id     TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL,
            title       TEXT NOT NULL,
            anomaly_type TEXT NOT NULL,
            severity    TEXT NOT NULL,
            confidence  TEXT NOT NULL,
            estimated_impact REAL DEFAULT 0,
            evidence    TEXT DEFAULT '[]',
            affected_entities TEXT DEFAULT '{}',
            recommended_action TEXT DEFAULT '',
            status      TEXT DEFAULT 'open',
            created_at  TEXT NOT NULL,
            sentiment_score TEXT DEFAULT NULL
        );
    """)
    conn.commit()
