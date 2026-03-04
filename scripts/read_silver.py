#!/usr/bin/env python3
"""Read and show Silver fact_orders and/or fact_order_items. Run from project root."""
import os
import sys

BASE = os.environ.get("BASE_PATH", "/tmp/medallion")
orders_path = f"{BASE}/silver/orders"
items_path = f"{BASE}/silver/order_items"

def main():
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("read_silver").getOrCreate()
    which = (sys.argv[1:2] or ["both"])[0].lower()
    if which in ("orders", "both"):
        print("=== fact_orders ===")
        df = spark.read.parquet(orders_path)
        df.show(truncate=False)
        df.printSchema()
    if which in ("items", "both"):
        print("=== fact_order_items ===")
        df = spark.read.parquet(items_path)
        df.show(truncate=False)
        df.printSchema()
    spark.stop()

if __name__ == "__main__":
    main()
