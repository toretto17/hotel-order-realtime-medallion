#!/usr/bin/env python3
"""
Truncate all medallion tables in Postgres. Use for a full reset (start from scratch).

Use when:
- You ran make clean-data and want Postgres to match (empty layers).
- You need to reload everything from Kafka/Parquet and want no stale rows in Postgres.

Requires: POSTGRES_JDBC_URL in .env.

Usage:
  python3 scripts/truncate_postgres_medallion.py --yes
  make postgres-truncate   # same (prompts without --yes)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_env = _REPO_ROOT / ".env"
if _env.is_file():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass

from streaming.config_loader import load_config
from streaming.postgres_sink import get_postgres_config, jdbc_to_conn_params


TABLES = [
    "medallion.bronze_orders",
    "medallion.silver_order_items",
    "medallion.silver_orders",
    "medallion.gold_daily_sales",
    "medallion.gold_customer_360",
    "medallion.gold_restaurant_metrics",
]


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Truncate all medallion tables (full reset)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    config = load_config()
    cfg = get_postgres_config(config)
    jdbc_url = (cfg.get("jdbc_url") or "").strip()
    if not jdbc_url:
        print("POSTGRES_JDBC_URL not set in .env. Cannot truncate.")
        return 1

    if not args.yes:
        print("This will TRUNCATE all medallion tables (Bronze, Silver, Gold).")
        print("Tables:", ", ".join(TABLES))
        try:
            ok = input("Type 'yes' to confirm: ").strip().lower()
        except EOFError:
            ok = ""
        if ok != "yes":
            print("Aborted.")
            return 0

    try:
        import psycopg2
    except ImportError:
        print("psycopg2 required: pip install psycopg2-binary")
        return 1

    conn_params = jdbc_to_conn_params(jdbc_url)
    conn = psycopg2.connect(**conn_params)
    try:
        cur = conn.cursor()
        for table in TABLES:
            cur.execute(f'TRUNCATE TABLE {table} CASCADE')
            print(f"Truncated: {table}")
        conn.commit()
    finally:
        conn.close()

    print("All medallion tables truncated. Run make pipeline (or backfill) to repopulate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
