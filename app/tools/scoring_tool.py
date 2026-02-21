"""Scoring tool — assigns severity, confidence, and impact to raw anomalies.

Reads memory for false_positive_penalty to adjust confidence on rerun.
"""

from __future__ import annotations

from typing import Any

from app.models.schemas import Severity, Confidence
from app.storage.memory_store import get_memory
from app.storage.feedback_store import get_false_positive_case_ids


# Impact tiers
_IMPACT_HIGH = 200.0
_IMPACT_MEDIUM = 50.0

# Anomaly type → base severity / confidence
_BASE_SCORES: dict[str, dict[str, str]] = {
    "duplicate_refund":  {"severity": "high",   "confidence": "high"},
    "underbilling":      {"severity": "high",   "confidence": "high"},
    "tier_mismatch":     {"severity": "high",   "confidence": "high"},
    "refund_spike":      {"severity": "medium", "confidence": "medium"},
    "manual_credit":     {"severity": "medium", "confidence": "medium"},
}

# Recommended actions per type
_ACTIONS: dict[str, str] = {
    "duplicate_refund": "Investigate and reverse the duplicate refund. Verify with payment processor.",
    "underbilling":     "Correct billing amount on next invoice cycle. Notify finance team.",
    "tier_mismatch":    "Align invoice tier with subscription tier. Issue corrected invoice.",
    "refund_spike":     "Review regional refund surge. Check for service outage or policy abuse.",
    "manual_credit":    "Audit manual credit approval chain. Verify authorization.",
}


def score_anomaly(
    anomaly: dict[str, Any],
    false_positive_types: set[str] | None = None,
) -> dict[str, Any]:
    """Enrich a raw anomaly dict with severity, confidence, recommended_action.

    Args:
        anomaly: raw anomaly from anomaly_tool detectors
        false_positive_types: set of anomaly_types that had prior false positives
            (used to downgrade confidence on rerun)

    Returns:
        The same dict enriched with: severity, confidence, recommended_action, estimated_impact
    """
    atype = anomaly["anomaly_type"]
    base = _BASE_SCORES.get(atype, {"severity": "medium", "confidence": "medium"})

    severity = base["severity"]
    confidence = base["confidence"]
    impact = anomaly.get("raw_impact", 0.0)

    # Adjust severity by impact magnitude
    if impact >= _IMPACT_HIGH:
        severity = "high"
    elif impact < _IMPACT_MEDIUM:
        if severity == "high":
            severity = "medium"

    # Apply false-positive penalty from memory
    fp_penalty = get_memory("false_positive_penalty") or 0.0
    if false_positive_types and atype in false_positive_types:
        # Downgrade confidence one level
        if confidence == "high":
            confidence = "medium"
        elif confidence == "medium":
            confidence = "low"
        # Also reduce impact score by penalty factor
        if fp_penalty > 0:
            impact = impact * (1.0 - fp_penalty)

    anomaly["severity"] = severity
    anomaly["confidence"] = confidence
    anomaly["estimated_impact"] = round(impact, 2)
    anomaly["recommended_action"] = _ACTIONS.get(atype, "Review and investigate.")

    return anomaly


def score_all_anomalies(anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score and rank a list of raw anomalies.

    Returns anomalies sorted by estimated_impact descending.
    """
    # Determine which anomaly types have had false positives before
    fp_case_ids = get_false_positive_case_ids()
    # Map case ID prefixes back to anomaly types
    # Case IDs follow pattern: CASE-{TYPE_PREFIX}-{run}-{idx}
    _PREFIX_TO_TYPE = {
        "DUP": "duplicate_refund",
        "UND": "underbilling",
        "TIE": "tier_mismatch",
        "REF": "refund_spike",
        "MAN": "manual_credit",
    }
    fp_types: set[str] = set()
    for cid in fp_case_ids:
        parts = cid.split("-")
        if len(parts) >= 2:
            prefix = parts[1]
            if prefix in _PREFIX_TO_TYPE:
                fp_types.add(_PREFIX_TO_TYPE[prefix])

    scored = [score_anomaly(a, fp_types) for a in anomalies]

    # Sort: high severity first, then by impact descending
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    scored.sort(key=lambda x: (severity_order.get(x["severity"], 9), -x["estimated_impact"]))

    return scored
