#!/usr/bin/env python3
"""
Read only orders that came from the hotel website (vs script: make produce / produce-orders).

Website orders are identified by:
  - order_id starting with "web-"  (e.g. web-a1b2c3d4e5f6)
  - customer_id = "guest-web"

Usage (from project root):
  python3 scripts/read_web_orders.py           # Silver fact_orders + fact_order_items (web only)
  python3 scripts/read_web_orders.py bronze    # Bronze raw records (web only)
  python3 scripts/read_web_orders.py silver   # same as default
  python3 scripts/read_web_orders.py gold     # Gold tables (rows where web orders contributed)
"""
import os
import sys

BASE = os.environ.get("BASE_PATH", "/tmp/medallion")

# Identify website orders: order_id starts with "web-" and/or customer_id = "guest-web"
WEB_ORDER_ID_PREFIX = "web-"
WEB_CUSTOMER_ID = "guest-web"


def main():
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = SparkSession.builder.appName("read_web_orders").getOrCreate()
    layer = (sys.argv[1:2] or ["silver"])[0].lower()

    if layer == "bronze":
        df = spark.read.parquet(f"{BASE}/bronze/orders")
        # Bronze: value is raw JSON string; filter by parsing or by reading and filtering on value containing "guest-web" or "web-"
        from pyspark.sql.types import StringType
        df = df.filter(F.col("value").contains(WEB_CUSTOMER_ID) | F.col("value").contains('"order_id":"web-'))
        print("=== Bronze (website orders only: value contains guest-web or order_id web-) ===")
        df.show(truncate=False)
        print(f"Count: {df.count()}")
    elif layer in ("silver", "silver_orders"):
        df = spark.read.parquet(f"{BASE}/silver/orders")
        df = df.filter(F.col("order_id").startswith(WEB_ORDER_ID_PREFIX))
        print("=== Silver fact_orders (website orders only: order_id starts with 'web-') ===")
        df.show(truncate=False)
        print(f"Count: {df.count()}")
        # Items
        items = spark.read.parquet(f"{BASE}/silver/order_items")
        web_order_ids = [r.order_id for r in df.select("order_id").collect()]
        if web_order_ids:
            items = items.filter(F.col("order_id").isin(web_order_ids))
        print("=== Silver fact_order_items (lines for those orders) ===")
        items.show(truncate=False)
        print(f"Count: {items.count()}")
    elif layer == "gold":
        # Gold is aggregated; we can't filter "only web" per row, but we can show daily_sales that include web (e.g. restaurant R1 where guest-web orders go)
        print("=== Gold tables (all); website orders contribute to restaurant_id=R1, customer_id=guest-web in Silver ===")
        for name, path in [("daily_sales", f"{BASE}/gold/daily_sales"), ("customer_360", f"{BASE}/gold/customer_360"), ("restaurant_metrics", f"{BASE}/gold/restaurant_metrics")]:
            print(f"--- {name} ---")
            try:
                spark.read.parquet(path).show(20, truncate=False)
            except Exception as e:
                print(f"  (skip: {e})")
        # Show customer_360 row for guest-web if present
        try:
            cust = spark.read.parquet(f"{BASE}/gold/customer_360").filter(F.col("customer_id") == WEB_CUSTOMER_ID)
            print("=== Gold customer_360 (guest-web only) ===")
            cust.show(truncate=False)
        except Exception:
            pass
    else:
        print("Usage: read_web_orders.py [bronze|silver|gold]")
        sys.exit(1)
    spark.stop()


if __name__ == "__main__":
    main()
