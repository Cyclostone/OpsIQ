"""Tests for anomaly detection and scoring tools."""

import pytest
from app.models.schemas import Severity, Confidence


# ---------------------------------------------------------------------------
# Scoring Tool
# ---------------------------------------------------------------------------

class TestScoringTool:
    def test_score_anomaly_high_impact(self):
        from app.tools.scoring_tool import score_anomaly
        anomaly = {
            "anomaly_type": "duplicate_refund",
            "raw_impact": 500.0,
            "evidence": ["Test evidence"],
            "affected_entities": {"customer_id": "C001"},
        }
        scored = score_anomaly(anomaly)
        assert scored["severity"] == "high"
        assert scored["confidence"] == "high"
        assert scored["estimated_impact"] == 500.0
        assert "recommended_action" in scored

    def test_score_anomaly_low_impact_downgrades(self):
        from app.tools.scoring_tool import score_anomaly
        anomaly = {
            "anomaly_type": "duplicate_refund",
            "raw_impact": 30.0,
            "evidence": ["Small duplicate"],
            "affected_entities": {},
        }
        scored = score_anomaly(anomaly)
        # Impact < 50 should downgrade high → medium
        assert scored["severity"] == "medium"

    def test_score_anomaly_with_false_positive_penalty(self):
        from app.tools.scoring_tool import score_anomaly
        anomaly = {
            "anomaly_type": "duplicate_refund",
            "raw_impact": 500.0,
            "evidence": ["Test"],
            "affected_entities": {},
        }
        fp_types = {"duplicate_refund"}
        scored = score_anomaly(anomaly, false_positive_types=fp_types)
        # Confidence should be downgraded from high → medium
        assert scored["confidence"] == "medium"

    def test_score_all_anomalies_sorted(self):
        from app.tools.scoring_tool import score_all_anomalies
        anomalies = [
            {"anomaly_type": "manual_credit", "raw_impact": 100.0, "evidence": [], "affected_entities": {}},
            {"anomaly_type": "duplicate_refund", "raw_impact": 500.0, "evidence": [], "affected_entities": {}},
            {"anomaly_type": "underbilling", "raw_impact": 300.0, "evidence": [], "affected_entities": {}},
        ]
        scored = score_all_anomalies(anomalies)
        assert len(scored) == 3
        # Should be sorted by severity then impact descending
        assert scored[0]["estimated_impact"] >= scored[-1]["estimated_impact"]

    def test_recommended_actions_per_type(self):
        from app.tools.scoring_tool import score_anomaly
        types = ["duplicate_refund", "underbilling", "tier_mismatch", "refund_spike", "manual_credit"]
        for atype in types:
            anomaly = {"anomaly_type": atype, "raw_impact": 100.0, "evidence": [], "affected_entities": {}}
            scored = score_anomaly(anomaly)
            assert scored["recommended_action"] != ""
            assert len(scored["recommended_action"]) > 10


# ---------------------------------------------------------------------------
# Anomaly Tool (integration — requires DuckDB data)
# ---------------------------------------------------------------------------

class TestAnomalyTool:
    def test_run_all_detectors_returns_list(self):
        from app.tools.anomaly_tool import run_all_detectors
        results = run_all_detectors()
        assert isinstance(results, list)
        # With seed data, we should get at least some anomalies
        assert len(results) > 0

    def test_all_anomalies_have_required_fields(self):
        from app.tools.anomaly_tool import run_all_detectors
        results = run_all_detectors()
        for anomaly in results:
            assert "anomaly_type" in anomaly
            assert "evidence" in anomaly
            assert "affected_entities" in anomaly
            assert "raw_impact" in anomaly
            assert isinstance(anomaly["evidence"], list)
            assert isinstance(anomaly["affected_entities"], dict)

    def test_anomaly_types_are_valid(self):
        from app.tools.anomaly_tool import run_all_detectors
        valid_types = {"duplicate_refund", "underbilling", "tier_mismatch", "refund_spike", "manual_credit"}
        results = run_all_detectors()
        for anomaly in results:
            assert anomaly["anomaly_type"] in valid_types

    def test_detect_duplicate_refunds(self):
        from app.tools.anomaly_tool import detect_duplicate_refunds
        results = detect_duplicate_refunds()
        assert isinstance(results, list)
        for r in results:
            assert r["anomaly_type"] == "duplicate_refund"
            assert "refund_ids" in r["affected_entities"]

    def test_detect_underbilling(self):
        from app.tools.anomaly_tool import detect_underbilling
        results = detect_underbilling()
        assert isinstance(results, list)
        for r in results:
            assert r["anomaly_type"] == "underbilling"
            assert r["raw_impact"] > 0

    def test_detect_tier_mismatch(self):
        from app.tools.anomaly_tool import detect_tier_mismatch
        results = detect_tier_mismatch()
        assert isinstance(results, list)
        for r in results:
            assert r["anomaly_type"] == "tier_mismatch"

    def test_detect_refund_spike(self):
        from app.tools.anomaly_tool import detect_refund_spike
        results = detect_refund_spike()
        assert isinstance(results, list)
        for r in results:
            assert r["anomaly_type"] == "refund_spike"
            assert "region" in r["affected_entities"]

    def test_detect_manual_credits(self):
        from app.tools.anomaly_tool import detect_manual_credits
        results = detect_manual_credits()
        assert isinstance(results, list)
        for r in results:
            assert r["anomaly_type"] == "manual_credit"
            assert r["raw_impact"] > 0
