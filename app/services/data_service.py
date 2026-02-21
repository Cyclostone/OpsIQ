"""DuckDB data service — loads CSVs into an in-memory DuckDB instance.

Usage:
    from app.services.data_service import get_db, query_df, query_rows

    df = query_df("SELECT * FROM customers WHERE region = 'EMEA'")
    rows = query_rows("SELECT count(*) as cnt FROM refunds")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.config import DATA_DIR

# ---------------------------------------------------------------------------
# Module-level singleton connection
# ---------------------------------------------------------------------------
_conn: duckdb.DuckDBPyConnection | None = None

# CSV files to load as tables (filename stem becomes table name)
_TABLES = [
    "customers",
    "subscriptions",
    "invoices",
    "payments",
    "refunds",
    "usage_events",
    "signal_events",
]


def _init_db() -> duckdb.DuckDBPyConnection:
    """Create in-memory DuckDB and load all CSV files."""
    conn = duckdb.connect(":memory:")

    for table in _TABLES:
        csv_path = DATA_DIR / f"{table}.csv"
        if not csv_path.exists():
            print(f"  [data_service] WARNING: {csv_path} not found, skipping")
            continue

        # Read CSV with pandas first for reliable type handling
        df = pd.read_csv(str(csv_path))

        # For signal_events, parse the JSON payload column
        if table == "signal_events" and "payload_json" in df.columns:
            df["payload_json"] = df["payload_json"].fillna("{}")

        conn.execute(f"CREATE TABLE {table} AS SELECT * FROM df")
        print(f"  [data_service] Loaded {table}: {len(df)} rows")

    return conn


def get_db() -> duckdb.DuckDBPyConnection:
    """Return the singleton DuckDB connection, initializing if needed."""
    global _conn
    if _conn is None:
        print("[data_service] Initializing DuckDB...")
        _conn = _init_db()
        print("[data_service] DuckDB ready.")
    return _conn


def reset_db() -> None:
    """Force re-initialization (used by demo reset)."""
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def query_df(sql: str) -> pd.DataFrame:
    """Execute SQL and return a pandas DataFrame."""
    conn = get_db()
    try:
        return conn.execute(sql).fetchdf()
    except Exception as e:
        print(f"  [data_service] SQL error: {e}")
        return pd.DataFrame()


def query_rows(sql: str) -> list[dict[str, Any]]:
    """Execute SQL and return a list of dicts."""
    df = query_df(sql)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def query_scalar(sql: str, default: Any = None) -> Any:
    """Execute SQL and return a single scalar value."""
    conn = get_db()
    try:
        result = conn.execute(sql).fetchone()
        return result[0] if result else default
    except Exception as e:
        print(f"  [data_service] SQL error: {e}")
        return default


def get_loaded_tables() -> list[str]:
    """Return list of tables currently loaded in DuckDB."""
    conn = get_db()
    try:
        result = conn.execute("SHOW TABLES").fetchdf()
        return result["name"].tolist() if not result.empty else []
    except Exception:
        return []


def get_table_info(table: str) -> list[dict[str, str]]:
    """Return column names and types for a table."""
    conn = get_db()
    try:
        result = conn.execute(f"DESCRIBE {table}").fetchdf()
        return result.to_dict(orient="records")
    except Exception:
        return []


def get_table_row_count(table: str) -> int:
    """Return row count for a table."""
    return query_scalar(f"SELECT count(*) FROM {table}", default=0)
