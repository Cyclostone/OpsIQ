"""Tests for all FastAPI endpoints — full integration tests via TestClient."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealthAPI:
    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert data["mode"] in ("mock", "real")
        assert isinstance(data["tables_loaded"], list)
        assert len(data["tables_loaded"]) >= 7

    def test_health_tables_loaded(self):
        resp = client.get("/health")
        tables = resp.json()["tables_loaded"]
        expected = ["customers", "invoices", "payments", "refunds",
                    "signal_events", "subscriptions", "usage_events"]
        for t in expected:
            assert t in tables


# ---------------------------------------------------------------------------
# Monitor / Autonomous Run
# ---------------------------------------------------------------------------

class TestMonitorAPI:
    def test_run_autonomous(self):
        resp = client.post("/monitor/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "cases" in data
        assert "actions" in data
        assert isinstance(data["cases"], list)
        assert len(data["cases"]) > 0

    def test_run_autonomous_has_reasoning_trace(self):
        resp = client.post("/monitor/run")
        data = resp.json()
        assert "reasoning_trace" in data
        # If LLM is available, should have reasoning steps
        if data.get("reasoning_trace"):
            assert isinstance(data["reasoning_trace"], dict)

    def test_run_autonomous_has_sponsor_activity(self):
        resp = client.post("/monitor/run")
        data = resp.json()
        assert "sponsor_activity" in data
        activity = data["sponsor_activity"]
        assert isinstance(activity, dict)

    def test_fetch_signals(self):
        resp = client.get("/monitor/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert "signals" in data
        signals = data["signals"]
        assert isinstance(signals, list)
        assert len(signals) > 0
        for signal in signals:
            assert "signal_id" in signal
            assert "source" in signal
            assert "severity" in signal


# ---------------------------------------------------------------------------
# Triage Cases
# ---------------------------------------------------------------------------

class TestTriageAPI:
    def _ensure_cases_exist(self):
        """Run autonomous to populate cases."""
        client.post("/monitor/run")

    def test_get_cases(self):
        self._ensure_cases_exist()
        resp = client.get("/triage/cases")
        assert resp.status_code == 200
        data = resp.json()
        assert "cases" in data
        assert "count" in data
        assert len(data["cases"]) > 0

    def test_case_structure(self):
        self._ensure_cases_exist()
        resp = client.get("/triage/cases")
        cases = resp.json()["cases"]
        for c in cases:
            assert "case_id" in c
            assert "run_id" in c
            assert "title" in c
            assert "anomaly_type" in c
            assert "severity" in c
            assert "confidence" in c
            assert "estimated_impact" in c
            assert "evidence" in c
            assert "status" in c

    def test_case_has_sentiment_score(self):
        self._ensure_cases_exist()
        resp = client.get("/triage/cases")
        cases = resp.json()["cases"]
        for c in cases:
            assert "sentiment_score" in c
            if c["sentiment_score"]:
                assert "overall_polarity" in c["sentiment_score"]
                assert "overall_risk_level" in c["sentiment_score"]

    def test_get_case_by_id(self):
        self._ensure_cases_exist()
        cases = client.get("/triage/cases").json()["cases"]
        if cases:
            case_id = cases[0]["case_id"]
            resp = client.get(f"/triage/cases/{case_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["case_id"] == case_id

    def test_get_case_not_found(self):
        resp = client.get("/triage/cases/NONEXISTENT-CASE")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Analyst
# ---------------------------------------------------------------------------

class TestAnalystAPI:
    def test_ask_question(self):
        resp = client.post("/analyst/query", json={"question": "What is total revenue?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "question" in data
        assert "answer" in data
        assert data["question"] == "What is total revenue?"
        assert len(data["answer"]) > 0

    def test_ask_refund_question(self):
        resp = client.post("/analyst/query", json={"question": "Show me refund data by region"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data

    def test_ask_with_chart_data(self):
        resp = client.post("/analyst/query", json={"question": "What is total revenue?"})
        data = resp.json()
        # Should have chart_data and follow_ups
        assert "chart_data" in data
        assert "follow_ups" in data


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class TestFeedbackAPI:
    def test_submit_feedback(self):
        # Ensure a case exists first
        client.post("/monitor/run")
        cases = client.get("/triage/cases").json()["cases"]
        target_id = cases[0]["case_id"] if cases else "CASE-TEST-001"
        resp = client.post("/feedback", json={
            "target_type": "case",
            "target_id": target_id,
            "feedback_type": "approve",
            "comment": "Looks correct",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "feedback" in data
        assert data["feedback"]["feedback_id"].startswith("FB-")

    def test_get_all_feedback(self):
        # Submit one first
        client.post("/feedback", json={
            "target_type": "case",
            "target_id": "CASE-TEST-002",
            "feedback_type": "reject",
            "comment": "Not relevant",
        })
        resp = client.get("/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert "feedback" in data
        assert isinstance(data["feedback"], list)
        assert len(data["feedback"]) >= 1

    def test_feedback_counts(self):
        resp = client.get("/feedback/counts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_improvement_summary(self):
        resp = client.get("/feedback/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Evaluation & Observability
# ---------------------------------------------------------------------------

class TestEvalAPI:
    def test_get_latest_eval(self):
        resp = client.get("/eval/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "eval" in data

    def test_get_all_evals(self):
        resp = client.get("/eval/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "evals" in data
        assert isinstance(data["evals"], list)

    def test_get_memory(self):
        resp = client.get("/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert "memory" in data
        assert isinstance(data["memory"], list)

    def test_get_latest_trace(self):
        # Run autonomous first to generate a trace
        client.post("/monitor/run")
        resp = client.get("/traces/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "trace" in data
        if data["trace"]:
            assert "run_id" in data["trace"]
            assert "steps" in data["trace"]

    def test_get_all_traces(self):
        resp = client.get("/traces/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert isinstance(data["traces"], list)

    def test_llm_status(self):
        resp = client.get("/llm/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "provider" in data
        assert "model" in data

    def test_llm_reasoning_log(self):
        resp = client.get("/llm/reasoning")
        assert resp.status_code == 200
        data = resp.json()
        assert "reasoning_log" in data
        assert isinstance(data["reasoning_log"], list)


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------

class TestSentimentAPI:
    def test_analyze_text(self):
        resp = client.post("/sentiment/analyze", json={
            "text": "Suspicious duplicate refund detected",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "polarity" in data
        assert "risk_level" in data

    def test_sentiment_status(self):
        resp = client.get("/sentiment/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert data["name"] == "modulate"

    def test_sentiment_log(self):
        # Analyze something first
        client.post("/sentiment/analyze", json={"text": "Test text"})
        resp = client.get("/sentiment/log")
        assert resp.status_code == 200
        data = resp.json()
        assert "analysis_log" in data
        assert isinstance(data["analysis_log"], list)


# ---------------------------------------------------------------------------
# Sponsors & Demo
# ---------------------------------------------------------------------------

class TestSponsorAPI:
    def test_sponsor_status(self):
        resp = client.get("/sponsors/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "sponsors" in data
        assert "llm" in data
        assert "mode" in data
        sponsors = data["sponsors"]
        assert len(sponsors) == 4
        names = [s["name"] for s in sponsors]
        assert "Datadog" in names
        assert "Lightdash" in names
        assert "Airia" in names
        # Modulate may be lowercase
        assert any("modulate" in n.lower() for n in names)

    def test_sponsor_status_no_duplicates(self):
        resp = client.get("/sponsors/status")
        sponsors = resp.json()["sponsors"]
        names = [s["name"].lower() for s in sponsors]
        assert len(names) == len(set(names)), f"Duplicate sponsors found: {names}"

    def test_sponsor_activity(self):
        # Run autonomous first to generate activity
        client.post("/monitor/run")
        resp = client.get("/sponsors/activity")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_demo_reset(self):
        resp = client.post("/demo/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_demo_reset_clears_cases(self):
        # Run to generate cases
        client.post("/monitor/run")
        cases_before = client.get("/triage/cases").json()["cases"]
        assert len(cases_before) > 0
        # Reset
        client.post("/demo/reset")
        cases_after = client.get("/triage/cases").json()["cases"]
        assert len(cases_after) == 0
