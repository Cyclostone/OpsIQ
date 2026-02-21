"""Datadog Adapter — signal source / alert context ingestion.

Usage in OpsIQ:
  - Ingest monitoring signals (anomaly alerts, metric thresholds)
  - Provide event metadata that triggers autonomous investigation
  - In mock mode: reads from signal_events CSV (source='datadog')
  - In real mode: calls Datadog Events/Metrics API

Mock mode works without any API keys for demo reliability.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.config import settings
from app.models.schemas import SignalEvent, Severity, AdapterMode


# ---------------------------------------------------------------------------
# State tracking for demo / sponsor page
# ---------------------------------------------------------------------------
_last_used: datetime | None = None
_call_log: list[dict[str, Any]] = []


def get_mode() -> AdapterMode:
    return AdapterMode.real if settings.datadog_available else AdapterMode.mock


def get_status() -> dict[str, Any]:
    return {
        "name": "Datadog",
        "mode": get_mode().value,
        "available": settings.datadog_available,
        "description": "Monitoring signal source — ingests anomaly alerts and metric threshold events to trigger autonomous investigation.",
        "last_used": _last_used.isoformat() if _last_used else None,
        "call_count": len(_call_log),
        "sample_payload": _get_sample_payload(),
    }


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def fetch_signals() -> list[SignalEvent]:
    """Fetch latest Datadog signals.

    In mock mode: queries DuckDB signal_events where source='datadog'.
    In real mode: would call Datadog Events API.
    """
    global _last_used
    _last_used = datetime.utcnow()

    if settings.datadog_available:
        return _fetch_real_signals()
    else:
        return _fetch_mock_signals()


def fetch_alert_context(signal: SignalEvent) -> dict[str, Any]:
    """Enrich a signal with additional Datadog context.

    In mock mode: returns simulated enrichment data.
    In real mode: would call Datadog API for related monitors/events.
    """
    global _last_used
    _last_used = datetime.utcnow()

    context = {
        "source": "datadog",
        "signal_id": signal.signal_id,
        "enriched_at": datetime.utcnow().isoformat(),
    }

    if settings.datadog_available:
        # Real mode: would call GET /api/v1/events or /api/v2/events
        context["mode"] = "real"
        context["note"] = "Real Datadog API enrichment would be here"
    else:
        # Mock enrichment
        context["mode"] = "mock"
        context["related_monitors"] = [
            {"monitor_id": "MON-001", "name": "Refund Rate Monitor", "status": "Alert"},
            {"monitor_id": "MON-002", "name": "Revenue Anomaly Detector", "status": "Warn"},
        ]
        context["tags"] = ["env:production", "service:billing", "team:finance"]
        context["priority"] = "P2"

    _log_call("fetch_alert_context", context)
    return context


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------

def _fetch_mock_signals() -> list[SignalEvent]:
    """Read Datadog signals from DuckDB signal_events table."""
    from app.services.data_service import query_rows

    rows = query_rows("""
        SELECT signal_id, timestamp, signal_type, severity, source,
               related_entity, payload_json
        FROM signal_events
        WHERE source = 'datadog'
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
            source="datadog",
            related_entity=r["related_entity"],
            payload=payload,
        ))

    _log_call("fetch_signals (mock)", {"count": len(signals)})
    return signals


# ---------------------------------------------------------------------------
# Real implementation placeholder
# ---------------------------------------------------------------------------

def _fetch_real_signals() -> list[SignalEvent]:
    """Call Datadog Events API. Placeholder for real integration."""
    import httpx

    # Example: GET https://api.datadoghq.com/api/v1/events
    # Headers: DD-API-KEY, DD-APPLICATION-KEY
    # This is a placeholder — would need proper implementation
    try:
        client = httpx.Client(
            base_url=f"https://api.{settings.datadog_site}",
            headers={
                "DD-API-KEY": settings.datadog_api_key,
                "DD-APPLICATION-KEY": settings.datadog_app_key,
            },
            timeout=10.0,
        )
        # For hackathon: fall back to mock if real call fails
        resp = client.get("/api/v1/events", params={"start": int(datetime.utcnow().timestamp()) - 3600})
        resp.raise_for_status()
        # Parse response into SignalEvents...
        _log_call("fetch_signals (real)", {"status": resp.status_code})
        return []  # Would parse real events here
    except Exception as e:
        print(f"  [datadog_adapter] Real API call failed, falling back to mock: {e}")
        return _fetch_mock_signals()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_sample_payload() -> dict[str, Any]:
    return {
        "event_type": "anomaly_alert",
        "source": "datadog",
        "metric": "refund.count",
        "value": 6,
        "threshold": 3,
        "region": "EMEA",
        "tags": ["env:production", "service:billing"],
        "message": "Refund count spike detected in EMEA region",
    }


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
