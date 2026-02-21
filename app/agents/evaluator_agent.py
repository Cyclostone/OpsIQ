"""Evaluator Agent — LLM-powered quality assessment of triage runs.

This agent uses an LLM (Groq/OpenAI) to:
  - Analyze triage run output quality with reasoning
  - Assess calibration of confidence scores vs actual outcomes
  - Generate specific, actionable improvement suggestions
  - Score across dimensions: actionability, correctness, specificity

Falls back to rule-based heuristics if LLM is unavailable.
Called after each triage run and after feedback is processed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import EvalScore, TriageCase, CaseStatus
from app.storage.eval_store import save_eval
from app.storage.case_store import get_cases_by_run, get_all_cases
from app.storage.feedback_store import get_false_positive_case_ids, get_feedback_counts
from app.adapters.llm_client import chat, is_available as llm_available


def evaluate_run(run_id: str) -> EvalScore:
    """Evaluate a triage run's output quality using LLM reasoning + heuristics.

    Args:
        run_id: The run to evaluate. If empty, evaluates all current cases.

    Returns:
        EvalScore persisted to eval_store.
    """
    if run_id:
        cases = get_cases_by_run(run_id)
    else:
        cases = get_all_cases()
        run_id = cases[0].run_id if cases else "unknown"

    fp_ids = set(get_false_positive_case_ids())
    fb_counts = get_feedback_counts()

    total = len(cases)
    fp_count = sum(1 for c in cases if c.case_id in fp_ids or c.status == CaseStatus.false_positive)

    # --- Heuristic scores (baseline) ---
    if total == 0:
        actionability, correctness, specificity = 1, 3, 1
    else:
        has_action = sum(1 for c in cases if c.recommended_action)
        has_evidence = sum(1 for c in cases if len(c.evidence) >= 2)
        action_ratio = (has_action + has_evidence) / (2 * total)
        actionability = max(1, min(5, round(action_ratio * 5)))

        fp_rate = fp_count / total
        correctness = max(1, min(5, round((1 - fp_rate) * 5)))

        has_impact = sum(1 for c in cases if c.estimated_impact > 0)
        has_detail = sum(1 for c in cases if len(c.evidence) >= 3)
        spec_ratio = (has_impact + has_detail) / (2 * total)
        specificity = max(1, min(5, round(spec_ratio * 5)))

    # --- LLM-powered calibration analysis ---
    calibration_note = _llm_evaluate_calibration(cases, fp_ids, fb_counts, actionability, correctness, specificity)

    score = EvalScore(
        run_id=run_id,
        actionability=actionability,
        correctness=correctness,
        specificity=specificity,
        calibration_note=calibration_note,
        total_cases=total,
        false_positive_count=fp_count,
        timestamp=datetime.utcnow(),
    )

    saved = save_eval(score)
    print(f"[evaluator] Run {run_id}: actionability={actionability} correctness={correctness} specificity={specificity} FP={fp_count}/{total}")
    return saved


def _llm_evaluate_calibration(
    cases: list[TriageCase],
    fp_ids: set[str],
    fb_counts: dict[str, int],
    actionability: int,
    correctness: int,
    specificity: int,
) -> str:
    """Use LLM to analyze calibration and generate improvement suggestions."""
    if not llm_available():
        return _heuristic_calibration(cases, fp_ids, fb_counts)

    case_summaries = []
    for c in cases[:8]:
        is_fp = c.case_id in fp_ids or c.status == CaseStatus.false_positive
        case_summaries.append(
            f"- {c.case_id}: {c.title} | severity={c.severity.value} | confidence={c.confidence.value} | "
            f"impact=${c.estimated_impact:,.2f} | evidence_count={len(c.evidence)} | "
            f"false_positive={'YES' if is_fp else 'no'}"
        )

    prompt = f"""You are the OpsIQ evaluator agent. Analyze this triage run's quality.

Heuristic scores: actionability={actionability}/5, correctness={correctness}/5, specificity={specificity}/5
False positives: {sum(1 for c in cases if c.case_id in fp_ids or c.status == CaseStatus.false_positive)}/{len(cases)}
Feedback counts: {fb_counts}

Cases:
{chr(10).join(case_summaries) if case_summaries else 'No cases generated.'}

Provide:
1. CALIBRATION ASSESSMENT: Are confidence scores well-calibrated? Are high-confidence cases actually correct?
2. QUALITY ISSUES: What specific problems do you see in the cases?
3. IMPROVEMENT SUGGESTIONS: What specific threshold or rule changes would improve the next run?
4. OVERALL VERDICT: One-sentence summary of run quality.

Be specific and actionable. Reference case IDs where relevant."""

    result = chat([
        {"role": "system", "content": "You are an AI quality evaluator for a billing anomaly detection system. Provide specific, actionable calibration analysis."},
        {"role": "user", "content": prompt},
    ], max_tokens=500, purpose="evaluator_calibration_analysis")

    return result if result else _heuristic_calibration(cases, fp_ids, fb_counts)


def _heuristic_calibration(
    cases: list[TriageCase],
    fp_ids: set[str],
    fb_counts: dict[str, int],
) -> str:
    """Fallback heuristic calibration note."""
    total = len(cases)
    fp_count = sum(1 for c in cases if c.case_id in fp_ids or c.status == CaseStatus.false_positive)
    parts = []
    if fp_count > 0:
        parts.append(f"{fp_count}/{total} cases marked as false positives")
    high_conf_cases = [c for c in cases if c.confidence.value == "high"]
    high_conf_fp = sum(1 for c in high_conf_cases if c.case_id in fp_ids or c.status == CaseStatus.false_positive)
    if high_conf_fp > 0:
        parts.append(f"{high_conf_fp} high-confidence cases were false positives — confidence may be over-calibrated")
    approved = fb_counts.get("approve", 0)
    if approved > 0:
        parts.append(f"{approved} cases approved by user")
    if not parts:
        parts.append("No feedback yet — baseline evaluation")
    return ". ".join(parts)
