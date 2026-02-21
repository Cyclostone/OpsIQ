"""Analyst Agent — orchestrates business Q&A: question → SQL → chart → answer.

Flow:
  1. Match question to SQL template (sql_tool)
  2. Execute query against DuckDB
  3. Build chart from results (chart_tool + Lightdash config)
  4. Generate answer summary (template-based, LLM-enhanced if available)
  5. Generate follow-up suggestions
  6. Return AnalystResponse
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.schemas import AnalystResponse, Confidence
from app.tools.sql_tool import execute_query
from app.tools.chart_tool import build_chart
from app.adapters.llm_client import rewrite_answer, generate_follow_ups
from app.adapters.lightdash_adapter import get_metric_definitions


def ask(question: str) -> AnalystResponse:
    """Process a business question and return a structured response.

    Args:
        question: Natural-language business question

    Returns:
        AnalystResponse with answer, chart, SQL, confidence, follow-ups
    """
    print(f"[analyst_agent] Question: {question}")

    # Step 1: Match and execute SQL
    result = execute_query(question)
    matched = result["matched"]
    print(f"  Template matched: {matched} ({result['name']})")

    # Step 2: Build answer
    if matched and result["data"]:
        raw_answer = _build_answer(result)
        confidence = Confidence.high
    elif matched:
        raw_answer = f"{result['description']}. No data found for the current period."
        confidence = Confidence.medium
    else:
        raw_answer = result["answer_template"]
        confidence = Confidence.low

    # Step 3: Optional LLM enhancement
    answer = rewrite_answer(raw_answer, question)

    # Step 4: Build chart
    chart_data = None
    chart_type = result.get("chart_type", "bar")
    if result.get("chart_data"):
        # Find related Lightdash metric for chart config
        metric_name = _find_related_metric(result["name"])
        chart_data = build_chart(
            chart_data=result["chart_data"],
            chart_type=chart_type,
            title=result["description"],
            metric_name=metric_name,
        )

    # Step 5: Follow-ups
    follow_ups = generate_follow_ups(question, answer)

    print(f"  Confidence: {confidence.value}")
    print(f"  Chart: {'yes' if chart_data else 'no'}")
    print(f"  Follow-ups: {len(follow_ups)}")

    return AnalystResponse(
        question=question,
        answer=answer,
        sql_used=result["sql"],
        chart_data=chart_data,
        chart_type=chart_type,
        confidence=confidence,
        follow_ups=follow_ups,
        timestamp=datetime.utcnow(),
    )


def _build_answer(result: dict[str, Any]) -> str:
    """Build a human-readable answer from query results."""
    template = result.get("answer_template", "")
    data = result.get("data", [])

    if not data:
        return template or "No data available."

    # Try to fill template with first row of data
    if template and data:
        try:
            first_row = data[0]
            # Convert values to float where possible for formatting
            fmt_row = {}
            for k, v in first_row.items():
                try:
                    fmt_row[k] = float(v)
                except (ValueError, TypeError):
                    fmt_row[k] = v
            return template.format(**fmt_row)
        except (KeyError, IndexError, ValueError):
            pass

    # Fallback: build answer from data
    if len(data) == 1:
        row = data[0]
        parts = [f"{k}: {v}" for k, v in row.items()]
        return f"{result['description']}. Results: {', '.join(parts)}."
    else:
        summary = f"{result['description']}. Found {len(data)} results."
        # Show top 3 rows
        for i, row in enumerate(data[:3]):
            parts = [f"{k}={v}" for k, v in row.items()]
            summary += f"\n  {i+1}. {', '.join(parts)}"
        return summary


def _find_related_metric(template_name: str) -> str | None:
    """Map a SQL template name to a Lightdash metric name."""
    mapping = {
        "revenue_down_analysis": "monthly_revenue",
        "refund_changes": "refunds_by_region",
        "refunds_by_region": "refunds_by_region",
        "underbilling_by_tier": "underbilling_by_tier",
        "revenue_trend": "monthly_revenue",
    }
    return mapping.get(template_name)
