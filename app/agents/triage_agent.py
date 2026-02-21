"""Triage Agent — orchestrates anomaly detection, scoring, and case creation.

Flow:
  1. Run all anomaly detectors (anomaly_tool)
  2. Score and rank results (scoring_tool)
  3. Generate TriageCase objects
  4. Persist cases to case_store
  5. Return ranked case list

Reads memory thresholds so reruns after feedback produce different results.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import TriageCase, Severity, Confidence, CaseStatus
from app.tools.anomaly_tool import run_all_detectors
from app.tools.scoring_tool import score_all_anomalies
from app.storage.case_store import save_cases
from app.storage.memory_store import get_memory
from app.adapters import modulate_adapter


def _generate_title(anomaly: dict[str, Any]) -> str:
    """Create a human-readable title for a case."""
    atype = anomaly["anomaly_type"]
    entities = anomaly.get("affected_entities", {})

    if atype == "duplicate_refund":
        cid = entities.get("customer_id", "unknown")
        refs = entities.get("refund_ids", [])
        return f"Duplicate Refund: {cid} ({', '.join(refs)})"

    elif atype == "underbilling":
        name = entities.get("customer_name", entities.get("customer_id", "unknown"))
        inv = entities.get("invoice_id", "")
        return f"Underbilling: {name} ({inv})"

    elif atype == "tier_mismatch":
        name = entities.get("customer_name", entities.get("customer_id", "unknown"))
        sub_tier = entities.get("subscription_tier", "?")
        bill_tier = entities.get("billed_tier", "?")
        return f"Tier Mismatch: {name} ({sub_tier} → billed as {bill_tier})"

    elif atype == "refund_spike":
        region = entities.get("region", "unknown")
        date = entities.get("date", "")
        count = entities.get("refund_count", 0)
        return f"Refund Spike: {region} region — {count} refunds on {date}"

    elif atype == "manual_credit":
        name = entities.get("customer_name", entities.get("customer_id", "unknown"))
        rid = entities.get("refund_id", "")
        return f"Suspicious Manual Credit: {name} ({rid})"

    return f"Anomaly: {atype}"


def _anomaly_to_case(anomaly: dict[str, Any], run_id: str, index: int) -> TriageCase:
    """Convert a scored anomaly dict into a TriageCase model."""
    atype = anomaly["anomaly_type"]
    short = atype[:3].upper()
    case_id = f"CASE-{short}-{run_id[-6:]}-{index:02d}"

    return TriageCase(
        case_id=case_id,
        run_id=run_id,
        title=_generate_title(anomaly),
        anomaly_type=atype,
        severity=Severity(anomaly.get("severity", "medium")),
        confidence=Confidence(anomaly.get("confidence", "medium")),
        estimated_impact=anomaly.get("estimated_impact", 0.0),
        evidence=anomaly.get("evidence", []),
        affected_entities=anomaly.get("affected_entities", {}),
        recommended_action=anomaly.get("recommended_action", ""),
        status=CaseStatus.open,
        created_at=datetime.utcnow(),
    )


def run_triage(run_id: str | None = None) -> list[TriageCase]:
    """Execute full triage pipeline: detect → score → create cases → persist.

    Args:
        run_id: Optional run identifier. Auto-generated if not provided.

    Returns:
        List of TriageCase objects, ranked by severity and impact.
    """
    if not run_id:
        run_id = f"RUN-{uuid.uuid4().hex[:8]}"

    print(f"[triage_agent] Starting triage run {run_id}")

    # Step 1: Detect anomalies
    print("[triage_agent] Step 1: Running anomaly detectors...")
    raw_anomalies = run_all_detectors()
    print(f"[triage_agent] Found {len(raw_anomalies)} raw anomalies")

    if not raw_anomalies:
        print("[triage_agent] No anomalies detected.")
        return []

    # Step 2: Score and rank
    print("[triage_agent] Step 2: Scoring anomalies...")
    scored = score_all_anomalies(raw_anomalies)

    # Step 3: Convert to cases
    print("[triage_agent] Step 3: Creating cases...")
    cases = [
        _anomaly_to_case(a, run_id, i)
        for i, a in enumerate(scored)
    ]

    # Step 4: Modulate sentiment analysis on case evidence
    print("[triage_agent] Step 4: Running Modulate sentiment analysis...")
    for case in cases:
        try:
            sentiment = modulate_adapter.analyze_case_evidence(
                evidence=case.evidence,
                case_title=case.title,
                anomaly_type=case.anomaly_type,
            )
            case.sentiment_score = sentiment
            risk = sentiment.get("overall_risk_level", "neutral")
            polarity = sentiment.get("overall_polarity", 0)
            print(f"  {case.case_id}: polarity={polarity:.2f}, risk={risk}")
        except Exception as e:
            print(f"  {case.case_id}: sentiment analysis failed: {e}")

    # Step 5: Persist
    print("[triage_agent] Step 5: Persisting cases...")
    save_cases(cases)

    total_impact = sum(c.estimated_impact for c in cases)
    print(f"[triage_agent] Triage complete: {len(cases)} cases, total impact ${total_impact:,.2f}")

    return cases
