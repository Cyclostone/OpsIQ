"""Rule-based anomaly detection tool.

Scans DuckDB tables for the 5 seeded anomaly types.
Thresholds are read from memory_store so the self-improvement loop can tune them.

Each detector returns a list of raw anomaly dicts with:
  - anomaly_type, evidence, affected_entities, raw_impact
"""

from __future__ import annotations

from typing import Any

from app.services.data_service import query_df, query_rows
from app.storage.memory_store import get_memory


# ---------------------------------------------------------------------------
# 1. Duplicate Refunds
# ---------------------------------------------------------------------------

def detect_duplicate_refunds() -> list[dict[str, Any]]:
    """Same customer + same amount within configurable window."""
    window_hours = get_memory("duplicate_refund_window_hours") or 2
    window_seconds = window_hours * 3600

    rows = query_rows(f"""
        SELECT
            r1.refund_id AS ref1,
            r2.refund_id AS ref2,
            r1.customer_id,
            r1.amount,
            r1.refund_date AS date1,
            r2.refund_date AS date2,
            r1.reason,
            r1.linked_payment_id
        FROM refunds r1
        JOIN refunds r2
            ON r1.customer_id = r2.customer_id
            AND r1.amount = r2.amount
            AND r1.refund_id < r2.refund_id
            AND abs(epoch(r2.refund_date::timestamp - r1.refund_date::timestamp)) < {window_seconds}
    """)

    results = []
    for r in rows:
        results.append({
            "anomaly_type": "duplicate_refund",
            "evidence": [
                f"Refunds {r['ref1']} and {r['ref2']} for customer {r['customer_id']}",
                f"Same amount ${r['amount']:.2f} within {window_hours}h window",
                f"Dates: {r['date1']} → {r['date2']}",
                f"Reason: {r['reason']}",
            ],
            "affected_entities": {
                "customer_id": r["customer_id"],
                "refund_ids": [r["ref1"], r["ref2"]],
                "payment_id": r["linked_payment_id"],
            },
            "raw_impact": float(r["amount"]),  # duplicate amount
        })
    return results


# ---------------------------------------------------------------------------
# 2. Underbilling
# ---------------------------------------------------------------------------

def detect_underbilling() -> list[dict[str, Any]]:
    """Invoices where expected_amount > billed_amount beyond threshold."""
    threshold = get_memory("underbilling_threshold") or 10.0

    rows = query_rows(f"""
        SELECT
            i.invoice_id,
            i.customer_id,
            i.billed_amount,
            i.expected_amount,
            i.expected_amount - i.billed_amount AS gap,
            i.plan_tier_billed,
            i.invoice_date,
            c.customer_name
        FROM invoices i
        JOIN customers c ON i.customer_id = c.customer_id
        WHERE i.expected_amount - i.billed_amount > {threshold}
    """)

    results = []
    for r in rows:
        results.append({
            "anomaly_type": "underbilling",
            "evidence": [
                f"Invoice {r['invoice_id']} for {r['customer_name']} ({r['customer_id']})",
                f"Billed ${r['billed_amount']:.2f} but expected ${r['expected_amount']:.2f}",
                f"Revenue gap: ${r['gap']:.2f}",
                f"Invoice date: {r['invoice_date']}",
            ],
            "affected_entities": {
                "customer_id": r["customer_id"],
                "customer_name": r["customer_name"],
                "invoice_id": r["invoice_id"],
            },
            "raw_impact": float(r["gap"]),
        })
    return results


# ---------------------------------------------------------------------------
# 3. Tier Mismatch
# ---------------------------------------------------------------------------

def detect_tier_mismatch() -> list[dict[str, Any]]:
    """Subscription plan_tier != invoice plan_tier_billed."""
    rows = query_rows("""
        SELECT
            i.invoice_id,
            i.customer_id,
            s.plan_tier AS subscription_tier,
            i.plan_tier_billed AS billed_tier,
            i.billed_amount,
            i.expected_amount,
            i.invoice_date,
            c.customer_name
        FROM invoices i
        JOIN subscriptions s ON i.customer_id = s.customer_id
        JOIN customers c ON i.customer_id = c.customer_id
        WHERE s.plan_tier != i.plan_tier_billed
          AND s.billing_status = 'active'
    """)

    results = []
    for r in rows:
        impact = float(r["expected_amount"]) - float(r["billed_amount"])
        results.append({
            "anomaly_type": "tier_mismatch",
            "evidence": [
                f"Invoice {r['invoice_id']} for {r['customer_name']} ({r['customer_id']})",
                f"Subscription tier: {r['subscription_tier']}, but billed as: {r['billed_tier']}",
                f"Billed ${r['billed_amount']:.2f} vs expected ${r['expected_amount']:.2f}",
                f"Invoice date: {r['invoice_date']}",
            ],
            "affected_entities": {
                "customer_id": r["customer_id"],
                "customer_name": r["customer_name"],
                "invoice_id": r["invoice_id"],
                "subscription_tier": r["subscription_tier"],
                "billed_tier": r["billed_tier"],
            },
            "raw_impact": max(impact, 0),
        })
    return results


# ---------------------------------------------------------------------------
# 4. Refund Spike (by region/day)
# ---------------------------------------------------------------------------

def detect_refund_spike() -> list[dict[str, Any]]:
    """Region/day refund count exceeds multiplier × rolling baseline."""
    multiplier = get_memory("refund_spike_multiplier") or 2.0

    # Get daily refund counts per region
    df = query_df("""
        SELECT
            c.region,
            r.refund_date::date AS refund_day,
            count(*) AS daily_count,
            sum(r.amount) AS daily_amount
        FROM refunds r
        JOIN customers c ON r.customer_id = c.customer_id
        GROUP BY c.region, r.refund_date::date
        ORDER BY refund_day
    """)

    if df.empty:
        return []

    results = []
    # Compute per-region baseline (average daily count)
    for region in df["region"].unique():
        region_df = df[df["region"] == region].sort_values("refund_day")
        if len(region_df) < 2:
            continue

        baseline_count = region_df["daily_count"].mean()
        threshold_count = baseline_count * multiplier

        # Check each day for spikes
        for _, row in region_df.iterrows():
            if row["daily_count"] > threshold_count and row["daily_count"] >= 3:
                results.append({
                    "anomaly_type": "refund_spike",
                    "evidence": [
                        f"Region {region} on {row['refund_day']}: {int(row['daily_count'])} refunds",
                        f"Baseline average: {baseline_count:.1f} refunds/day",
                        f"Threshold ({multiplier}x): {threshold_count:.1f}",
                        f"Total refund amount: ${row['daily_amount']:.2f}",
                    ],
                    "affected_entities": {
                        "region": region,
                        "date": str(row["refund_day"]),
                        "refund_count": int(row["daily_count"]),
                    },
                    "raw_impact": float(row["daily_amount"]),
                })
    return results


# ---------------------------------------------------------------------------
# 5. Suspicious Manual Credits
# ---------------------------------------------------------------------------

def detect_manual_credits() -> list[dict[str, Any]]:
    """Large refunds with reason='manual_credit' above threshold."""
    threshold = get_memory("manual_credit_threshold") or 200.0

    rows = query_rows(f"""
        SELECT
            r.refund_id,
            r.customer_id,
            r.amount,
            r.refund_date,
            r.processor,
            c.customer_name
        FROM refunds r
        JOIN customers c ON r.customer_id = c.customer_id
        WHERE r.reason = 'manual_credit'
          AND r.amount > {threshold}
    """)

    results = []
    for r in rows:
        results.append({
            "anomaly_type": "manual_credit",
            "evidence": [
                f"Refund {r['refund_id']} for {r['customer_name']} ({r['customer_id']})",
                f"Manual credit of ${r['amount']:.2f} via {r['processor']}",
                f"Date: {r['refund_date']}",
                f"Exceeds threshold of ${threshold:.2f}",
            ],
            "affected_entities": {
                "customer_id": r["customer_id"],
                "customer_name": r["customer_name"],
                "refund_id": r["refund_id"],
            },
            "raw_impact": float(r["amount"]),
        })
    return results


# ---------------------------------------------------------------------------
# Run all detectors
# ---------------------------------------------------------------------------

def run_all_detectors() -> list[dict[str, Any]]:
    """Execute all anomaly detectors and return combined results."""
    all_anomalies: list[dict[str, Any]] = []

    detectors = [
        ("duplicate_refund", detect_duplicate_refunds),
        ("underbilling", detect_underbilling),
        ("tier_mismatch", detect_tier_mismatch),
        ("refund_spike", detect_refund_spike),
        ("manual_credit", detect_manual_credits),
    ]

    for name, detector in detectors:
        try:
            found = detector()
            all_anomalies.extend(found)
            print(f"  [anomaly_tool] {name}: {len(found)} anomalies found")
        except Exception as e:
            print(f"  [anomaly_tool] {name}: ERROR - {e}")

    return all_anomalies
