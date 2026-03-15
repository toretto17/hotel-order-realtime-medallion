#!/usr/bin/env python3
"""
Check if an order_id exists in Bronze and Silver Parquet data (and optionally in checkpoints).
Usage (from repo root, with BASE_PATH set):
  python3 scripts/check_order_in_medallion.py [order_id]
  ORDER_ID=web-xyz python3 scripts/check_order_in_medallion.py
Default order_id: web-567ebca2749c
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

BASE_PATH = os.environ.get("BASE_PATH", "/tmp/medallion")
ORDER_ID = os.environ.get("ORDER_ID") or (sys.argv[1] if len(sys.argv) > 1 else "web-567ebca2749c")

BRONZE_ORDERS = f"{BASE_PATH}/bronze/orders"
SILVER_ORDERS = f"{BASE_PATH}/silver/orders"
SILVER_ITEMS = f"{BASE_PATH}/silver/order_items"
CP_BRONZE = f"{BASE_PATH}/checkpoints/bronze_orders"
CP_SILVER = f"{BASE_PATH}/checkpoints/silver_orders"
CP_SILVER_ITEMS = f"{BASE_PATH}/checkpoints/silver_orders_order_items"


def main() -> None:
    print(f"Order ID: {ORDER_ID}")
    print(f"BASE_PATH: {BASE_PATH}")
    if BASE_PATH == "/tmp/medallion":
        print("  (default path — if you meant to check the VM, run this ON THE VM with export BASE_PATH=/home/ubuntu/medallion_data)")
    print()

    # Try PySpark so we can read Parquet and filter by order_id
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except ImportError:
        print("PySpark not available. Using grep fallback.")
        _check_with_grep()
        return

    spark = (
        SparkSession.builder
        .appName("check_order_medallion")
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .getOrCreate()
    )

    # Bronze: value column is JSON string; parse and filter by order_id
    bronze_found = False
    bronze_path = Path(BRONZE_ORDERS)
    if bronze_path.exists():
        try:
            df = spark.read.parquet(BRONZE_ORDERS)
            if "value" in df.columns:
                df = df.withColumn("_order_id", F.get_json_object(F.col("value"), "$.order_id"))
                matches = df.filter(F.col("_order_id") == ORDER_ID)
            else:
                matches = df.limit(0)
            count = matches.count()
            bronze_found = count > 0
            print(f"Bronze (Parquet): {'FOUND' if bronze_found else 'NOT FOUND'} ({count} row(s))")
        except Exception as e:
            print(f"Bronze (Parquet): Error - {e}")
    else:
        print("Bronze (Parquet): path does not exist")

    # Silver orders
    silver_orders_found = False
    if Path(SILVER_ORDERS).exists():
        try:
            df = spark.read.parquet(SILVER_ORDERS)
            if "order_id" in df.columns:
                count = df.filter(F.col("order_id") == ORDER_ID).count()
                silver_orders_found = count > 0
                print(f"Silver orders (Parquet): {'FOUND' if silver_orders_found else 'NOT FOUND'} ({count} row(s))")
            else:
                print("Silver orders (Parquet): no order_id column")
        except Exception as e:
            print(f"Silver orders (Parquet): Error - {e}")
    else:
        print("Silver orders (Parquet): path does not exist")

    # Silver order_items
    silver_items_found = False
    if Path(SILVER_ITEMS).exists():
        try:
            df = spark.read.parquet(SILVER_ITEMS)
            if "order_id" in df.columns:
                count = df.filter(F.col("order_id") == ORDER_ID).count()
                silver_items_found = count > 0
                print(f"Silver order_items (Parquet): {'FOUND' if silver_items_found else 'NOT FOUND'} ({count} row(s))")
            else:
                print("Silver order_items (Parquet): no order_id column")
        except Exception as e:
            print(f"Silver order_items (Parquet): Error - {e}")
    else:
        print("Silver order_items (Parquet): path does not exist")

    # Checkpoint dirs (metadata only; Spark stores file paths, not order_ids)
    print()
    for name, p in [("Bronze checkpoint", CP_BRONZE), ("Silver checkpoint (orders)", CP_SILVER), ("Silver checkpoint (order_items)", CP_SILVER_ITEMS)]:
        path = Path(p)
        if path.exists():
            files = list(path.iterdir())
            print(f"{name}: exists ({len(files)} entries)")
        else:
            print(f"{name}: does not exist")

    spark.stop()
    print()
    if bronze_found and not (silver_orders_found or silver_items_found):
        print("=> Order is in Bronze but NOT in Silver. Re-run pipeline (or wait for Silver retry) so Silver picks it up.")
    elif not bronze_found:
        print("=> Order not in Bronze. It was never consumed from Kafka (produce again or check topic).")
    else:
        print("=> Order is in both Bronze and Silver.")


def _check_with_grep() -> None:
    """Fallback: grep for order_id in Parquet dirs (string may appear in file)."""
    import subprocess
    for label, d in [("Bronze", BRONZE_ORDERS), ("Silver orders", SILVER_ORDERS), ("Silver order_items", SILVER_ITEMS)]:
        if not Path(d).exists():
            print(f"{label}: path does not exist")
            continue
        r = subprocess.run(
            ["grep", "-r", "-l", ORDER_ID, d],
            capture_output=True,
            timeout=30,
        )
        if r.returncode == 0 and r.stdout:
            print(f"{label}: FOUND (in {r.stdout.decode().strip().split(chr(10))})")
        else:
            print(f"{label}: NOT FOUND")


if __name__ == "__main__":
    main()
