"""LLM Client — AI reasoning backbone for OpsIQ agents.

Provider priority:
  1. Groq (free tier, Llama 3.3 70B, OpenAI-compatible) — preferred
  2. OpenAI (GPT-4o-mini) — fallback if Groq key not set
  3. Deterministic templates — fallback if no API key at all

Used by:
  - Orchestrator: reason about signals, decide investigation strategy
  - Evaluator: analyze run quality, generate improvement suggestions
  - Memory Agent: reason about what to learn from feedback
  - Analyst: enhance answers, generate follow-ups
  - Triage: enhance case explanations

Setup:
  1. Go to https://console.groq.com → Sign up (free, no credit card)
  2. API Keys → Create API Key
  3. Add to .env: GROQ_API_KEY=gsk_...
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import settings


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------
_last_used: datetime | None = None
_call_count: int = 0
_reasoning_log: list[dict[str, Any]] = []


def is_available() -> bool:
    return settings.llm_available


def get_provider() -> str:
    return settings.llm_provider


def get_model() -> str:
    if settings.llm_provider == "groq":
        return settings.groq_model
    elif settings.llm_provider == "openai":
        return settings.openai_model
    return "none"


def get_status() -> dict[str, Any]:
    return {
        "available": is_available(),
        "provider": get_provider(),
        "model": get_model() if is_available() else "none (deterministic fallback)",
        "call_count": _call_count,
        "last_used": _last_used.isoformat() if _last_used else None,
        "reasoning_steps": len(_reasoning_log),
    }


def get_reasoning_log() -> list[dict[str, Any]]:
    """Return the log of all LLM reasoning calls for observability."""
    return list(_reasoning_log)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def enhance_explanation(case_title: str, evidence: list[str], anomaly_type: str) -> str:
    """Generate a natural-language explanation for a triage case.

    Falls back to a template-based explanation if LLM is unavailable.
    """
    if is_available():
        return _llm_explain(case_title, evidence, anomaly_type)
    return _template_explain(case_title, evidence, anomaly_type)


def rewrite_answer(raw_answer: str, question: str) -> str:
    """Rewrite an analyst answer for clarity and conciseness.

    Falls back to returning the raw answer if LLM is unavailable.
    """
    if is_available():
        return _llm_rewrite(raw_answer, question)
    return raw_answer


def generate_follow_ups(question: str, answer: str) -> list[str]:
    """Generate follow-up question suggestions.

    Falls back to deterministic suggestions based on keywords.
    """
    if is_available():
        return _llm_follow_ups(question, answer)
    return _template_follow_ups(question)


# ---------------------------------------------------------------------------
# Generic chat — the core LLM call used by all agents
# ---------------------------------------------------------------------------

def chat(messages: list[dict[str, str]], max_tokens: int = 500, purpose: str = "") -> str:
    """Send a chat completion request to the configured LLM provider.

    Args:
        messages: OpenAI-format messages [{"role": ..., "content": ...}]
        max_tokens: Max response tokens
        purpose: Description of why this call is being made (for logging)

    Returns:
        LLM response text, or empty string on failure.
    """
    if not is_available():
        return ""

    provider = get_provider()
    if provider == "groq":
        return _call_groq(messages, max_tokens, purpose)
    elif provider == "openai":
        return _call_openai(messages, max_tokens, purpose)
    return ""


def _call_groq(messages: list[dict[str, str]], max_tokens: int = 500, purpose: str = "") -> str:
    """Call Groq API (OpenAI-compatible). Free tier: Llama 3.3 70B."""
    global _last_used, _call_count

    try:
        import httpx

        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        _last_used = datetime.utcnow()
        _call_count += 1
        result = resp.json()["choices"][0]["message"]["content"].strip()
        _log_reasoning(purpose, messages, result, "groq")
        return result
    except Exception as e:
        print(f"  [llm_client] Groq call failed: {e}")
        return ""


def _call_openai(messages: list[dict[str, str]], max_tokens: int = 500, purpose: str = "") -> str:
    """Call OpenAI API. Fallback if Groq not configured."""
    global _last_used, _call_count

    try:
        import httpx

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        _last_used = datetime.utcnow()
        _call_count += 1
        result = resp.json()["choices"][0]["message"]["content"].strip()
        _log_reasoning(purpose, messages, result, "openai")
        return result
    except Exception as e:
        print(f"  [llm_client] OpenAI call failed: {e}")
        return ""


def _log_reasoning(purpose: str, messages: list[dict[str, str]], result: str, provider: str) -> None:
    """Log reasoning call for observability in QA Lab."""
    _reasoning_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "provider": provider,
        "model": get_model(),
        "purpose": purpose,
        "prompt_preview": messages[-1]["content"][:200] if messages else "",
        "response_preview": result[:300],
        "tokens_approx": len(result.split()),
    })


def _llm_explain(case_title: str, evidence: list[str], anomaly_type: str) -> str:
    evidence_text = "\n".join(f"- {e}" for e in evidence)
    result = chat([
        {"role": "system", "content": "You are a concise financial operations analyst. Explain anomalies in 2-3 sentences."},
        {"role": "user", "content": f"Explain this {anomaly_type} anomaly:\nTitle: {case_title}\nEvidence:\n{evidence_text}"},
    ], purpose="explain_anomaly")
    return result if result else _template_explain(case_title, evidence, anomaly_type)


def _llm_rewrite(raw_answer: str, question: str) -> str:
    result = chat([
        {"role": "system", "content": "Rewrite this analyst answer to be clear and concise. Keep all data points."},
        {"role": "user", "content": f"Question: {question}\nRaw answer: {raw_answer}"},
    ], purpose="rewrite_answer")
    return result if result else raw_answer


def _llm_follow_ups(question: str, answer: str) -> list[str]:
    result = chat([
        {"role": "system", "content": "Suggest 3 follow-up business questions. Return one per line, no numbering."},
        {"role": "user", "content": f"Original question: {question}\nAnswer: {answer}"},
    ], purpose="generate_follow_ups")
    if result:
        return [line.strip() for line in result.strip().split("\n") if line.strip()][:3]
    return _template_follow_ups(question)


# ---------------------------------------------------------------------------
# Deterministic fallbacks
# ---------------------------------------------------------------------------

_EXPLAIN_TEMPLATES = {
    "duplicate_refund": "A duplicate refund was detected for the same customer and amount within a short time window. This may indicate a processing error or potential fraud that requires immediate investigation.",
    "underbilling": "The customer was billed less than the expected amount based on their subscription tier. This represents direct revenue leakage that should be corrected in the next billing cycle.",
    "tier_mismatch": "The invoice was generated using a different plan tier than the customer's active subscription. This billing configuration error is causing systematic underbilling.",
    "refund_spike": "An unusual spike in refund volume was detected in a specific region, significantly exceeding the historical baseline. This may indicate a service issue, policy abuse, or systematic billing problem.",
    "manual_credit": "A large manual credit was issued outside the normal refund workflow. Manual credits above the threshold require additional audit review to verify authorization.",
}


def _template_explain(case_title: str, evidence: list[str], anomaly_type: str) -> str:
    base = _EXPLAIN_TEMPLATES.get(anomaly_type, "An anomaly was detected that requires investigation.")
    return f"{base} Evidence: {'; '.join(evidence[:2])}."


def _template_follow_ups(question: str) -> list[str]:
    q_lower = question.lower()

    if "revenue" in q_lower:
        return [
            "Which customers contributed most to the revenue change?",
            "How does this compare to the same period last quarter?",
            "What is the breakdown by plan tier?",
        ]
    elif "refund" in q_lower:
        return [
            "Which region has the highest refund rate?",
            "Are there any duplicate refunds in the data?",
            "What are the top refund reasons this month?",
        ]
    elif "underbilling" in q_lower or "billing" in q_lower:
        return [
            "Which plan tiers are most affected by underbilling?",
            "What is the total billing gap this month?",
            "How many customers have tier mismatches?",
        ]
    else:
        return [
            "What are the top anomalies this week?",
            "Show revenue trend for the last 30 days",
            "Which region has the most billing exceptions?",
        ]


def reset() -> None:
    global _last_used, _call_count, _reasoning_log
    _last_used = None
    _call_count = 0
    _reasoning_log = []
