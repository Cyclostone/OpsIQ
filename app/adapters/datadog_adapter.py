"""Datadog Adapter — signal source / alert context ingestion.

Ingests monitoring signals (anomaly alerts, metric thresholds) from the
signal_events dataset to trigger autonomous investigation.
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
# Core functions
# ---------------------------------------------------------------------------

def fetch_signals() -> list[SignalEvent]:
    """Fetch signals from the signal_events dataset where source='datadog'."""
    global _last_used
    _last_used = datetime.utcnow()
    return _fetch_signals()


def fetch_alert_context(signal: SignalEvent) -> dict[str, Any]:
    """Enrich a signal with additional context."""
    global _last_used
    _last_used = datetime.utcnow()

    context = {
        "source": "datadog",
        "signal_id": signal.signal_id,
        "enriched_at": datetime.utcnow().isoformat(),
        "related_monitors": [
            {"monitor_id": "MON-001", "name": "Refund Rate Monitor", "status": "Alert"},
            {"monitor_id": "MON-002", "name": "Revenue Anomaly Detector", "status": "Warn"},
        ],
        "tags": ["env:production", "service:billing", "team:finance"],
        "priority": "P2",
    }

    _log_call("fetch_alert_context", context)
    return context


# ---------------------------------------------------------------------------
# Signal fetching
# ---------------------------------------------------------------------------

def _fetch_signals() -> list[SignalEvent]:
    """Read signals from DuckDB signal_events table where source='datadog'."""
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

    _log_call("fetch_signals", {"count": len(signals)})
    return signals


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
