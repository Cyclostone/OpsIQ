"""Lightdash Adapter — BI analytics / semantic metric layer.

Provides the semantic metric context for OpsIQ:
  - Semantic metric definitions (what metrics mean, how they're calculated)
  - Chart configurations for metric visualizations
  - Metric drift signals (revenue drop, refund spike, etc.)
  - Enriches analyst answers with metric context
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.schemas import SignalEvent, Severity


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------
_last_used: datetime | None = None
_call_log: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Semantic Metric Definitions
# ---------------------------------------------------------------------------

# Lightdash-compatible metric layer — used by Analyst to understand what metrics mean
METRIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "monthly_revenue",
        "label": "Monthly Revenue",
        "description": "Total billed amount from paid invoices in the current month",
        "sql": "SELECT sum(billed_amount) FROM invoices WHERE status = 'paid' AND invoice_date >= date_trunc('month', current_date)",
        "type": "sum",
        "table": "invoices",
        "column": "billed_amount",
        "filters": [{"field": "status", "operator": "equals", "value": "paid"}],
        "time_dimension": "invoice_date",
    },
    {
        "name": "total_refunds",
        "label": "Total Refunds",
        "description": "Sum of all refund amounts in the current month",
        "sql": "SELECT sum(amount) FROM refunds WHERE refund_date >= date_trunc('month', current_date)",
        "type": "sum",
        "table": "refunds",
        "column": "amount",
        "time_dimension": "refund_date",
    },
    {
        "name": "refund_count",
        "label": "Refund Count",
        "description": "Number of refunds processed",
        "sql": "SELECT count(*) FROM refunds",
        "type": "count",
        "table": "refunds",
        "time_dimension": "refund_date",
    },
    {
        "name": "net_revenue",
        "label": "Net Revenue",
        "description": "Monthly revenue minus total refunds",
        "sql": "SELECT (SELECT coalesce(sum(billed_amount),0) FROM invoices WHERE status='paid') - (SELECT coalesce(sum(amount),0) FROM refunds)",
        "type": "derived",
    },
    {
        "name": "avg_invoice_amount",
        "label": "Average Invoice Amount",
        "description": "Average billed amount per invoice",
        "sql": "SELECT avg(billed_amount) FROM invoices WHERE status = 'paid'",
        "type": "average",
        "table": "invoices",
        "column": "billed_amount",
    },
    {
        "name": "billing_gap",
        "label": "Total Billing Gap",
        "description": "Sum of (expected - billed) across all invoices where expected > billed",
        "sql": "SELECT sum(expected_amount - billed_amount) FROM invoices WHERE expected_amount > billed_amount",
        "type": "sum",
    },
    {
        "name": "refunds_by_region",
        "label": "Refunds by Region",
        "description": "Total refund amount broken down by customer region",
        "sql": "SELECT c.region, sum(r.amount) as total FROM refunds r JOIN customers c ON r.customer_id = c.customer_id GROUP BY c.region",
        "type": "grouped_sum",
        "dimensions": ["region"],
    },
    {
        "name": "underbilling_by_tier",
        "label": "Underbilling by Plan Tier",
        "description": "Billing gap grouped by plan tier",
        "sql": "SELECT plan_tier_billed, sum(expected_amount - billed_amount) as gap FROM invoices WHERE expected_amount > billed_amount GROUP BY plan_tier_billed",
        "type": "grouped_sum",
        "dimensions": ["plan_tier_billed"],
    },
]


def get_metric_definitions() -> list[dict[str, Any]]:
    """Return the semantic metric layer (Lightdash-compatible definitions)."""
    global _last_used
    _last_used = datetime.utcnow()
    _log_call("get_metric_definitions", {"count": len(METRIC_DEFINITIONS)})
    return METRIC_DEFINITIONS


def get_metric_by_name(name: str) -> dict[str, Any] | None:
    """Look up a single metric definition by name."""
    for m in METRIC_DEFINITIONS:
        if m["name"] == name:
            return m
    return None


# ---------------------------------------------------------------------------
# Chart Configuration
# ---------------------------------------------------------------------------

def get_chart_config(metric_name: str, chart_type: str = "bar") -> dict[str, Any]:
    """Return a Lightdash-compatible chart configuration for a metric."""
    global _last_used
    _last_used = datetime.utcnow()

    metric = get_metric_by_name(metric_name)
    config = {
        "source": "lightdash",
        "metric": metric_name,
        "chart_type": chart_type,
        "title": metric["label"] if metric else metric_name,
        "description": metric["description"] if metric else "",
        "config": {
            "type": chart_type,
            "showLegend": True,
            "showGrid": True,
            "colors": ["#4C78A8", "#F58518", "#E45756", "#72B7B2", "#54A24B"],
        },
    }
    _log_call("get_chart_config", {"metric": metric_name, "chart_type": chart_type})
    return config


# ---------------------------------------------------------------------------
# Signal Ingestion
# ---------------------------------------------------------------------------

def fetch_signals() -> list[SignalEvent]:
    """Fetch metric drift signals from the signal_events dataset."""
    global _last_used
    _last_used = datetime.utcnow()
    return _fetch_signals()


def _fetch_signals() -> list[SignalEvent]:
    """Read signals from DuckDB signal_events table where source='lightdash'."""
    from app.services.data_service import query_rows

    rows = query_rows("""
        SELECT signal_id, timestamp, signal_type, severity, source,
               related_entity, payload_json
        FROM signal_events
        WHERE source = 'lightdash'
        ORDER BY timestamp DESC
    """)

    signals = []
    for r in rows:
        payload = {}
        if r.get("payload_json"):
            try:
                payload = json.loads(r["payload_json"]) if isinstance(r["payload_json"], str) else r["payload_json"]
            except (json.JSONDecodeError, TypeError):
                payload = {}

        signals.append(SignalEvent(
            signal_id=r["signal_id"],
            timestamp=r["timestamp"],
            signal_type=r["signal_type"],
            severity=Severity(r["severity"]),
            source="lightdash",
            related_entity=r["related_entity"],
            payload=payload,
        ))

    _log_call("fetch_signals", {"count": len(signals)})
    return signals


def query_metric(metric_name: str) -> dict[str, Any]:
    """Query a specific metric value against local DuckDB."""
    global _last_used
    _last_used = datetime.utcnow()

    metric = get_metric_by_name(metric_name)
    if not metric:
        return {"error": f"Unknown metric: {metric_name}"}

    return _query_metric(metric)


def _query_metric(metric: dict[str, Any]) -> dict[str, Any]:
    """Run metric query against local DuckDB."""
    from app.services.data_service import query_rows

    try:
        rows = query_rows(metric.get("sql", "SELECT 1"))
        _log_call("query_metric", {
            "metric": metric["name"],
            "rows": len(rows),
        })
        return {
            "metric": metric["name"],
            "label": metric["label"],
            "source": "duckdb",
            "result": rows,
        }
    except Exception as e:
        return {
            "metric": metric["name"],
            "source": "error",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_call(action: str, details: dict[str, Any]) -> None:
    _call_log.append({
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details,
    })


def get_call_log() -> list[dict[str, Any]]:
    return list(_call_log)


def reset() -> None:
    global _last_used, _call_log
    _last_used = None
    _call_log = []
