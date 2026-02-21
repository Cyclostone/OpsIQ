"""Tests for agents — triage, monitor."""

import pytest
from datetime import datetime

from app.models.schemas import SignalEvent, Severity, TriageCase


# ---------------------------------------------------------------------------
# Monitor Agent
# ---------------------------------------------------------------------------

class TestMonitorAgent:
    def test_fetch_all_signals(self):
        from app.agents.monitor_agent import fetch_all_signals
        signals = fetch_all_signals()
        assert isinstance(signals, list)
        assert len(signals) > 0
        for s in signals:
            assert isinstance(s, SignalEvent)

    def test_signals_sorted_by_severity(self):
        from app.agents.monitor_agent import fetch_all_signals
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        signals = fetch_all_signals()
        if len(signals) >= 2:
            for i in range(len(signals) - 1):
                s1_order = severity_order.get(signals[i].severity.value, 9)
                s2_order = severity_order.get(signals[i + 1].severity.value, 9)
                assert s1_order <= s2_order

    def test_pick_trigger_signal(self):
        from app.agents.monitor_agent import fetch_all_signals, pick_trigger_signal
        signals = fetch_all_signals()
        trigger = pick_trigger_signal(signals)
        assert trigger is not None
        assert isinstance(trigger, SignalEvent)
        # Should be the highest-priority signal
        assert trigger == signals[0]

    def test_pick_trigger_signal_empty(self):
        from app.agents.monitor_agent import pick_trigger_signal
        trigger = pick_trigger_signal([])
        assert trigger is None

    def test_enrich_signal_datadog(self):
        from app.agents.monitor_agent import enrich_signal
        signal = SignalEvent(
            signal_id="SIG-DD-TEST",
            timestamp=datetime.utcnow(),
            signal_type="anomaly_alert",
            severity=Severity.high,
            source="datadog",
            related_entity="refunds",
        )
        context = enrich_signal(signal)
        assert "signal" in context
        assert "adapter_context" in context
        assert context["adapter_context"]["source"] == "datadog"

    def test_enrich_signal_lightdash(self):
        from app.agents.monitor_agent import enrich_signal
        signal = SignalEvent(
            signal_id="SIG-LH-TEST",
            timestamp=datetime.utcnow(),
            signal_type="metric_drift",
            severity=Severity.medium,
            source="lightdash",
            related_entity="invoices",
        )
        context = enrich_signal(signal)
        assert context["adapter_context"]["source"] == "lightdash"

    def test_enrich_signal_internal(self):
        from app.agents.monitor_agent import enrich_signal
        signal = SignalEvent(
            signal_id="SIG-INT-TEST",
            timestamp=datetime.utcnow(),
            signal_type="billing_anomaly",
            severity=Severity.high,
            source="internal",
            related_entity="billing",
        )
        context = enrich_signal(signal)
        assert context["adapter_context"]["source"] == "internal"


# ---------------------------------------------------------------------------
# Triage Agent
# ---------------------------------------------------------------------------

class TestTriageAgent:
    def test_run_triage_returns_cases(self):
        from app.agents.triage_agent import run_triage
        cases = run_triage("RUN-test-triage")
        assert isinstance(cases, list)
        assert len(cases) > 0
        for c in cases:
            assert isinstance(c, TriageCase)

    def test_triage_cases_have_required_fields(self):
        from app.agents.triage_agent import run_triage
        cases = run_triage("RUN-test-fields")
        for c in cases:
            assert c.case_id.startswith("CASE-")
            assert c.run_id == "RUN-test-fields"
            assert c.title != ""
            assert c.anomaly_type != ""
            assert c.severity in (Severity.low, Severity.medium, Severity.high, Severity.critical)
            assert c.recommended_action != ""

    def test_triage_cases_have_sentiment(self):
        from app.agents.triage_agent import run_triage
        cases = run_triage("RUN-test-sentiment")
        # All cases should have sentiment scores from Modulate adapter
        for c in cases:
            assert c.sentiment_score is not None
            assert "overall_polarity" in c.sentiment_score
            assert "overall_risk_level" in c.sentiment_score

    def test_triage_auto_generates_run_id(self):
        from app.agents.triage_agent import run_triage
        cases = run_triage()
        assert len(cases) > 0
        assert cases[0].run_id.startswith("RUN-")

    def test_triage_case_id_format(self):
        from app.agents.triage_agent import run_triage
        cases = run_triage("RUN-abc12345")
        for i, c in enumerate(cases):
            # Format: CASE-{TYPE_PREFIX}-{run_suffix}-{index}
            parts = c.case_id.split("-")
            assert parts[0] == "CASE"
            assert len(parts) >= 4

    def test_generate_title(self):
        from app.agents.triage_agent import _generate_title
        anomaly = {
            "anomaly_type": "duplicate_refund",
            "affected_entities": {"customer_id": "C003", "refund_ids": ["R001", "R002"]},
        }
        title = _generate_title(anomaly)
        assert "C003" in title
        assert "Duplicate Refund" in title

    def test_generate_title_underbilling(self):
        from app.agents.triage_agent import _generate_title
        anomaly = {
            "anomaly_type": "underbilling",
            "affected_entities": {"customer_name": "Acme Corp", "invoice_id": "INV001"},
        }
        title = _generate_title(anomaly)
        assert "Acme Corp" in title
        assert "Underbilling" in title

    def test_generate_title_refund_spike(self):
        from app.agents.triage_agent import _generate_title
        anomaly = {
            "anomaly_type": "refund_spike",
            "affected_entities": {"region": "EMEA", "date": "2026-02-15", "refund_count": 6},
        }
        title = _generate_title(anomaly)
        assert "EMEA" in title
        assert "Refund Spike" in title
