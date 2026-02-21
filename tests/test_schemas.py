"""Tests for Pydantic schemas and models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.schemas import (
    Severity, Confidence, CaseStatus, FeedbackType, AdapterMode,
    SignalEvent, TriageCase, AnalystQuery, AnalystResponse,
    FeedbackItem, EvalScore, MemoryEntry, TraceRecord,
    AutonomousRunResult, HealthResponse, ResetResponse,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_severity_values(self):
        assert Severity.low == "low"
        assert Severity.medium == "medium"
        assert Severity.high == "high"
        assert Severity.critical == "critical"

    def test_confidence_values(self):
        assert Confidence.low == "low"
        assert Confidence.medium == "medium"
        assert Confidence.high == "high"

    def test_case_status_values(self):
        assert CaseStatus.open == "open"
        assert CaseStatus.approved == "approved"
        assert CaseStatus.rejected == "rejected"
        assert CaseStatus.false_positive == "false_positive"

    def test_feedback_type_values(self):
        assert FeedbackType.approve == "approve"
        assert FeedbackType.reject == "reject"
        assert FeedbackType.false_positive == "false_positive"
        assert FeedbackType.useful == "useful"
        assert FeedbackType.not_useful == "not_useful"

    def test_adapter_mode_values(self):
        assert AdapterMode.mock == "mock"
        assert AdapterMode.real == "real"


# ---------------------------------------------------------------------------
# SignalEvent
# ---------------------------------------------------------------------------

class TestSignalEvent:
    def test_create_valid(self):
        s = SignalEvent(
            signal_id="SIG001",
            timestamp=datetime.utcnow(),
            signal_type="anomaly_alert",
            severity=Severity.high,
            source="datadog",
            related_entity="refunds",
        )
        assert s.signal_id == "SIG001"
        assert s.source == "datadog"
        assert s.payload == {}

    def test_with_payload(self):
        s = SignalEvent(
            signal_id="SIG002",
            timestamp=datetime.utcnow(),
            signal_type="metric_drift",
            severity=Severity.medium,
            source="lightdash",
            related_entity="invoices",
            payload={"metric": "monthly_revenue", "drift_pct": -16.1},
        )
        assert s.payload["drift_pct"] == -16.1

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            SignalEvent(signal_id="SIG003", timestamp=datetime.utcnow())


# ---------------------------------------------------------------------------
# TriageCase
# ---------------------------------------------------------------------------

class TestTriageCase:
    def test_create_minimal(self):
        c = TriageCase(
            case_id="CASE-DUP-001",
            run_id="RUN-abc",
            title="Duplicate Refund: C003",
            anomaly_type="duplicate_refund",
            severity=Severity.high,
            confidence=Confidence.high,
        )
        assert c.status == CaseStatus.open
        assert c.estimated_impact == 0.0
        assert c.sentiment_score is None

    def test_with_sentiment_score(self):
        sentiment = {"overall_polarity": -0.5, "overall_risk_level": "high"}
        c = TriageCase(
            case_id="CASE-DUP-002",
            run_id="RUN-abc",
            title="Test",
            anomaly_type="duplicate_refund",
            severity=Severity.high,
            confidence=Confidence.high,
            sentiment_score=sentiment,
        )
        assert c.sentiment_score["overall_polarity"] == -0.5

    def test_with_evidence_and_entities(self):
        c = TriageCase(
            case_id="CASE-UND-001",
            run_id="RUN-abc",
            title="Underbilling: Acme",
            anomaly_type="underbilling",
            severity=Severity.high,
            confidence=Confidence.high,
            estimated_impact=450.0,
            evidence=["Billed $100 but expected $550"],
            affected_entities={"customer_id": "C001", "invoice_id": "INV001"},
        )
        assert c.estimated_impact == 450.0
        assert len(c.evidence) == 1
        assert c.affected_entities["customer_id"] == "C001"


# ---------------------------------------------------------------------------
# AnalystQuery / AnalystResponse
# ---------------------------------------------------------------------------

class TestAnalyst:
    def test_query(self):
        q = AnalystQuery(question="What is total revenue?")
        assert q.question == "What is total revenue?"
        assert q.context is None

    def test_response_defaults(self):
        r = AnalystResponse(question="Q", answer="A")
        assert r.confidence == Confidence.medium
        assert r.follow_ups == []
        assert r.chart_data is None


# ---------------------------------------------------------------------------
# FeedbackItem
# ---------------------------------------------------------------------------

class TestFeedbackItem:
    def test_create(self):
        f = FeedbackItem(
            target_type="case",
            target_id="CASE-DUP-001",
            feedback_type=FeedbackType.approve,
            comment="Looks correct",
        )
        assert f.target_type == "case"
        assert f.feedback_id == ""  # auto-generated on save


# ---------------------------------------------------------------------------
# EvalScore
# ---------------------------------------------------------------------------

class TestEvalScore:
    def test_create(self):
        e = EvalScore(run_id="RUN-abc", actionability=4, correctness=5, specificity=3)
        assert e.actionability == 4
        assert e.total_cases == 0

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            EvalScore(run_id="RUN-abc", actionability=6)
        with pytest.raises(ValidationError):
            EvalScore(run_id="RUN-abc", correctness=0)


# ---------------------------------------------------------------------------
# MemoryEntry
# ---------------------------------------------------------------------------

class TestMemoryEntry:
    def test_create(self):
        m = MemoryEntry(key="duplicate_refund_window_hours", value=2, reason="default", source="seed")
        assert m.key == "duplicate_refund_window_hours"
        assert m.value == 2


# ---------------------------------------------------------------------------
# TraceRecord
# ---------------------------------------------------------------------------

class TestTraceRecord:
    def test_create(self):
        t = TraceRecord(
            run_id="RUN-abc",
            steps=["fetch_signals", "run_triage"],
            tools_called=["anomaly_tool"],
            cases_generated=5,
            duration_ms=1200,
        )
        assert t.cases_generated == 5
        assert len(t.steps) == 2


# ---------------------------------------------------------------------------
# AutonomousRunResult
# ---------------------------------------------------------------------------

class TestAutonomousRunResult:
    def test_empty_result(self):
        r = AutonomousRunResult(run_id="RUN-abc")
        assert r.cases == []
        assert r.actions == []
        assert r.reasoning_trace == {}

    def test_with_reasoning_trace(self):
        r = AutonomousRunResult(
            run_id="RUN-abc",
            reasoning_trace={"signal_analysis": "Found refund spike"},
        )
        assert "signal_analysis" in r.reasoning_trace


# ---------------------------------------------------------------------------
# API Response Models
# ---------------------------------------------------------------------------

class TestAPIResponses:
    def test_health_response(self):
        h = HealthResponse(status="ok", version="0.1.0", mode="real", tables_loaded=["customers"])
        assert h.mode == "real"

    def test_reset_response(self):
        r = ResetResponse()
        assert r.status == "ok"
        assert r.message == "Demo state reset"
