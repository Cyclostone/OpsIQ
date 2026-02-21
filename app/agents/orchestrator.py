"""Orchestrator — the top-level autonomous AI agent pipeline.

This is the brain of OpsIQ. It uses an LLM (Groq/OpenAI) to:
  1. Analyze incoming signals and reason about investigation strategy
  2. Decide which anomalies to prioritize based on context
  3. Generate executive summaries of findings
  4. Reason about what actions to take
  5. Produce a full reasoning trace for observability

Full autonomous flow:
  1. Monitor: ingest signals from Datadog / Lightdash / internal
  2. Reason: LLM analyzes signals and decides investigation strategy
  3. Triage: run anomaly detection → scoring → case generation
  4. Synthesize: LLM reviews cases and generates executive summary
  5. Action: create case actions + alert via Airia
  6. Trace: log the full run with reasoning for observability

This is the single entry point for `/monitor/run` and the demo flow.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import (
    AutonomousRunResult, SignalEvent, TraceRecord, TriageCase,
)
from app.agents.monitor_agent import fetch_all_signals, pick_trigger_signal, enrich_signal
from app.agents.triage_agent import run_triage
from app.adapters import airia_adapter, datadog_adapter, lightdash_adapter, modulate_adapter
from app.adapters.llm_client import chat, is_available as llm_available
from app.storage.trace_store import save_trace
from app.storage.case_store import clear_cases
from app.storage.memory_store import get_all_memory


# ---------------------------------------------------------------------------
# LLM Reasoning helpers
# ---------------------------------------------------------------------------

def _llm_analyze_signals(signals: list[SignalEvent], memory: list[Any]) -> str:
    """LLM reasons about incoming signals and decides investigation strategy."""
    if not llm_available():
        return "LLM unavailable — using rule-based signal prioritization."

    signal_summaries = []
    for s in signals[:10]:  # Cap to avoid token overflow
        signal_summaries.append(
            f"- [{s.severity.value.upper()}] {s.signal_type} from {s.source}: {s.related_entity} (payload: {json.dumps(s.payload)[:150]})"
        )

    memory_notes = []
    for m in memory:
        memory_notes.append(f"- {m.key} = {m.value} (reason: {m.reason})")

    prompt = f"""You are the OpsIQ orchestrator agent — an autonomous AI that investigates billing anomalies.

You have received {len(signals)} signals from monitoring sources (Datadog, Lightdash, internal).

Signals:
{chr(10).join(signal_summaries) if signal_summaries else 'No signals received.'}

Memory (learned from past feedback):
{chr(10).join(memory_notes) if memory_notes else 'No memory entries yet.'}

Analyze these signals and provide:
1. PRIORITY ASSESSMENT: Which signal is most urgent and why?
2. INVESTIGATION STRATEGY: What should we look for during triage?
3. RISK FACTORS: What patterns or thresholds should we watch for?
4. CONTEXT: How does our learned memory affect this investigation?

Be concise and specific. Focus on actionable reasoning."""

    return chat([
        {"role": "system", "content": "You are an autonomous billing operations AI agent. You reason about signals, decide investigation priorities, and explain your thinking clearly."},
        {"role": "user", "content": prompt},
    ], max_tokens=600, purpose="orchestrator_signal_analysis")


def _llm_synthesize_cases(cases: list[TriageCase], signal: SignalEvent, reasoning: str) -> str:
    """LLM reviews triage results and generates executive summary."""
    if not llm_available():
        total_impact = sum(c.estimated_impact for c in cases)
        return f"Found {len(cases)} anomalies with ${total_impact:,.2f} total estimated impact."

    case_summaries = []
    for c in cases[:8]:
        case_summaries.append(
            f"- [{c.severity.value.upper()}] {c.title} | Impact: ${c.estimated_impact:,.2f} | Confidence: {c.confidence.value} | Action: {c.recommended_action}"
        )

    prompt = f"""You are the OpsIQ orchestrator agent. You just completed an autonomous investigation.

Trigger signal: {signal.signal_id} ({signal.source}, {signal.severity.value})

Your earlier reasoning:
{reasoning[:500]}

Triage results ({len(cases)} cases found):
{chr(10).join(case_summaries) if case_summaries else 'No anomalies detected.'}

Provide an EXECUTIVE SUMMARY:
1. KEY FINDINGS: What are the most important anomalies found?
2. TOTAL RISK: Aggregate the financial impact and urgency.
3. RECOMMENDED ACTIONS: What should the finance team do immediately?
4. CONFIDENCE ASSESSMENT: How confident are you in these findings?

Be concise. This summary will be shown to the operations team."""

    return chat([
        {"role": "system", "content": "You are an autonomous billing operations AI agent producing an executive summary of your investigation findings."},
        {"role": "user", "content": prompt},
    ], max_tokens=600, purpose="orchestrator_executive_summary")


def _llm_decide_actions(cases: list[TriageCase]) -> str:
    """LLM reasons about what actions to take for the cases."""
    if not llm_available():
        return "Using rule-based action assignment."

    case_summaries = []
    for c in cases[:5]:
        case_summaries.append(
            f"- {c.case_id}: {c.title} (severity={c.severity.value}, impact=${c.estimated_impact:,.2f})"
        )

    prompt = f"""You are the OpsIQ orchestrator. Based on these triage cases, decide what actions to take:

{chr(10).join(case_summaries)}

For each case, decide:
1. Should we create a remediation workflow? (via Airia)
2. Should we send an alert to the finance team?
3. Should we create an approval task for a manager?
4. What is the urgency level?

Be specific about which cases need which actions and why."""

    return chat([
        {"role": "system", "content": "You are an autonomous AI agent deciding what remediation actions to take for billing anomalies."},
        {"role": "user", "content": prompt},
    ], max_tokens=400, purpose="orchestrator_action_decision")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_autonomous(signal: SignalEvent | None = None) -> AutonomousRunResult:
    """Execute the full autonomous investigation pipeline with LLM reasoning.

    Args:
        signal: Optional pre-selected signal. If None, the monitor agent
                picks the highest-priority signal automatically.

    Returns:
        AutonomousRunResult with cases, actions, trace, reasoning, and sponsor activity.
    """
    run_id = f"RUN-{uuid.uuid4().hex[:8]}"
    start_time = time.time()
    steps: list[str] = []
    tools_called: list[str] = []
    actions: list[dict[str, Any]] = []
    sponsor_activity: dict[str, Any] = {}
    reasoning_trace: dict[str, str] = {}

    print(f"\n{'='*60}")
    print(f"[orchestrator] Autonomous run {run_id} starting...")
    print(f"  LLM: {'ACTIVE (' + str(llm_available()) + ')' if llm_available() else 'FALLBACK (deterministic)'}")
    print(f"{'='*60}\n")

    # --- Step 1: Monitor — ingest signals ---
    steps.append("ingest_signals")
    tools_called.append("datadog_adapter")
    tools_called.append("lightdash_adapter")

    if signal is None:
        print("[orchestrator] Step 1: Fetching signals from all sources...")
        all_signals = fetch_all_signals()
        signal = pick_trigger_signal(all_signals)
    else:
        all_signals = [signal]
        print(f"[orchestrator] Step 1: Using provided signal {signal.signal_id}")

    if signal is None:
        print("[orchestrator] No signals found. Aborting.")
        return AutonomousRunResult(run_id=run_id, cases=[], actions=[], sponsor_activity={})

    sponsor_activity["datadog"] = {
        "action": "signal_ingestion",
        "signal_id": signal.signal_id if signal.source == "datadog" else "N/A",
        "signals_fetched": True,
    }

    # --- Step 2: LLM Reasoning — analyze signals & decide strategy ---
    steps.append("llm_signal_analysis")
    tools_called.append("llm_client")
    print(f"\n[orchestrator] Step 2: LLM analyzing {len(all_signals)} signals...")
    memory = get_all_memory()
    signal_reasoning = _llm_analyze_signals(all_signals, memory)
    reasoning_trace["signal_analysis"] = signal_reasoning
    print(f"  LLM reasoning: {signal_reasoning[:150]}...")

    # --- Step 3: Enrich signal ---
    steps.append("enrich_signal")
    print(f"\n[orchestrator] Step 3: Enriching signal {signal.signal_id}...")
    enrichment = enrich_signal(signal)
    print(f"  Enrichment source: {enrichment.get('adapter_context', {}).get('source', 'unknown')}")

    # --- Step 4: Lightdash metric context ---
    steps.append("fetch_metric_context")
    tools_called.append("lightdash_adapter")
    print("\n[orchestrator] Step 4: Fetching Lightdash metric context...")
    metric_defs = lightdash_adapter.get_metric_definitions()
    sponsor_activity["lightdash"] = {
        "action": "metric_context",
        "metrics_loaded": len(metric_defs),
        "signal_id": signal.signal_id if signal.source == "lightdash" else "N/A",
    }
    print(f"  Loaded {len(metric_defs)} metric definitions")

    # --- Step 5: Triage — detect, score, create cases (includes Modulate sentiment) ---
    steps.append("run_triage")
    tools_called.extend(["anomaly_tool", "scoring_tool", "modulate_adapter"])
    print("\n[orchestrator] Step 5: Running triage (with Modulate sentiment)...")
    clear_cases()
    cases = run_triage(run_id)
    print(f"  Generated {len(cases)} cases")

    # Track Modulate sponsor activity
    cases_with_sentiment = sum(1 for c in cases if c.sentiment_score is not None)
    sponsor_activity["modulate"] = {
        "action": "sentiment_analysis",
        "mode": modulate_adapter.get_mode().value,
        "cases_analyzed": cases_with_sentiment,
        "total_analyses": modulate_adapter.get_status()["call_count"],
    }

    # --- Step 6: LLM Synthesis — review cases & generate executive summary ---
    steps.append("llm_synthesis")
    print("\n[orchestrator] Step 6: LLM synthesizing findings...")
    executive_summary = _llm_synthesize_cases(cases, signal, signal_reasoning)
    reasoning_trace["executive_summary"] = executive_summary
    print(f"  Summary: {executive_summary[:150]}...")

    # --- Step 7: LLM Action Decision ---
    steps.append("llm_action_decision")
    print("\n[orchestrator] Step 7: LLM deciding actions...")
    action_reasoning = _llm_decide_actions(cases)
    reasoning_trace["action_decision"] = action_reasoning
    print(f"  Action reasoning: {action_reasoning[:150]}...")

    # --- Step 8: Actions via Airia ---
    steps.append("create_actions")
    tools_called.append("airia_adapter")
    print("\n[orchestrator] Step 8: Creating actions via Airia...")

    # Create case action for top case
    if cases:
        top_case = cases[0]
        case_action = airia_adapter.create_case_action(top_case)
        actions.append(case_action)
        print(f"  Created case action: {case_action['action_id']} for {top_case.case_id}")

    # Create alert for high-severity cases
    high_severity_cases = [c for c in cases if c.severity.value in ("high", "critical")]
    if high_severity_cases:
        total_impact = sum(c.estimated_impact for c in high_severity_cases)
        alert_action = airia_adapter.create_alert_action(
            title=f"OpsIQ Alert: {len(high_severity_cases)} high-severity anomalies detected",
            severity="high",
            message=f"Autonomous triage found {len(high_severity_cases)} high-severity cases with total estimated impact of ${total_impact:,.2f}. Top case: {high_severity_cases[0].title}",
            target="finance-team",
        )
        actions.append(alert_action)
        print(f"  Created alert action: {alert_action['action_id']}")

    # Create approval task for top case if impact > $200
    if cases and cases[0].estimated_impact > 200:
        approval = airia_adapter.create_approval_task(
            title=f"Review: {cases[0].title}",
            description=f"Estimated impact: ${cases[0].estimated_impact:,.2f}. {cases[0].recommended_action}",
            assignee="finance-manager",
            case_id=cases[0].case_id,
        )
        actions.append(approval)
        print(f"  Created approval task: {approval['action_id']}")

    sponsor_activity["airia"] = {
        "action": "workflow_execution",
        "actions_created": len(actions),
        "action_types": list(set(a["action_type"] for a in actions)),
    }

    # --- Step 9: Save trace ---
    steps.append("save_trace")
    duration_ms = int((time.time() - start_time) * 1000)

    trace = TraceRecord(
        run_id=run_id,
        timestamp=datetime.utcnow(),
        trigger_source=signal.signal_id,
        steps=steps,
        tools_called=list(set(tools_called)),
        cases_generated=len(cases),
        actions_created=len(actions),
        eval_summary=executive_summary[:500] if executive_summary else None,
        duration_ms=duration_ms,
    )
    save_trace(trace)

    print(f"\n{'='*60}")
    print(f"[orchestrator] Run {run_id} complete in {duration_ms}ms")
    print(f"  Signal: {signal.signal_id} ({signal.source})")
    print(f"  Cases: {len(cases)}")
    print(f"  Actions: {len(actions)}")
    print(f"  Total impact: ${sum(c.estimated_impact for c in cases):,.2f}")
    print(f"  LLM reasoning steps: {len(reasoning_trace)}")
    print(f"{'='*60}\n")

    return AutonomousRunResult(
        run_id=run_id,
        signal=signal,
        cases=cases,
        actions=actions,
        trace=trace,
        sponsor_activity=sponsor_activity,
        reasoning_trace=reasoning_trace,
    )
