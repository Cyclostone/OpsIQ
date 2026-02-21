"""Lightdash Adapter — BI analytics / semantic metric layer.

Lightdash is an open-source BI tool that sits on top of dbt.
In OpsIQ, Lightdash serves as the **metric context layer**:
  - Provides semantic metric definitions (what metrics mean, how they're calculated)
  - Supplies chart configurations for metric visualizations
  - Fetches metric drift signals (revenue drop, refund spike, etc.)
  - Enriches analyst answers with metric context

Real mode (LIGHTDASH_API_KEY set):
  - Calls Lightdash REST API v1 with Authorization: ApiKey <token>
  - Queries: GET /api/v1/projects/{uuid}/explores (metric catalog)
  - Results: POST /api/v1/projects/{uuid}/sqlRunner (run queries)
  - Charts: GET /api/v1/projects/{uuid}/charts (saved charts)

Mock mode (no key):
  - Returns hardcoded semantic metric layer (8 billing metrics)
  - Reads signal_events from DuckDB where source='lightdash'
  - Same interface, same data format

Setup:
  1. Go to https://app.lightdash.cloud → Sign up
  2. Settings → Personal Access Tokens → Create token
  3. Add to .env: LIGHTDASH_API_KEY=your_token
  4. Set LIGHTDASH_URL=https://app.lightdash.cloud
  5. Set LIGHTDASH_PROJECT_UUID=your_project_uuid

Note: Full Lightdash setup requires a dbt project + data warehouse.
For the hackathon, the mock metric layer is fully functional.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.config import settings
from app.models.schemas import SignalEvent, Severity, AdapterMode


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------
_last_used: datetime | None = None
_call_log: list[dict[str, Any]] = []
_api_errors: list[dict[str, Any]] = []


def get_mode() -> AdapterMode:
    return AdapterMode.real if settings.lightdash_available else AdapterMode.mock


def get_status() -> dict[str, Any]:
    return {
        "name": "Lightdash",
        "mode": get_mode().value,
        "available": settings.lightdash_available,
        "api_url": settings.lightdash_url or "(not set)",
        "api_key_set": bool(settings.lightdash_api_key),
        "project_uuid": settings.lightdash_project_uuid or "(not set)",
        "description": "BI analytics & semantic metric layer — provides metric definitions, chart configs, and metric drift signals. Powers the Analyst module.",
        "last_used": _last_used.isoformat() if _last_used else None,
        "call_count": len(_call_log),
        "api_errors": len(_api_errors),
        "metrics_available": len(METRIC_DEFINITIONS),
        "sample_payload": _get_sample_payload(),
    }


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
        "mode": get_mode().value,
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
    """Fetch Lightdash metric drift signals."""
    global _last_used
    _last_used = datetime.utcnow()

    if settings.lightdash_available:
        return _fetch_real_signals()
    else:
        return _fetch_mock_signals()


def _fetch_mock_signals() -> list[SignalEvent]:
    """Read Lightdash signals from DuckDB signal_events table."""
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

    _log_call("fetch_signals (mock)", {"count": len(signals)})
    return signals


def _fetch_real_signals() -> list[SignalEvent]:
    """Call Lightdash REST API for metric data.

    Lightdash API format:
      Base: {LIGHTDASH_URL}/api/v1
      Auth: Authorization: ApiKey {LIGHTDASH_API_KEY}
      Endpoints:
        - GET /projects/{uuid}/explores → metric catalog
        - GET /projects/{uuid}/charts → saved charts
        - POST /projects/{uuid}/sqlRunner → run SQL queries
    """
    import httpx

    try:
        base = settings.lightdash_url.rstrip("/")
        project = settings.lightdash_project_uuid
        headers = {
            "Authorization": f"ApiKey {settings.lightdash_api_key}",
            "Content-Type": "application/json",
        }

        # Try to fetch chart results for metric drift detection
        resp = httpx.get(
            f"{base}/api/v1/projects/{project}/charts",
            headers=headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        charts = data.get("results", [])

        _log_call("fetch_signals (real)", {
            "status": resp.status_code,
            "charts_found": len(charts),
        })
        print(f"  [lightdash_adapter] Real API: found {len(charts)} charts")

        # For now, still use mock signals since we don't have real metric alerts
        # but log that we successfully connected to the API
        return _fetch_mock_signals()

    except httpx.HTTPStatusError as e:
        error_detail = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        print(f"  [lightdash_adapter] API error: {error_detail}")
        _api_errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_detail,
        })
        return _fetch_mock_signals()

    except Exception as e:
        print(f"  [lightdash_adapter] Real API call failed, falling back to mock: {e}")
        _api_errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        })
        return _fetch_mock_signals()


def query_metric(metric_name: str) -> dict[str, Any]:
    """Query a specific metric value, using Lightdash API if available."""
    global _last_used
    _last_used = datetime.utcnow()

    metric = get_metric_by_name(metric_name)
    if not metric:
        return {"error": f"Unknown metric: {metric_name}"}

    if settings.lightdash_available:
        return _query_metric_real(metric)
    return _query_metric_mock(metric)


def _query_metric_real(metric: dict[str, Any]) -> dict[str, Any]:
    """Run a metric query via Lightdash SQL Runner."""
    import httpx

    try:
        base = settings.lightdash_url.rstrip("/")
        project = settings.lightdash_project_uuid
        headers = {
            "Authorization": f"ApiKey {settings.lightdash_api_key}",
            "Content-Type": "application/json",
        }

        resp = httpx.post(
            f"{base}/api/v1/projects/{project}/sqlRunner",
            headers=headers,
            json={"sql": metric.get("sql", "SELECT 1")},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        _log_call("query_metric (real)", {
            "metric": metric["name"],
            "status": resp.status_code,
        })
        return {
            "metric": metric["name"],
            "label": metric["label"],
            "source": "lightdash_api",
            "result": data.get("results", []),
        }

    except Exception as e:
        print(f"  [lightdash_adapter] SQL runner failed: {e}")
        return _query_metric_mock(metric)


def _query_metric_mock(metric: dict[str, Any]) -> dict[str, Any]:
    """Run metric query against local DuckDB."""
    from app.services.data_service import query_rows

    try:
        rows = query_rows(metric.get("sql", "SELECT 1"))
        _log_call("query_metric (mock/duckdb)", {
            "metric": metric["name"],
            "rows": len(rows),
        })
        return {
            "metric": metric["name"],
            "label": metric["label"],
            "source": "duckdb_local",
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

def _get_sample_payload() -> dict[str, Any]:
    return {
        "event_type": "metric_drift",
        "source": "lightdash",
        "metric": "monthly_revenue",
        "expected": 2800,
        "actual": 2350,
        "drift_pct": -16.1,
        "message": "Monthly revenue below forecast by 16%",
        "lightdash_api_format": {
            "auth": "Authorization: ApiKey <LIGHTDASH_API_KEY>",
            "endpoints": [
                "GET /api/v1/projects/{uuid}/explores",
                "GET /api/v1/projects/{uuid}/charts",
                "POST /api/v1/projects/{uuid}/sqlRunner",
            ],
        },
    }


def _log_call(action: str, details: dict[str, Any]) -> None:
    _call_log.append({
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details,
    })


def get_call_log() -> list[dict[str, Any]]:
    return list(_call_log)


def get_api_errors() -> list[dict[str, Any]]:
    """Return API error log for debugging."""
    return list(_api_errors)


def reset() -> None:
    global _last_used, _call_log, _api_errors
    _last_used = None
    _call_log = []
    _api_errors = []
