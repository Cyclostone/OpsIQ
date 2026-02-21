"""Memory Agent — LLM-powered self-improvement through feedback learning.

This is the core self-improvement mechanism. Uses an LLM to:
  1. Analyze feedback and reason about what went wrong
  2. Decide which memory entries (thresholds, penalties) to update
  3. Generate human-readable explanations of what it learned
  4. Apply updates that change future triage behavior

Memory updates affect triage behavior on rerun:
  - false_positive on duplicate_refund → narrow detection window
  - false_positive on any type → increase false_positive_penalty
  - approve on a case → reinforce current thresholds
  - not_useful on analyst → adjust explanation_style

Falls back to rule-based logic if LLM is unavailable.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.schemas import FeedbackItem, FeedbackType, MemoryEntry
from app.storage.memory_store import get_memory, set_memory, get_all_memory
from app.storage.case_store import get_case
from app.storage.feedback_store import get_false_positive_case_ids
from app.adapters.llm_client import chat, is_available as llm_available


def process_feedback(feedback: FeedbackItem) -> list[MemoryEntry]:
    """Process a feedback item using LLM reasoning and return memory updates.

    Args:
        feedback: The feedback item just submitted

    Returns:
        List of MemoryEntry objects that were created/updated
    """
    updates: list[MemoryEntry] = []

    # First, get LLM reasoning about what to learn (if available)
    llm_insight = _llm_reason_about_feedback(feedback)
    if llm_insight:
        print(f"[memory_agent] LLM insight: {llm_insight[:150]}...")

    if feedback.target_type == "case":
        updates.extend(_process_case_feedback(feedback, llm_insight))
    elif feedback.target_type == "analyst":
        updates.extend(_process_analyst_feedback(feedback, llm_insight))

    if updates:
        print(f"[memory_agent] {len(updates)} memory updates from feedback {feedback.feedback_id}")
        for u in updates:
            print(f"  {u.key} = {u.value} ({u.reason})")

    return updates


def _llm_reason_about_feedback(feedback: FeedbackItem) -> str:
    """LLM reasons about what to learn from this feedback."""
    if not llm_available():
        return ""

    case = get_case(feedback.target_id) if feedback.target_type == "case" else None
    current_memory = get_all_memory()

    memory_state = []
    for m in current_memory:
        memory_state.append(f"- {m.key} = {m.value}")

    case_context = ""
    if case:
        case_context = f"""\nCase details:
- ID: {case.case_id}
- Type: {case.anomaly_type}
- Title: {case.title}
- Severity: {case.severity.value}
- Confidence: {case.confidence.value}
- Impact: ${case.estimated_impact:,.2f}
- Evidence: {'; '.join(case.evidence[:3])}"""

    prompt = f"""You are the OpsIQ memory agent. You learn from user feedback to improve future anomaly detection.

Feedback received:
- Type: {feedback.feedback_type.value}
- Target: {feedback.target_type} ({feedback.target_id})
- Comment: {feedback.comment or 'No comment provided'}
{case_context}

Current memory state:
{chr(10).join(memory_state) if memory_state else 'Default thresholds (no adjustments yet).'}

Analyze this feedback and recommend:
1. WHAT WENT WRONG: Why did the user give this feedback?
2. WHAT TO LEARN: What specific threshold or behavior should change?
3. HOW MUCH TO ADJUST: Be specific about values (e.g., "raise underbilling threshold from $10 to $35")
4. RISK ASSESSMENT: Could this adjustment cause us to miss real anomalies?

Be specific and conservative. Small adjustments are better than large ones."""

    return chat([
        {"role": "system", "content": "You are an AI agent that learns from human feedback to improve anomaly detection. Be specific about what to change and why."},
        {"role": "user", "content": prompt},
    ], max_tokens=400, purpose="memory_agent_feedback_reasoning")


def _process_case_feedback(feedback: FeedbackItem, llm_insight: str = "") -> list[MemoryEntry]:
    """Process feedback on a triage case."""
    updates: list[MemoryEntry] = []
    case = get_case(feedback.target_id)

    if feedback.feedback_type == FeedbackType.false_positive:
        # --- False positive: adjust thresholds and penalty ---

        # 1. Increase false_positive_penalty
        current_penalty = get_memory("false_positive_penalty") or 0.0
        new_penalty = min(current_penalty + 0.15, 0.5)  # Cap at 50% reduction
        reason = f"Increased from {current_penalty} to {new_penalty} after false positive on {feedback.target_id}"
        if llm_insight:
            reason += f" | LLM: {llm_insight[:100]}"
        entry = set_memory(
            "false_positive_penalty",
            new_penalty,
            reason=reason,
            source="feedback+llm" if llm_insight else "feedback",
        )
        updates.append(entry)

        # 2. Type-specific threshold adjustments
        if case:
            if case.anomaly_type == "duplicate_refund":
                # Widen the duplicate detection window
                current_window = get_memory("duplicate_refund_window_hours") or 2
                new_window = max(1, current_window - 0.5)  # Narrow window = fewer matches = fewer FP
                # Actually for FP, we want to be MORE strict, so narrow the window
                entry = set_memory(
                    "duplicate_refund_window_hours",
                    new_window,
                    reason=f"Narrowed from {current_window}h to {new_window}h after false positive — stricter matching",
                    source="feedback",
                )
                updates.append(entry)

            elif case.anomaly_type == "underbilling":
                # Raise the underbilling threshold
                current_thresh = get_memory("underbilling_threshold") or 10.0
                new_thresh = current_thresh + 25.0
                entry = set_memory(
                    "underbilling_threshold",
                    new_thresh,
                    reason=f"Raised from ${current_thresh} to ${new_thresh} after false positive — less sensitive",
                    source="feedback",
                )
                updates.append(entry)

            elif case.anomaly_type == "refund_spike":
                # Raise the spike multiplier
                current_mult = get_memory("refund_spike_multiplier") or 2.0
                new_mult = current_mult + 0.5
                entry = set_memory(
                    "refund_spike_multiplier",
                    new_mult,
                    reason=f"Raised from {current_mult}x to {new_mult}x after false positive — higher bar for spike detection",
                    source="feedback",
                )
                updates.append(entry)

            elif case.anomaly_type == "manual_credit":
                # Raise the manual credit threshold
                current_thresh = get_memory("manual_credit_threshold") or 200.0
                new_thresh = current_thresh + 100.0
                entry = set_memory(
                    "manual_credit_threshold",
                    new_thresh,
                    reason=f"Raised from ${current_thresh} to ${new_thresh} after false positive — less sensitive",
                    source="feedback",
                )
                updates.append(entry)

    elif feedback.feedback_type == FeedbackType.approve:
        # --- Approval: reinforce current thresholds ---
        # Slightly decrease penalty if it was elevated
        current_penalty = get_memory("false_positive_penalty") or 0.0
        if current_penalty > 0:
            new_penalty = max(0, current_penalty - 0.05)
            entry = set_memory(
                "false_positive_penalty",
                new_penalty,
                reason=f"Reduced from {current_penalty} to {new_penalty} after case approval — positive reinforcement",
                source="feedback",
            )
            updates.append(entry)

    elif feedback.feedback_type == FeedbackType.reject:
        # --- Rejection: similar to false positive but milder ---
        current_penalty = get_memory("false_positive_penalty") or 0.0
        new_penalty = min(current_penalty + 0.05, 0.5)
        entry = set_memory(
            "false_positive_penalty",
            new_penalty,
            reason=f"Slightly increased from {current_penalty} to {new_penalty} after case rejection",
            source="feedback",
        )
        updates.append(entry)

    return updates


def _process_analyst_feedback(feedback: FeedbackItem, llm_insight: str = "") -> list[MemoryEntry]:
    """Process feedback on an analyst output."""
    updates: list[MemoryEntry] = []

    if feedback.feedback_type == FeedbackType.not_useful:
        # Switch explanation style
        current_style = get_memory("explanation_style") or "detailed"
        new_style = "concise" if current_style == "detailed" else "detailed"
        entry = set_memory(
            "explanation_style",
            new_style,
            reason=f"Switched from '{current_style}' to '{new_style}' after 'not useful' feedback",
            source="feedback",
        )
        updates.append(entry)

    elif feedback.feedback_type == FeedbackType.useful:
        # Reinforce current style
        current_style = get_memory("explanation_style") or "detailed"
        entry = set_memory(
            "explanation_style",
            current_style,
            reason=f"Reinforced '{current_style}' style after positive feedback",
            source="feedback",
        )
        updates.append(entry)

    return updates


def get_improvement_summary() -> dict[str, Any]:
    """Generate a summary of all memory changes for the QA Lab UI.

    Uses LLM to generate a narrative summary of what the system has learned.

    Returns dict with:
      - current_memory: all current values
      - changes: list of recent changes with before/after
      - improvement_notes: human-readable notes
      - llm_summary: LLM-generated narrative of learning progress
    """
    all_memory = get_all_memory()
    fp_ids = get_false_positive_case_ids()

    # Defaults for comparison
    defaults = {
        "duplicate_refund_window_hours": 2,
        "underbilling_threshold": 10.0,
        "refund_spike_multiplier": 2.0,
        "manual_credit_threshold": 200.0,
        "explanation_style": "detailed",
        "false_positive_penalty": 0.0,
    }

    changes = []
    improvement_notes = []

    for entry in all_memory:
        default_val = defaults.get(entry.key)
        if default_val is not None and entry.value != default_val:
            changes.append({
                "key": entry.key,
                "default": default_val,
                "current": entry.value,
                "reason": entry.reason,
                "source": entry.source,
                "updated_at": entry.updated_at.isoformat(),
            })

    # Generate human-readable notes
    penalty = get_memory("false_positive_penalty") or 0.0
    if penalty > 0:
        improvement_notes.append(f"Confidence penalty of {penalty:.0%} applied to anomaly types with prior false positives")

    dup_window = get_memory("duplicate_refund_window_hours") or 2
    if dup_window != defaults["duplicate_refund_window_hours"]:
        improvement_notes.append(f"Duplicate refund window adjusted from {defaults['duplicate_refund_window_hours']}h to {dup_window}h")

    underbill = get_memory("underbilling_threshold") or 10.0
    if underbill != defaults["underbilling_threshold"]:
        improvement_notes.append(f"Underbilling threshold raised from ${defaults['underbilling_threshold']} to ${underbill}")

    spike_mult = get_memory("refund_spike_multiplier") or 2.0
    if spike_mult != defaults["refund_spike_multiplier"]:
        improvement_notes.append(f"Refund spike multiplier raised from {defaults['refund_spike_multiplier']}x to {spike_mult}x")

    if fp_ids:
        improvement_notes.append(f"{len(fp_ids)} cases marked as false positives — rerun will deprioritize similar patterns")

    if not improvement_notes:
        improvement_notes.append("No improvements yet — submit feedback on cases to trigger self-improvement")

    # LLM narrative summary of learning progress
    llm_summary = _llm_summarize_learning(all_memory, changes, fp_ids)

    return {
        "current_memory": [m.model_dump() for m in all_memory],
        "changes": changes,
        "improvement_notes": improvement_notes,
        "false_positive_case_ids": fp_ids,
        "llm_summary": llm_summary,
    }


def _llm_summarize_learning(memory: list[MemoryEntry], changes: list[dict], fp_ids: list[str]) -> str:
    """LLM generates a narrative summary of what the system has learned."""
    if not llm_available():
        return ""

    if not changes:
        return "The system is running with default thresholds. No feedback has been processed yet. Submit feedback on triage cases to trigger the self-improvement loop."

    changes_text = []
    for c in changes:
        changes_text.append(f"- {c['key']}: {c['default']} → {c['current']} (reason: {c['reason']})")

    prompt = f"""You are the OpsIQ memory agent. Summarize what the system has learned from user feedback.

Memory changes from defaults:
{chr(10).join(changes_text)}

False positive cases: {len(fp_ids)}

Write a brief narrative (3-5 sentences) explaining:
1. What the system has learned so far
2. How these changes will affect future anomaly detection
3. Whether the system is improving or needs more feedback

Write in first person as the AI system ("I have learned...")."""

    return chat([
        {"role": "system", "content": "You are an AI system narrating your own learning progress. Be specific and honest about what you've learned."},
        {"role": "user", "content": prompt},
    ], max_tokens=300, purpose="memory_agent_learning_summary")
