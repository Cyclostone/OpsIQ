"""Case persistence — SQLite-backed store for triage cases."""

from __future__ import annotations

import json
from datetime import datetime

from app.storage.db import get_sqlite
from app.models.schemas import TriageCase, CaseStatus, Severity, Confidence


def save_case(case: TriageCase) -> TriageCase:
    """Insert or replace a triage case."""
    conn = get_sqlite()
    conn.execute(
        """INSERT OR REPLACE INTO cases
           (case_id, run_id, title, anomaly_type, severity, confidence,
            estimated_impact, evidence, affected_entities, recommended_action,
            status, created_at, sentiment_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            case.case_id,
            case.run_id,
            case.title,
            case.anomaly_type,
            case.severity.value,
            case.confidence.value,
            case.estimated_impact,
            json.dumps(case.evidence),
            json.dumps(case.affected_entities),
            case.recommended_action,
            case.status.value,
            case.created_at.isoformat(),
            json.dumps(case.sentiment_score) if case.sentiment_score else None,
        ),
    )
    conn.commit()
    return case


def save_cases(cases: list[TriageCase]) -> list[TriageCase]:
    """Bulk insert/replace cases."""
    for c in cases:
        save_case(c)
    return cases


def get_all_cases() -> list[TriageCase]:
    """Return all cases, newest first."""
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    return [_row_to_case(r) for r in rows]


def get_cases_by_run(run_id: str) -> list[TriageCase]:
    """Return cases for a specific run."""
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT * FROM cases WHERE run_id = ? ORDER BY estimated_impact DESC",
        (run_id,),
    ).fetchall()
    return [_row_to_case(r) for r in rows]


def get_case(case_id: str) -> TriageCase | None:
    """Return a single case by ID."""
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return _row_to_case(row) if row else None


def update_case_status(case_id: str, status: CaseStatus) -> TriageCase | None:
    """Update the status of a case."""
    conn = get_sqlite()
    conn.execute(
        "UPDATE cases SET status = ? WHERE case_id = ?",
        (status.value, case_id),
    )
    conn.commit()
    return get_case(case_id)


def get_open_cases() -> list[TriageCase]:
    """Return all open cases, sorted by impact descending."""
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT * FROM cases WHERE status = 'open' ORDER BY estimated_impact DESC"
    ).fetchall()
    return [_row_to_case(r) for r in rows]


def clear_cases() -> None:
    """Delete all cases (used by demo reset)."""
    conn = get_sqlite()
    conn.execute("DELETE FROM cases")
    conn.commit()


def _row_to_case(row) -> TriageCase:
    sentiment = None
    try:
        raw = row["sentiment_score"]
        if raw:
            sentiment = json.loads(raw)
    except (KeyError, json.JSONDecodeError, TypeError):
        sentiment = None

    return TriageCase(
        case_id=row["case_id"],
        run_id=row["run_id"],
        title=row["title"],
        anomaly_type=row["anomaly_type"],
        severity=Severity(row["severity"]),
        confidence=Confidence(row["confidence"]),
        estimated_impact=row["estimated_impact"],
        evidence=json.loads(row["evidence"]),
        affected_entities=json.loads(row["affected_entities"]),
        recommended_action=row["recommended_action"],
        status=CaseStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        sentiment_score=sentiment,
    )
