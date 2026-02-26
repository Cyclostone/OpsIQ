"""Tests for all adapters — Datadog, Lightdash, Airia, Modulate (Sentiment), LLM Client."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.models.schemas import (
    SignalEvent, Severity, Confidence, TriageCase, CaseStatus,
)


# ---------------------------------------------------------------------------
# Datadog Adapter
# ---------------------------------------------------------------------------

class TestDatadogAdapter:
    def setup_method(self):
        from app.adapters import datadog_adapter
        datadog_adapter.reset()
        self.adapter = datadog_adapter

    def test_fetch_signals_returns_list(self):
        signals = self.adapter.fetch_signals()
        assert isinstance(signals, list)
        for s in signals:
            assert isinstance(s, SignalEvent)
            assert s.source == "datadog"

    def test_fetch_alert_context(self):
        signal = SignalEvent(
            signal_id="SIG-TEST",
            timestamp=datetime.utcnow(),
            signal_type="anomaly_alert",
            severity=Severity.high,
            source="datadog",
            related_entity="refunds",
        )
        context = self.adapter.fetch_alert_context(signal)
        assert context["source"] == "datadog"
        assert context["signal_id"] == "SIG-TEST"

    def test_call_log_tracks_calls(self):
        self.adapter.fetch_signals()
        log = self.adapter.get_call_log()
        assert len(log) >= 1
        assert "action" in log[0]
        assert "timestamp" in log[0]

    def test_reset_clears_state(self):
        self.adapter.fetch_signals()
        assert len(self.adapter.get_call_log()) >= 1
        self.adapter.reset()
        assert len(self.adapter.get_call_log()) == 0


# ---------------------------------------------------------------------------
# Lightdash Adapter
# ---------------------------------------------------------------------------

class TestLightdashAdapter:
    def setup_method(self):
        from app.adapters import lightdash_adapter
        lightdash_adapter.reset()
        self.adapter = lightdash_adapter

    def test_metric_definitions_count(self):
        defs = self.adapter.get_metric_definitions()
        assert len(defs) == 8

    def test_metric_definitions_structure(self):
        defs = self.adapter.get_metric_definitions()
        for m in defs:
            assert "name" in m
            assert "label" in m
            assert "description" in m
            assert "sql" in m
            assert "type" in m

    def test_get_metric_by_name_found(self):
        m = self.adapter.get_metric_by_name("monthly_revenue")
        assert m is not None
        assert m["name"] == "monthly_revenue"
        assert "sum" in m["type"]

    def test_get_metric_by_name_not_found(self):
        m = self.adapter.get_metric_by_name("nonexistent_metric")
        assert m is None

    def test_get_chart_config(self):
        config = self.adapter.get_chart_config("monthly_revenue", "bar")
        assert config["source"] == "lightdash"
        assert config["chart_type"] == "bar"
        assert config["metric"] == "monthly_revenue"

    def test_fetch_signals_returns_list(self):
        signals = self.adapter.fetch_signals()
        assert isinstance(signals, list)
        for s in signals:
            assert isinstance(s, SignalEvent)

    def test_reset_clears_state(self):
        self.adapter.get_metric_definitions()
        self.adapter.reset()
        assert len(self.adapter.get_call_log()) == 0


# ---------------------------------------------------------------------------
# Airia Adapter
# ---------------------------------------------------------------------------

class TestAiriaAdapter:
    def setup_method(self):
        from app.adapters import airia_adapter
        airia_adapter.reset()
        self.adapter = airia_adapter

    def test_create_case_action(self):
        case = TriageCase(
            case_id="CASE-TEST-001",
            run_id="RUN-test",
            title="Test Case",
            anomaly_type="duplicate_refund",
            severity=Severity.high,
            confidence=Confidence.high,
            estimated_impact=500.0,
            recommended_action="Investigate",
        )
        action = self.adapter.create_case_action(case)
        assert "action_id" in action
        assert action["action_type"] == "create_case"
        assert action["case_id"] == "CASE-TEST-001"
        assert "workflow_run_id" in action
        assert "audit_trail" in action

    def test_create_alert_action(self):
        action = self.adapter.create_alert_action(
            title="Test Alert",
            severity="high",
            message="Test message",
            target="finance-team",
        )
        assert action["action_type"] == "send_alert"
        assert action["target"] == "finance-team"
        assert "workflow_run_id" in action

    def test_create_approval_task(self):
        action = self.adapter.create_approval_task(
            title="Review: Test",
            description="Test description",
            assignee="finance-manager",
            case_id="CASE-TEST-001",
        )
        assert action["action_type"] == "approval_task"
        assert action["assignee"] == "finance-manager"
        assert action["case_id"] == "CASE-TEST-001"

    def test_get_actions_tracks_created(self):
        case = TriageCase(
            case_id="CASE-TEST-002",
            run_id="RUN-test",
            title="Test",
            anomaly_type="underbilling",
            severity=Severity.medium,
            confidence=Confidence.medium,
        )
        self.adapter.create_case_action(case)
        actions = self.adapter.get_actions()
        assert len(actions) == 1

    def test_reset_clears_state(self):
        case = TriageCase(
            case_id="CASE-TEST-003",
            run_id="RUN-test",
            title="Test",
            anomaly_type="underbilling",
            severity=Severity.medium,
            confidence=Confidence.medium,
        )
        self.adapter.create_case_action(case)
        self.adapter.reset()
        assert len(self.adapter.get_actions()) == 0
        assert len(self.adapter.get_call_log()) == 0


# ---------------------------------------------------------------------------
# Modulate Adapter (Sentiment Engine)
# ---------------------------------------------------------------------------

class TestModulateAdapter:
    def setup_method(self):
        from app.adapters import modulate_adapter
        modulate_adapter.reset()
        self.adapter = modulate_adapter

    def test_analyze_text_negative(self):
        result = self.adapter.analyze_text("Suspicious duplicate refund detected for fraud")
        assert "polarity" in result
        assert "risk_level" in result
        assert result["polarity"] < 0  # negative sentiment
        assert result["risk_level"] in ("high", "elevated")

    def test_analyze_text_positive(self):
        result = self.adapter.analyze_text("Invoice verified and confirmed as correct and valid")
        assert result["polarity"] > 0
        assert result["risk_level"] == "low"

    def test_analyze_text_empty(self):
        result = self.adapter.analyze_text("")
        assert result["polarity"] == 0.0
        assert result["risk_level"] == "neutral"

    def test_analyze_case_evidence(self):
        evidence = [
            "Duplicate refund detected for customer C003",
            "Same amount $150.00 within 2h window",
            "Suspicious pattern of manual credits",
        ]
        result = self.adapter.analyze_case_evidence(
            evidence=evidence,
            case_title="Duplicate Refund: C003",
            anomaly_type="duplicate_refund",
        )
        assert "overall_polarity" in result
        assert "overall_risk_level" in result
        assert "evidence_scores" in result
        assert result["analyzed_count"] == 3
        assert len(result["evidence_scores"]) == 3

    def test_analyze_case_evidence_empty(self):
        result = self.adapter.analyze_case_evidence(evidence=[])
        assert result["analyzed_count"] == 0
        assert result["overall_risk_level"] == "neutral"

    def test_analysis_log(self):
        self.adapter.analyze_text("Test text for logging")
        log = self.adapter.get_analysis_log()
        assert len(log) >= 1
        assert "timestamp" in log[0]
        assert "provider" in log[0]

    def test_reset_clears_state(self):
        self.adapter.analyze_text("Test")
        self.adapter.reset()
        assert len(self.adapter.get_analysis_log()) == 0


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class TestLLMClient:
    def setup_method(self):
        from app.adapters import llm_client
        llm_client.reset()
        self.client = llm_client

    def test_is_available(self):
        # Should be True if Groq key is set in .env
        result = self.client.is_available()
        assert isinstance(result, bool)

    def test_get_provider(self):
        provider = self.client.get_provider()
        assert provider in ("groq", "openai", "none")

    def test_get_model(self):
        model = self.client.get_model()
        assert isinstance(model, str)

    def test_get_status_structure(self):
        status = self.client.get_status()
        assert "available" in status
        assert "provider" in status
        assert "model" in status
        assert "call_count" in status
        assert "reasoning_steps" in status

    def test_template_explain_fallback(self):
        explanation = self.client._template_explain(
            "Duplicate Refund: C003",
            ["Refunds R001 and R002 for same amount"],
            "duplicate_refund",
        )
        assert "duplicate refund" in explanation.lower()
        assert len(explanation) > 20

    def test_template_follow_ups_revenue(self):
        follow_ups = self.client._template_follow_ups("What is total revenue?")
        assert len(follow_ups) == 3
        assert any("revenue" in f.lower() for f in follow_ups)

    def test_template_follow_ups_refund(self):
        follow_ups = self.client._template_follow_ups("Show me refund data")
        assert len(follow_ups) == 3
        assert any("refund" in f.lower() for f in follow_ups)

    def test_template_follow_ups_generic(self):
        follow_ups = self.client._template_follow_ups("Tell me about operations")
        assert len(follow_ups) == 3

    def test_reset_clears_state(self):
        self.client.reset()
        assert self.client.get_status()["call_count"] == 0
        assert self.client.get_status()["reasoning_steps"] == 0
