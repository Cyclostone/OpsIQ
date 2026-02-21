"""Tests for SQLite storage layer — cases, feedback, evals, memory, traces."""

import json
import pytest
from datetime import datetime
from unittest.mock import patch

from app.models.schemas import (
    TriageCase, Severity, Confidence, CaseStatus,
    FeedbackItem, FeedbackType,
    EvalScore, MemoryEntry, TraceRecord,
)


# ---------------------------------------------------------------------------
# Case Store
# ---------------------------------------------------------------------------

class TestCaseStore:
    def _make_case(self, case_id="CASE-TEST-001", sentiment=None):
        return TriageCase(
            case_id=case_id,
            run_id="RUN-test",
            title="Test Duplicate Refund",
            anomaly_type="duplicate_refund",
            severity=Severity.high,
            confidence=Confidence.high,
            estimated_impact=500.0,
            evidence=["Evidence line 1", "Evidence line 2"],
            affected_entities={"customer_id": "C001"},
            recommended_action="Investigate",
            status=CaseStatus.open,
            created_at=datetime.utcnow(),
            sentiment_score=sentiment,
        )

    def test_save_and_get_case(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, get_case
            case = self._make_case()
            save_case(case)
            loaded = get_case("CASE-TEST-001")
            assert loaded is not None
            assert loaded.case_id == "CASE-TEST-001"
            assert loaded.severity == Severity.high
            assert loaded.estimated_impact == 500.0
            assert loaded.evidence == ["Evidence line 1", "Evidence line 2"]
            assert loaded.affected_entities == {"customer_id": "C001"}

    def test_save_case_with_sentiment(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, get_case
            sentiment = {"overall_polarity": -0.5, "overall_risk_level": "high"}
            case = self._make_case(sentiment=sentiment)
            save_case(case)
            loaded = get_case("CASE-TEST-001")
            assert loaded.sentiment_score is not None
            assert loaded.sentiment_score["overall_polarity"] == -0.5
            assert loaded.sentiment_score["overall_risk_level"] == "high"

    def test_save_case_without_sentiment(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, get_case
            case = self._make_case(sentiment=None)
            save_case(case)
            loaded = get_case("CASE-TEST-001")
            assert loaded.sentiment_score is None

    def test_get_all_cases(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, get_all_cases
            save_case(self._make_case("CASE-A"))
            save_case(self._make_case("CASE-B"))
            cases = get_all_cases()
            assert len(cases) == 2

    def test_get_cases_by_run(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, get_cases_by_run
            save_case(self._make_case("CASE-A"))
            save_case(self._make_case("CASE-B"))
            cases = get_cases_by_run("RUN-test")
            assert len(cases) == 2
            cases_other = get_cases_by_run("RUN-nonexistent")
            assert len(cases_other) == 0

    def test_update_case_status(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, update_case_status, get_case
            save_case(self._make_case())
            updated = update_case_status("CASE-TEST-001", CaseStatus.approved)
            assert updated is not None
            assert updated.status == CaseStatus.approved

    def test_get_open_cases(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, update_case_status, get_open_cases
            save_case(self._make_case("CASE-A"))
            save_case(self._make_case("CASE-B"))
            update_case_status("CASE-A", CaseStatus.approved)
            open_cases = get_open_cases()
            assert len(open_cases) == 1
            assert open_cases[0].case_id == "CASE-B"

    def test_clear_cases(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_case, clear_cases, get_all_cases
            save_case(self._make_case("CASE-A"))
            save_case(self._make_case("CASE-B"))
            clear_cases()
            assert len(get_all_cases()) == 0

    def test_save_cases_bulk(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import save_cases, get_all_cases
            cases = [self._make_case(f"CASE-{i}") for i in range(5)]
            save_cases(cases)
            assert len(get_all_cases()) == 5

    def test_case_not_found(self, sqlite_conn):
        with patch("app.storage.case_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.case_store import get_case
            assert get_case("NONEXISTENT") is None


# ---------------------------------------------------------------------------
# Feedback Store
# ---------------------------------------------------------------------------

class TestFeedbackStore:
    def _make_feedback(self, target_id="CASE-001", fb_type=FeedbackType.approve):
        return FeedbackItem(
            target_type="case",
            target_id=target_id,
            feedback_type=fb_type,
            comment="Test feedback",
        )

    def test_save_and_get_feedback(self, sqlite_conn):
        with patch("app.storage.feedback_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.feedback_store import save_feedback, get_all_feedback
            fb = self._make_feedback()
            saved = save_feedback(fb)
            assert saved.feedback_id.startswith("FB-")
            all_fb = get_all_feedback()
            assert len(all_fb) == 1
            assert all_fb[0].target_id == "CASE-001"

    def test_get_feedback_for_target(self, sqlite_conn):
        with patch("app.storage.feedback_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.feedback_store import save_feedback, get_feedback_for_target
            save_feedback(self._make_feedback("CASE-001"))
            save_feedback(self._make_feedback("CASE-002"))
            fb = get_feedback_for_target("case", "CASE-001")
            assert len(fb) == 1

    def test_get_false_positive_case_ids(self, sqlite_conn):
        with patch("app.storage.feedback_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.feedback_store import save_feedback, get_false_positive_case_ids
            save_feedback(self._make_feedback("CASE-001", FeedbackType.false_positive))
            save_feedback(self._make_feedback("CASE-002", FeedbackType.approve))
            fp_ids = get_false_positive_case_ids()
            assert "CASE-001" in fp_ids
            assert "CASE-002" not in fp_ids

    def test_get_feedback_counts(self, sqlite_conn):
        with patch("app.storage.feedback_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.feedback_store import save_feedback, get_feedback_counts
            save_feedback(self._make_feedback("C1", FeedbackType.approve))
            save_feedback(self._make_feedback("C2", FeedbackType.approve))
            save_feedback(self._make_feedback("C3", FeedbackType.reject))
            counts = get_feedback_counts()
            assert counts.get("approve") == 2
            assert counts.get("reject") == 1

    def test_clear_feedback(self, sqlite_conn):
        with patch("app.storage.feedback_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.feedback_store import save_feedback, clear_feedback, get_all_feedback
            save_feedback(self._make_feedback())
            clear_feedback()
            assert len(get_all_feedback()) == 0


# ---------------------------------------------------------------------------
# Eval Store
# ---------------------------------------------------------------------------

class TestEvalStore:
    def _create_evals_table(self, conn):
        """Create the evals table with the correct name used by eval_store."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evals (
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
        conn.commit()

    def test_save_and_get_eval(self, sqlite_conn):
        self._create_evals_table(sqlite_conn)
        with patch("app.storage.eval_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.eval_store import save_eval, get_latest_eval, get_all_evals
            score = EvalScore(
                eval_id="EVAL-001",
                run_id="RUN-test",
                actionability=4,
                correctness=5,
                specificity=3,
                total_cases=6,
            )
            save_eval(score)
            latest = get_latest_eval()
            assert latest is not None
            assert latest.run_id == "RUN-test"
            assert latest.actionability == 4

            all_evals = get_all_evals()
            assert len(all_evals) == 1


# ---------------------------------------------------------------------------
# Memory Store
# ---------------------------------------------------------------------------

class TestMemoryStore:
    def test_get_set_memory(self, sqlite_conn):
        with patch("app.storage.memory_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.memory_store import set_memory, get_memory
            set_memory("test_key", 42, reason="test", source="unit_test")
            val = get_memory("test_key")
            assert val == 42

    def test_get_memory_default(self, sqlite_conn):
        with patch("app.storage.memory_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.memory_store import get_memory
            val = get_memory("nonexistent_key")
            assert val is None


# ---------------------------------------------------------------------------
# Trace Store
# ---------------------------------------------------------------------------

class TestTraceStore:
    def test_save_and_get_trace(self, sqlite_conn):
        with patch("app.storage.trace_store.get_sqlite", return_value=sqlite_conn):
            from app.storage.trace_store import save_trace, get_latest_trace, get_all_traces
            trace = TraceRecord(
                run_id="RUN-test",
                steps=["fetch_signals", "run_triage"],
                tools_called=["anomaly_tool"],
                cases_generated=5,
                duration_ms=1200,
            )
            save_trace(trace)
            latest = get_latest_trace()
            assert latest is not None
            assert latest.run_id == "RUN-test"
            assert latest.cases_generated == 5

            all_traces = get_all_traces()
            assert len(all_traces) == 1
