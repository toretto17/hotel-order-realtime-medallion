#!/usr/bin/env python3
"""Read and show Gold tables (daily_sales, customer_360, restaurant_metrics). Run from project root."""
import os
import sys

BASE = os.environ.get("BASE_PATH", "/tmp/medallion")
paths = {
    "daily_sales": f"{BASE}/gold/daily_sales",
    "customer_360": f"{BASE}/gold/customer_360",
    "restaurant_metrics": f"{BASE}/gold/restaurant_metrics",
}


def main():
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("read_gold").getOrCreate()
    which = (sys.argv[1:2] or ["all"])[0].lower()
    for name, path in paths.items():
        if which != "all" and which != name:
            continue
        print(f"=== {name} ===")
        try:
            df = spark.read.parquet(path)
            df.show(20, truncate=False)
        except Exception as e:
            print(f"  (no data or path missing: {e})")
    spark.stop()


if __name__ == "__main__":
    main()
