#!/usr/bin/env python3
"""
Backfill Postgres medallion tables from existing Parquet data.

Use when:
- Bronze Postgres is empty but Bronze Parquet has data (e.g. data was ingested before
  Postgres was configured, or Bronze runs had "no new messages" so nothing was synced).
- You want to repopulate Postgres from Parquet after a manual fix or restore.

Requires: POSTGRES_JDBC_URL in .env, and Parquet data under BASE_PATH.

Usage:
  python3 scripts/backfill_postgres_from_parquet.py              # Bronze only
  python3 scripts/backfill_postgres_from_parquet.py --all       # Bronze + Silver + Gold (from Parquet)
  python3 scripts/backfill_postgres_from_parquet.py --bronze --silver   # Bronze and Silver only
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load .env before any streaming imports
_env = _REPO_ROOT / ".env"
if _env.is_file():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass

from streaming.config_loader import get_paths_config, load_config
from streaming.postgres_sink import (
    is_enabled as postgres_enabled,
    write_bronze_batch,
    write_silver_items_batch,
    write_silver_orders_batch,
)


def _backfill_bronze(base_path: str, config: dict) -> int:
    """Read Bronze Parquet and insert into Postgres (idempotent). Returns row count."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("backfill_bronze").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    bronze_path = f"{base_path.rstrip('/')}/bronze/orders"
    if not os.path.isdir(bronze_path):
        print(f"Bronze path not found: {bronze_path} (skip backfill)")
        return 0
    df = spark.read.option("recursiveFileLookup", "true").parquet(bronze_path)
    n = df.count()
    if n == 0:
        print("Bronze Parquet is empty; nothing to backfill.")
        return 0
    print(f"Backfilling Bronze: {n} row(s) from Parquet → Postgres (idempotent)...")
    write_bronze_batch(df, config)
    print("Bronze backfill done.")
    return int(n)


def _backfill_silver(base_path: str, config: dict) -> tuple[int, int]:
    """Read Silver Parquet (orders + order_items) and upsert into Postgres. Returns (orders, items) counts."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("backfill_silver").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    orders_path = f"{base_path.rstrip('/')}/silver/orders"
    items_path = f"{base_path.rstrip('/')}/silver/order_items"
    orders_count, items_count = 0, 0
    if os.path.isdir(orders_path):
        df_orders = spark.read.option("recursiveFileLookup", "true").parquet(orders_path)
        orders_count = df_orders.count()
        if orders_count > 0:
            print(f"Backfilling Silver orders: {orders_count} row(s) → Postgres...")
            write_silver_orders_batch(df_orders, config)
            print("Silver orders backfill done.")
    else:
        print(f"Silver orders path not found: {orders_path}")
    if os.path.isdir(items_path):
        df_items = spark.read.option("recursiveFileLookup", "true").parquet(items_path)
        items_count = df_items.count()
        if items_count > 0:
            print(f"Backfilling Silver order_items: {items_count} row(s) → Postgres...")
            write_silver_items_batch(df_items, config)
            print("Silver order_items backfill done.")
    else:
        print(f"Silver order_items path not found: {items_path}")
    return orders_count, items_count


def _backfill_gold(_base_path: str, _config: dict) -> None:
    """Run Gold batch job (reads Silver Parquet, writes Gold Parquet + Postgres)."""
    import subprocess
    # Gold batch already writes to Parquet and Postgres when Postgres is enabled
    print("Running Gold batch to repopulate Gold Parquet and Postgres from Silver...")
    out = subprocess.run(
        [sys.executable, "-m", "streaming.gold_batch"],
        cwd=str(_REPO_ROOT),
        env={**os.environ, "BASE_PATH": _base_path},
    )
    if out.returncode != 0:
        raise SystemExit(out.returncode)
    print("Gold backfill done (Gold job ran and synced to Postgres).")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Backfill Postgres from Parquet")
    parser.add_argument("--bronze", action="store_true", help="Backfill Bronze only")
    parser.add_argument("--silver", action="store_true", help="Backfill Silver only")
    parser.add_argument("--gold", action="store_true", help="Run Gold job to backfill Gold tables")
    parser.add_argument("--all", action="store_true", help="Backfill Bronze, Silver, and run Gold")
    args = parser.parse_args()

    if not args.bronze and not args.silver and not args.gold and not args.all:
        parser.print_help()
        print("\nDefault: --bronze (backfill Bronze only). Use --all for full backfill.")
        args.bronze = True

    if args.all:
        args.bronze = args.silver = args.gold = True

    config = load_config()
    if not postgres_enabled(config):
        print("POSTGRES_JDBC_URL not set in .env. Cannot backfill.")
        return 1

    paths = get_paths_config(config)
    base_path = (paths.get("base") or os.environ.get("BASE_PATH", "/tmp/medallion")).rstrip("/")

    if args.bronze:
        _backfill_bronze(base_path, config)
    if args.silver:
        _backfill_silver(base_path, config)
    if args.gold:
        _backfill_gold(base_path, config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
