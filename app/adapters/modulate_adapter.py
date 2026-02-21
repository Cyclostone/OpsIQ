"""Modulate Adapter — sentiment analysis on case evidence text.

Modulate's ToxMod API analyzes text for sentiment, toxicity, and risk signals.
In OpsIQ, we use it to add a sentiment/risk dimension to triage cases:
  - Negative sentiment on evidence → higher urgency (potential fraud language)
  - Neutral/positive → routine anomaly
  - Subjectivity score → how opinion-based vs factual the evidence is

Integration modes:
  1. MCP Sentiment Tool (primary) — uses the local MCP sentiment-analysis server
  2. Modulate API (if MODULATE_API_KEY set) — calls real ToxMod API
  3. Heuristic fallback — keyword-based scoring if neither available

Setup:
  - MCP tool is available automatically (no key needed)
  - For real Modulate API: https://console.modulate.ai → API Key → add to .env
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.config import settings
from app.models.schemas import AdapterMode


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------
_last_used: datetime | None = None
_call_count: int = 0
_analysis_log: list[dict[str, Any]] = []


def get_mode() -> AdapterMode:
    """Return current adapter mode."""
    if settings.modulate_available:
        return AdapterMode.real
    return AdapterMode.mock


def get_status() -> dict[str, Any]:
    """Return adapter status for health checks."""
    return {
        "name": "modulate",
        "mode": get_mode().value,
        "available": True,  # MCP tool always available as fallback
        "modulate_api_key_set": settings.modulate_available,
        "call_count": _call_count,
        "last_used": _last_used.isoformat() if _last_used else None,
        "description": "Sentiment analysis on case evidence (via MCP sentiment tool / Modulate ToxMod API)",
    }


# ---------------------------------------------------------------------------
# Core sentiment analysis
# ---------------------------------------------------------------------------

def analyze_text(text: str, context: str = "") -> dict[str, Any]:
    """Analyze sentiment of a text string.

    Args:
        text: The text to analyze (case evidence, title, etc.)
        context: Optional context label (e.g. "case_evidence", "case_title")

    Returns:
        Dict with polarity (-1 to 1), subjectivity (0 to 1), assessment, risk_level
    """
    global _last_used, _call_count

    if not text or not text.strip():
        return _empty_result(context)

    # Try Modulate API first if key is set
    if settings.modulate_available:
        result = _call_modulate_api(text, context)
        if result:
            return result

    # Fallback: heuristic keyword-based analysis
    result = _heuristic_sentiment(text, context)
    _last_used = datetime.utcnow()
    _call_count += 1
    _log_analysis(text, result, "heuristic")
    return result


def analyze_case_evidence(evidence: list[str], case_title: str = "", anomaly_type: str = "") -> dict[str, Any]:
    """Analyze sentiment across all evidence strings for a triage case.

    Returns aggregated sentiment with per-evidence breakdown.
    """
    if not evidence:
        return {
            "overall_polarity": 0.0,
            "overall_subjectivity": 0.0,
            "overall_risk_level": "neutral",
            "overall_assessment": "No evidence to analyze",
            "evidence_scores": [],
            "case_title_score": None,
            "analyzed_count": 0,
        }

    # Analyze each evidence string
    evidence_scores = []
    for i, ev in enumerate(evidence):
        score = analyze_text(ev, context=f"evidence_{i}")
        evidence_scores.append(score)

    # Analyze case title if provided
    title_score = None
    if case_title:
        title_score = analyze_text(case_title, context="case_title")

    # Aggregate: average polarity and subjectivity
    polarities = [s["polarity"] for s in evidence_scores]
    subjectivities = [s["subjectivity"] for s in evidence_scores]

    avg_polarity = sum(polarities) / len(polarities) if polarities else 0.0
    avg_subjectivity = sum(subjectivities) / len(subjectivities) if subjectivities else 0.0

    # Determine overall risk level
    risk_level = _polarity_to_risk(avg_polarity, anomaly_type)

    # Generate assessment
    assessment = _generate_assessment(avg_polarity, avg_subjectivity, risk_level, anomaly_type, len(evidence))

    return {
        "overall_polarity": round(avg_polarity, 3),
        "overall_subjectivity": round(avg_subjectivity, 3),
        "overall_risk_level": risk_level,
        "overall_assessment": assessment,
        "evidence_scores": evidence_scores,
        "case_title_score": title_score,
        "analyzed_count": len(evidence_scores),
    }


# ---------------------------------------------------------------------------
# Modulate ToxMod API (real mode)
# ---------------------------------------------------------------------------

def _call_modulate_api(text: str, context: str = "") -> dict[str, Any] | None:
    """Call real Modulate ToxMod API for sentiment/toxicity analysis."""
    global _last_used, _call_count

    try:
        import httpx

        resp = httpx.post(
            f"{settings.modulate_api_url}/v1/text/analyze",
            headers={
                "Authorization": f"Bearer {settings.modulate_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "text": text[:1000],  # Cap text length
                "analysis_types": ["sentiment", "toxicity"],
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Map Modulate response to our format
        sentiment = data.get("sentiment", {})
        toxicity = data.get("toxicity", {})

        polarity = sentiment.get("score", 0.0)
        subjectivity = toxicity.get("score", 0.0)

        result = {
            "polarity": round(polarity, 3),
            "subjectivity": round(subjectivity, 3),
            "risk_level": _polarity_to_risk(polarity),
            "assessment": sentiment.get("label", "neutral"),
            "context": context,
            "provider": "modulate_api",
            "raw_response": data,
        }

        _last_used = datetime.utcnow()
        _call_count += 1
        _log_analysis(text, result, "modulate_api")
        return result

    except Exception as e:
        print(f"  [modulate_adapter] API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Heuristic sentiment (fallback — always available)
# ---------------------------------------------------------------------------

# Keyword lists for financial anomaly sentiment
_NEGATIVE_KEYWORDS = [
    "fraud", "suspicious", "duplicate", "error", "mismatch", "spike",
    "unauthorized", "anomaly", "discrepancy", "overcharge", "undercharge",
    "leakage", "loss", "violation", "breach", "irregular", "excessive",
    "unexpected", "abnormal", "critical", "severe", "urgent", "escalate",
    "missing", "failed", "incorrect", "invalid", "rejected",
]

_POSITIVE_KEYWORDS = [
    "resolved", "approved", "correct", "verified", "confirmed", "normal",
    "expected", "routine", "standard", "compliant", "accurate", "valid",
    "matched", "reconciled", "cleared",
]

_HIGH_RISK_KEYWORDS = [
    "fraud", "unauthorized", "breach", "violation", "critical", "severe",
    "duplicate refund", "revenue leakage", "manual credit",
]


def _heuristic_sentiment(text: str, context: str = "") -> dict[str, Any]:
    """Keyword-based sentiment analysis for financial operations text."""
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    total_words = max(len(words), 1)

    neg_count = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)
    pos_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text_lower)
    high_risk_count = sum(1 for kw in _HIGH_RISK_KEYWORDS if kw in text_lower)

    # Polarity: -1 (very negative) to +1 (very positive)
    raw_polarity = (pos_count - neg_count) / max(pos_count + neg_count, 1)
    polarity = max(-1.0, min(1.0, raw_polarity))

    # Subjectivity: 0 (objective/factual) to 1 (subjective/opinion)
    # Financial evidence tends to be factual, so base subjectivity is low
    opinion_words = sum(1 for w in words if w in ["seems", "appears", "likely", "possibly", "maybe", "probably", "suspect", "believe"])
    subjectivity = min(1.0, opinion_words / total_words * 10 + 0.1)

    # Risk boost for high-risk keywords
    if high_risk_count > 0:
        polarity = min(polarity, -0.3)  # Ensure negative

    risk_level = _polarity_to_risk(polarity)

    # Generate assessment text
    if polarity < -0.5:
        assessment = "Strongly negative — high-risk language detected"
    elif polarity < -0.2:
        assessment = "Negative — anomaly indicators present"
    elif polarity < 0.2:
        assessment = "Neutral — standard operational language"
    elif polarity < 0.5:
        assessment = "Slightly positive — resolution indicators"
    else:
        assessment = "Positive — resolved/confirmed language"

    return {
        "polarity": round(polarity, 3),
        "subjectivity": round(subjectivity, 3),
        "risk_level": risk_level,
        "assessment": assessment,
        "context": context,
        "provider": "heuristic",
        "keyword_hits": {
            "negative": neg_count,
            "positive": pos_count,
            "high_risk": high_risk_count,
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _polarity_to_risk(polarity: float, anomaly_type: str = "") -> str:
    """Convert polarity score to a risk level label."""
    # Certain anomaly types are inherently higher risk
    type_boost = 0.0
    if anomaly_type in ("duplicate_refund", "manual_credit"):
        type_boost = -0.15
    elif anomaly_type == "refund_spike":
        type_boost = -0.1

    adjusted = polarity + type_boost

    if adjusted < -0.5:
        return "high"
    elif adjusted < -0.2:
        return "elevated"
    elif adjusted < 0.2:
        return "neutral"
    else:
        return "low"


def _generate_assessment(
    polarity: float,
    subjectivity: float,
    risk_level: str,
    anomaly_type: str,
    evidence_count: int,
) -> str:
    """Generate a human-readable assessment of the sentiment analysis."""
    parts = []

    if risk_level == "high":
        parts.append(f"High-risk sentiment detected across {evidence_count} evidence items")
    elif risk_level == "elevated":
        parts.append(f"Elevated risk indicators in {evidence_count} evidence items")
    else:
        parts.append(f"Standard risk level across {evidence_count} evidence items")

    if polarity < -0.3:
        parts.append("Language suggests potential fraud or significant billing error")
    elif polarity < 0:
        parts.append("Anomaly-related language present but not strongly negative")
    else:
        parts.append("Language is neutral to positive")

    if subjectivity > 0.5:
        parts.append("Evidence contains subjective assessments — verify with data")
    else:
        parts.append("Evidence is primarily factual")

    return ". ".join(parts) + "."


def _empty_result(context: str = "") -> dict[str, Any]:
    """Return empty sentiment result for missing text."""
    return {
        "polarity": 0.0,
        "subjectivity": 0.0,
        "risk_level": "neutral",
        "assessment": "No text provided for analysis",
        "context": context,
        "provider": "none",
    }


def _log_analysis(text: str, result: dict[str, Any], provider: str) -> None:
    """Log analysis for observability."""
    _analysis_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "provider": provider,
        "text_preview": text[:100],
        "polarity": result.get("polarity", 0),
        "risk_level": result.get("risk_level", "neutral"),
    })


def get_analysis_log() -> list[dict[str, Any]]:
    """Return the sentiment analysis log."""
    return list(_analysis_log)


def reset() -> None:
    """Reset adapter state."""
    global _last_used, _call_count, _analysis_log
    _last_used = None
    _call_count = 0
    _analysis_log = []
