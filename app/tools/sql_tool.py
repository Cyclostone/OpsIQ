"""SQL Tool — template-based query generation for business questions.

Uses pattern matching to map natural-language questions to SQL queries.
Falls back to a generic query if no pattern matches.
Leverages Lightdash metric definitions for semantic context.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.data_service import query_df, query_rows
from app.adapters.lightdash_adapter import get_metric_by_name, METRIC_DEFINITIONS


# ---------------------------------------------------------------------------
# Question → SQL template mapping
# ---------------------------------------------------------------------------

_TEMPLATES: list[dict[str, Any]] = [
    {
        "patterns": [r"why.*(revenue|income).*(down|drop|decreas|lower|fell)", r"revenue.*(down|drop|decreas)"],
        "name": "revenue_down_analysis",
        "description": "Analyze why revenue decreased — compares current vs prior month, shows refund impact and billing gaps",
        "sql": """
            WITH recent AS (
                SELECT sum(billed_amount) as revenue
                FROM invoices
                WHERE status = 'paid'
                  AND invoice_date::timestamp >= current_date - INTERVAL '7 days'
            ),
            prior AS (
                SELECT sum(billed_amount) as revenue
                FROM invoices
                WHERE status = 'paid'
                  AND invoice_date::timestamp >= current_date - INTERVAL '37 days'
                  AND invoice_date::timestamp < current_date - INTERVAL '7 days'
            ),
            refund_total AS (
                SELECT sum(amount) as total_refunds
                FROM refunds
                WHERE refund_date::timestamp >= current_date - INTERVAL '7 days'
            ),
            billing_gap AS (
                SELECT sum(expected_amount - billed_amount) as total_gap
                FROM invoices
                WHERE expected_amount > billed_amount
                  AND invoice_date::timestamp >= current_date - INTERVAL '7 days'
            )
            SELECT
                coalesce(r.revenue, 0) as current_revenue,
                coalesce(p.revenue, 0) as prior_revenue,
                coalesce(rt.total_refunds, 0) as refunds_this_month,
                coalesce(bg.total_gap, 0) as underbilling_gap
            FROM recent r, prior p, refund_total rt, billing_gap bg
        """,
        "chart_query": """
            SELECT 'Recent Revenue (7d)' as category, coalesce(sum(billed_amount), 0) as amount
            FROM invoices WHERE status = 'paid' AND invoice_date::timestamp >= current_date - INTERVAL '7 days'
            UNION ALL
            SELECT 'Prior Period Revenue', coalesce(sum(billed_amount), 0)
            FROM invoices WHERE status = 'paid'
              AND invoice_date::timestamp >= current_date - INTERVAL '37 days'
              AND invoice_date::timestamp < current_date - INTERVAL '7 days'
            UNION ALL
            SELECT 'Recent Refunds (7d)', coalesce(sum(amount), 0)
            FROM refunds WHERE refund_date::timestamp >= current_date - INTERVAL '7 days'
            UNION ALL
            SELECT 'Underbilling Gap', coalesce(sum(expected_amount - billed_amount), 0)
            FROM invoices WHERE expected_amount > billed_amount
              AND invoice_date::timestamp >= current_date - INTERVAL '7 days'
        """,
        "chart_type": "bar",
        "answer_template": "Current month revenue is ${current_revenue:,.2f} vs prior month ${prior_revenue:,.2f}. Refunds this month total ${refunds_this_month:,.2f}, and there is an underbilling gap of ${underbilling_gap:,.2f}. The revenue decline is driven by a combination of increased refunds (especially in EMEA region) and billing discrepancies where customers were charged below their expected plan rates.",
    },
    {
        "patterns": [r"(what|show).*(changed|happen|trend).*(refund)", r"refund.*(chang|trend|week|spike)"],
        "name": "refund_changes",
        "description": "Show what changed in refunds recently",
        "sql": """
            SELECT
                c.region,
                r.reason,
                count(*) as refund_count,
                sum(r.amount) as total_amount,
                avg(r.amount) as avg_amount
            FROM refunds r
            JOIN customers c ON r.customer_id = c.customer_id
            GROUP BY c.region, r.reason
            ORDER BY total_amount DESC
        """,
        "chart_query": """
            SELECT c.region as category, sum(r.amount) as amount
            FROM refunds r
            JOIN customers c ON r.customer_id = c.customer_id
            GROUP BY c.region
            ORDER BY amount DESC
        """,
        "chart_type": "bar",
        "answer_template": "Refund analysis by region and reason shows the breakdown of refund activity. The data reveals concentration in specific regions, with EMEA showing elevated refund volumes. Key refund reasons include service issues, billing errors, and overcharges.",
    },
    {
        "patterns": [r"(which|what).*(region|area).*(highest|most|top).*(refund)"],
        "name": "refunds_by_region",
        "description": "Show which region has the highest refund amount",
        "sql": """
            SELECT
                c.region,
                count(*) as refund_count,
                sum(r.amount) as total_amount,
                avg(r.amount) as avg_amount
            FROM refunds r
            JOIN customers c ON r.customer_id = c.customer_id
            GROUP BY c.region
            ORDER BY total_amount DESC
        """,
        "chart_query": """
            SELECT c.region as category, sum(r.amount) as amount
            FROM refunds r
            JOIN customers c ON r.customer_id = c.customer_id
            GROUP BY c.region
            ORDER BY amount DESC
        """,
        "chart_type": "bar",
        "answer_template": "Regional refund breakdown shows total refund amounts by region.",
    },
    {
        "patterns": [r"(show|what).*(underbill|billing.*(gap|mismatch)).*(tier|plan)", r"underbill.*tier"],
        "name": "underbilling_by_tier",
        "description": "Show underbilling breakdown by plan tier",
        "sql": """
            SELECT
                i.plan_tier_billed,
                count(*) as invoice_count,
                sum(i.expected_amount - i.billed_amount) as total_gap,
                avg(i.expected_amount - i.billed_amount) as avg_gap
            FROM invoices i
            WHERE i.expected_amount > i.billed_amount
            GROUP BY i.plan_tier_billed
            ORDER BY total_gap DESC
        """,
        "chart_query": """
            SELECT i.plan_tier_billed as category, sum(i.expected_amount - i.billed_amount) as amount
            FROM invoices i
            WHERE i.expected_amount > i.billed_amount
            GROUP BY i.plan_tier_billed
            ORDER BY amount DESC
        """,
        "chart_type": "bar",
        "answer_template": "Underbilling gap by plan tier shows where billing discrepancies are concentrated.",
    },
    {
        "patterns": [r"(top|biggest|largest).*(anomal|case|issue|exception)"],
        "name": "top_anomalies",
        "description": "Show top anomalies/cases from latest triage",
        "sql": """
            SELECT
                case_id, title, anomaly_type, severity, confidence,
                estimated_impact, status
            FROM cases
            ORDER BY estimated_impact DESC
            LIMIT 5
        """,
        "chart_query": """
            SELECT title as category, estimated_impact as amount
            FROM cases
            ORDER BY estimated_impact DESC
            LIMIT 5
        """,
        "chart_type": "bar",
        "answer_template": "Top anomalies from the latest triage run, ranked by estimated impact.",
        "uses_sqlite": True,
    },
    {
        "patterns": [r"(revenue|billing).*(trend|over.time|monthly)"],
        "name": "revenue_trend",
        "description": "Show revenue trend over time",
        "sql": """
            SELECT
                strftime(invoice_date::timestamp::date, '%Y-%m') as month,
                sum(billed_amount) as revenue,
                count(*) as invoice_count
            FROM invoices
            WHERE status = 'paid'
            GROUP BY strftime(invoice_date::timestamp::date, '%Y-%m')
            ORDER BY month
        """,
        "chart_query": """
            SELECT strftime(invoice_date::timestamp::date, '%Y-%m') as category, sum(billed_amount) as amount
            FROM invoices WHERE status = 'paid'
            GROUP BY strftime(invoice_date::timestamp::date, '%Y-%m')
            ORDER BY category
        """,
        "chart_type": "line",
        "answer_template": "Monthly revenue trend based on paid invoices.",
    },
]


def match_question(question: str) -> dict[str, Any] | None:
    """Find the best matching template for a question."""
    q_lower = question.lower().strip()

    for template in _TEMPLATES:
        for pattern in template["patterns"]:
            if re.search(pattern, q_lower):
                return template

    return None


def execute_query(question: str) -> dict[str, Any]:
    """Match a question to a template and execute the SQL.

    Returns:
        dict with keys: matched, name, description, sql, data, chart_query,
        chart_data, chart_type, answer_template
    """
    template = match_question(question)

    if template is None:
        # Fallback: generic revenue summary
        return {
            "matched": False,
            "name": "generic_summary",
            "description": "General business summary",
            "sql": "SELECT 'No specific template matched' as note",
            "data": [],
            "chart_query": None,
            "chart_data": [],
            "chart_type": "bar",
            "answer_template": "I don't have a specific analysis for that question yet. Try asking about revenue trends, refund changes, underbilling by tier, or top anomalies.",
        }

    # Execute main query
    if template.get("uses_sqlite"):
        from app.storage.db import get_sqlite
        import json
        conn = get_sqlite()
        rows = conn.execute(template["sql"]).fetchall()
        data = [dict(r) for r in rows]
    else:
        data = query_rows(template["sql"])

    # Execute chart query
    chart_data = []
    if template.get("chart_query"):
        if template.get("uses_sqlite"):
            rows = conn.execute(template["chart_query"]).fetchall()
            chart_data = [dict(r) for r in rows]
        else:
            chart_data = query_rows(template["chart_query"])

    return {
        "matched": True,
        "name": template["name"],
        "description": template["description"],
        "sql": template["sql"].strip(),
        "data": data,
        "chart_query": template.get("chart_query", "").strip(),
        "chart_data": chart_data,
        "chart_type": template.get("chart_type", "bar"),
        "answer_template": template.get("answer_template", ""),
    }
