"""Shared fixtures for OpsIQ test suite."""

import os
import sys
import sqlite3
import pytest

# Ensure the project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch, tmp_path):
    """Set safe environment defaults so tests never hit real APIs unless opted in."""
    # Use a temp SQLite DB for each test
    db_path = str(tmp_path / "test_opsiq.db")
    monkeypatch.setenv("OPSIQ_TEST_DB", db_path)


@pytest.fixture()
def sqlite_conn(tmp_path):
    """Return a fresh SQLite connection with the OpsIQ schema."""
    db_path = str(tmp_path / "opsiq_test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
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
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id  TEXT PRIMARY KEY,
            target_type  TEXT NOT NULL,
            target_id    TEXT NOT NULL,
            feedback_type TEXT NOT NULL,
            comment      TEXT DEFAULT '',
            timestamp    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_scores (
            eval_id     TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL,
            actionability INTEGER DEFAULT 3,
            correctness   INTEGER DEFAULT 3,
            specificity   INTEGER DEFAULT 3,
            calibration_note TEXT DEFAULT '',
            total_cases  INTEGER DEFAULT 0,
            false_positive_count INTEGER DEFAULT 0,
            timestamp    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            memory_id   TEXT PRIMARY KEY,
            key         TEXT UNIQUE NOT NULL,
            value       TEXT NOT NULL,
            reason      TEXT DEFAULT '',
            source      TEXT DEFAULT '',
            updated_at  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            run_id      TEXT PRIMARY KEY,
            timestamp   TEXT NOT NULL,
            trigger_source TEXT DEFAULT '',
            steps       TEXT DEFAULT '[]',
            tools_called TEXT DEFAULT '[]',
            cases_generated INTEGER DEFAULT 0,
            actions_created INTEGER DEFAULT 0,
            eval_summary TEXT DEFAULT NULL,
            duration_ms INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn
