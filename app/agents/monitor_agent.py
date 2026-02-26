"""Monitor Agent — ingests signals from all sponsor sources and internal events.

Responsibilities:
  - Fetch latest signals from Datadog, Lightdash, and internal sources
  - Pick the highest-priority signal to act on
  - Enrich signal with context from the originating adapter
  - Return the trigger signal for the orchestrator
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.schemas import SignalEvent, Severity
from app.adapters import datadog_adapter, lightdash_adapter
from app.services.data_service import query_rows


# Severity priority for sorting
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def fetch_all_signals() -> list[SignalEvent]:
    """Fetch signals from all sources: Datadog, Lightdash, internal."""
    all_signals: list[SignalEvent] = []

    # 1. Datadog signals
    try:
        dd = datadog_adapter.fetch_signals()
        all_signals.extend(dd)
        print(f"  [monitor_agent] Datadog: {len(dd)} signals")
    except Exception as e:
        print(f"  [monitor_agent] Datadog fetch error: {e}")

    # 2. Lightdash signals
    try:
        lh = lightdash_adapter.fetch_signals()
        all_signals.extend(lh)
        print(f"  [monitor_agent] Lightdash: {len(lh)} signals")
    except Exception as e:
        print(f"  [monitor_agent] Lightdash fetch error: {e}")

    # 3. Internal signals
    try:
        internal = _fetch_internal_signals()
        all_signals.extend(internal)
        print(f"  [monitor_agent] Internal: {len(internal)} signals")
    except Exception as e:
        print(f"  [monitor_agent] Internal fetch error: {e}")

    # Sort by severity (highest first), then by timestamp (newest first)
    all_signals.sort(key=lambda s: (
        _SEVERITY_ORDER.get(s.severity.value, 9),
        -s.timestamp.timestamp(),
    ))

    print(f"  [monitor_agent] Total signals: {len(all_signals)}")
    return all_signals


def pick_trigger_signal(signals: list[SignalEvent] | None = None) -> SignalEvent | None:
    """Select the highest-priority signal to trigger investigation.

    Returns the top signal, or None if no signals available.
    """
    if signals is None:
        signals = fetch_all_signals()

    if not signals:
        print("  [monitor_agent] No signals available")
        return None

    trigger = signals[0]
    print(f"  [monitor_agent] Trigger signal: {trigger.signal_id} ({trigger.source}, {trigger.severity.value})")
    return trigger


def enrich_signal(signal: SignalEvent) -> dict[str, Any]:
    """Enrich a signal with additional context from its source adapter."""
    context: dict[str, Any] = {
        "signal": signal.model_dump(),
        "enriched_at": datetime.utcnow().isoformat(),
    }

    if signal.source == "datadog":
        context["adapter_context"] = datadog_adapter.fetch_alert_context(signal)
    elif signal.source == "lightdash":
        # Lightdash enrichment: add relevant metric definitions
        context["adapter_context"] = {
            "source": "lightdash",
            "related_metrics": _find_related_metrics(signal),
        }
    else:
        context["adapter_context"] = {
            "source": "internal",
            "note": "Internal signal — no external enrichment needed",
        }

    return context


def _find_related_metrics(signal: SignalEvent) -> list[dict[str, Any]]:
    """Find Lightdash metric definitions related to a signal."""
    metrics = lightdash_adapter.get_metric_definitions()
    related_entity = signal.related_entity.lower()

    related = []
    for m in metrics:
        # Match by table name or metric name containing the entity
        if (related_entity in m.get("name", "").lower()
                or related_entity in m.get("table", "").lower()
                or related_entity in m.get("description", "").lower()):
            related.append({"name": m["name"], "label": m["label"], "description": m["description"]})

    return related


def _fetch_internal_signals() -> list[SignalEvent]:
    """Read internal signals from DuckDB signal_events table."""
    rows = query_rows("""
        SELECT signal_id, timestamp, signal_type, severity, source,
               related_entity, payload_json
        FROM signal_events
        WHERE source = 'internal'
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
            source="internal",
            related_entity=r["related_entity"],
            payload=payload,
        ))

    return signals
