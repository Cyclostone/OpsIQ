"""
Generate sample CSV datasets for OpsIQ demo.
Dates are relative to 'today' so the demo always looks fresh.
Anomalies are deterministically seeded for reliable triage detection.

Seeded anomalies:
  1. Duplicate refund: customer C003, $150.00 x2 within 1 hour
  2. Underbilling: customer C005 expected $299 billed $199 (invoice INV008)
  3. Tier mismatch: customer C007 on enterprise plan billed as pro (INV010)
  4. Refund spike: 4 refunds in EMEA region on same day (abnormal)
  5. Suspicious manual credit: customer C009, large $500 refund reason="manual_credit"
"""

import csv
import json
import os
from datetime import datetime, timedelta

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def d(days_ago: int, hour: int = 10, minute: int = 0) -> str:
    """Return ISO date string for `days_ago` days before today."""
    dt = TODAY - timedelta(days=days_ago) + timedelta(hours=hour, minutes=minute)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def write_csv(filename: str, headers: list, rows: list):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"  Created {filename} ({len(rows)} rows)")


def generate_customers():
    headers = ["customer_id", "customer_name", "region", "plan_tier", "status"]
    rows = [
        ["C001", "Acme Corp", "NA", "enterprise", "active"],
        ["C002", "Globex Inc", "NA", "pro", "active"],
        ["C003", "Initech", "NA", "starter", "active"],
        ["C004", "Umbrella Ltd", "EMEA", "enterprise", "active"],
        ["C005", "Stark Industries", "NA", "enterprise", "active"],
        ["C006", "Wayne Enterprises", "EMEA", "pro", "active"],
        ["C007", "Cyberdyne Systems", "APAC", "enterprise", "active"],
        ["C008", "Soylent Corp", "EMEA", "starter", "active"],
        ["C009", "Tyrell Corp", "EMEA", "pro", "active"],
        ["C010", "Wonka Industries", "APAC", "starter", "churned"],
    ]
    write_csv("customers.csv", headers, rows)


def generate_subscriptions():
    headers = ["subscription_id", "customer_id", "plan_tier", "start_date", "monthly_price", "billing_status"]
    rows = [
        ["SUB001", "C001", "enterprise", d(180), 499.00, "active"],
        ["SUB002", "C002", "pro", d(120), 199.00, "active"],
        ["SUB003", "C003", "starter", d(90), 49.00, "active"],
        ["SUB004", "C004", "enterprise", d(200), 499.00, "active"],
        ["SUB005", "C005", "enterprise", d(150), 299.00, "active"],
        ["SUB006", "C006", "pro", d(100), 199.00, "active"],
        ["SUB007", "C007", "enterprise", d(60), 499.00, "active"],
        ["SUB008", "C008", "starter", d(45), 49.00, "active"],
        ["SUB009", "C009", "pro", d(80), 199.00, "active"],
        ["SUB010", "C010", "starter", d(300), 49.00, "cancelled"],
    ]
    write_csv("subscriptions.csv", headers, rows)


def generate_invoices():
    headers = ["invoice_id", "customer_id", "invoice_date", "billed_amount", "expected_amount", "plan_tier_billed", "status"]
    rows = [
        # Normal invoices
        ["INV001", "C001", d(30), 499.00, 499.00, "enterprise", "paid"],
        ["INV002", "C002", d(30), 199.00, 199.00, "pro", "paid"],
        ["INV003", "C003", d(30), 49.00, 49.00, "starter", "paid"],
        ["INV004", "C004", d(30), 499.00, 499.00, "enterprise", "paid"],
        ["INV005", "C001", d(2), 499.00, 499.00, "enterprise", "paid"],
        ["INV006", "C002", d(2), 199.00, 199.00, "pro", "paid"],
        ["INV007", "C003", d(2), 49.00, 49.00, "starter", "paid"],
        # ANOMALY 2: Underbilling — C005 should be $299 but billed $199
        ["INV008", "C005", d(2), 199.00, 299.00, "enterprise", "paid"],
        ["INV009", "C006", d(2), 199.00, 199.00, "pro", "paid"],
        # ANOMALY 3: Tier mismatch — C007 is enterprise but billed as pro
        ["INV010", "C007", d(2), 199.00, 499.00, "pro", "paid"],
        ["INV011", "C008", d(2), 49.00, 49.00, "starter", "paid"],
        ["INV012", "C009", d(2), 199.00, 199.00, "pro", "paid"],
        # Older invoices for trend data
        ["INV013", "C005", d(32), 299.00, 299.00, "enterprise", "paid"],
        ["INV014", "C007", d(32), 499.00, 499.00, "enterprise", "paid"],
        ["INV015", "C006", d(32), 199.00, 199.00, "pro", "paid"],
        ["INV016", "C004", d(2), 499.00, 499.00, "enterprise", "paid"],
    ]
    write_csv("invoices.csv", headers, rows)


def generate_payments():
    headers = ["payment_id", "invoice_id", "customer_id", "payment_date", "amount", "payment_processor", "status"]
    rows = [
        ["PAY001", "INV001", "C001", d(30, 12), 499.00, "stripe", "completed"],
        ["PAY002", "INV002", "C002", d(30, 12), 199.00, "stripe", "completed"],
        ["PAY003", "INV003", "C003", d(30, 12), 49.00, "stripe", "completed"],
        ["PAY004", "INV004", "C004", d(30, 12), 499.00, "stripe", "completed"],
        ["PAY005", "INV005", "C001", d(2, 12), 499.00, "stripe", "completed"],
        ["PAY006", "INV006", "C002", d(2, 12), 199.00, "stripe", "completed"],
        ["PAY007", "INV007", "C003", d(2, 12), 49.00, "stripe", "completed"],
        ["PAY008", "INV008", "C005", d(2, 12), 199.00, "stripe", "completed"],
        ["PAY009", "INV009", "C006", d(2, 12), 199.00, "stripe", "completed"],
        ["PAY010", "INV010", "C007", d(2, 12), 199.00, "stripe", "completed"],
        ["PAY011", "INV011", "C008", d(2, 12), 49.00, "stripe", "completed"],
        ["PAY012", "INV012", "C009", d(2, 12), 199.00, "stripe", "completed"],
        ["PAY013", "INV013", "C005", d(32, 12), 299.00, "stripe", "completed"],
        ["PAY014", "INV014", "C007", d(32, 12), 499.00, "stripe", "completed"],
        ["PAY015", "INV015", "C006", d(32, 12), 199.00, "stripe", "completed"],
        ["PAY016", "INV016", "C004", d(2, 12), 499.00, "stripe", "completed"],
    ]
    write_csv("payments.csv", headers, rows)


def generate_refunds():
    headers = ["refund_id", "customer_id", "refund_date", "amount", "reason", "processor", "linked_payment_id"]
    rows = [
        # Normal refunds (spread across time)
        ["REF001", "C002", d(25), 50.00, "service_issue", "stripe", "PAY002"],
        ["REF002", "C001", d(20), 100.00, "billing_error", "stripe", "PAY001"],
        # ANOMALY 1: Duplicate refund — C003, same amount $150, within 1 hour
        ["REF003", "C003", d(1, 14, 0), 150.00, "overcharge", "stripe", "PAY007"],
        ["REF004", "C003", d(1, 14, 45), 150.00, "overcharge", "stripe", "PAY007"],
        # ANOMALY 4: Refund spike in EMEA — 4 refunds on same day
        ["REF005", "C004", d(1, 9), 200.00, "service_issue", "stripe", "PAY004"],
        ["REF006", "C006", d(1, 10), 199.00, "billing_error", "stripe", "PAY009"],
        ["REF007", "C008", d(1, 11), 49.00, "service_issue", "stripe", "PAY011"],
        ["REF008", "C009", d(1, 12), 180.00, "overcharge", "stripe", "PAY012"],
        # ANOMALY 5: Suspicious manual credit — large amount
        ["REF009", "C009", d(1, 16), 500.00, "manual_credit", "manual", "PAY012"],
        # Older normal refunds for baseline
        ["REF010", "C004", d(35), 50.00, "service_issue", "stripe", "PAY004"],
        ["REF011", "C006", d(40), 30.00, "billing_error", "stripe", "PAY015"],
    ]
    write_csv("refunds.csv", headers, rows)


def generate_usage_events():
    headers = ["event_id", "customer_id", "event_time", "usage_units", "feature_type"]
    rows = []
    event_id = 1
    features = ["api_calls", "storage_gb", "compute_hours", "data_export"]
    for days_ago in [30, 20, 10, 5, 2, 1]:
        for cid in [f"C{str(i).zfill(3)}" for i in range(1, 11)]:
            for feat in features[:2]:  # Keep it small
                rows.append([
                    f"EVT{str(event_id).zfill(4)}",
                    cid,
                    d(days_ago, 8 + (event_id % 10)),
                    50 + (event_id * 7) % 200,
                    feat,
                ])
                event_id += 1
    write_csv("usage_events.csv", headers, rows)


def generate_signal_events():
    headers = ["signal_id", "timestamp", "signal_type", "severity", "source", "related_entity", "payload_json"]
    rows = [
        [
            "SIG001",
            d(1, 8, 0),
            "anomaly_alert",
            "high",
            "datadog",
            "refunds",
            json.dumps({"metric": "refund.count", "value": 6, "threshold": 3, "region": "EMEA", "message": "Refund count spike detected in EMEA region"}),
        ],
        [
            "SIG002",
            d(1, 8, 5),
            "metric_drift",
            "medium",
            "lightdash",
            "revenue",
            json.dumps({"metric": "monthly_revenue", "expected": 2800, "actual": 2350, "drift_pct": -16.1, "message": "Monthly revenue below forecast by 16%"}),
        ],
        [
            "SIG003",
            d(1, 8, 10),
            "billing_exception",
            "high",
            "internal",
            "invoices",
            json.dumps({"type": "underbilling_detected", "invoice_ids": ["INV008", "INV010"], "total_gap": 400, "message": "Billing gap detected: $400 underbilled across 2 invoices"}),
        ],
        [
            "SIG004",
            d(0, 7, 0),
            "anomaly_alert",
            "medium",
            "datadog",
            "payments",
            json.dumps({"metric": "payment.failure_rate", "value": 0.08, "threshold": 0.05, "message": "Payment failure rate elevated at 8%"}),
        ],
        [
            "SIG005",
            d(0, 7, 30),
            "scheduled_scan",
            "low",
            "internal",
            "all",
            json.dumps({"message": "Scheduled daily triage scan triggered"}),
        ],
    ]
    write_csv("signal_events.csv", headers, rows)


if __name__ == "__main__":
    print("Seeding OpsIQ demo data...")
    generate_customers()
    generate_subscriptions()
    generate_invoices()
    generate_payments()
    generate_refunds()
    generate_usage_events()
    generate_signal_events()
    print("Done! All CSV files created.")
