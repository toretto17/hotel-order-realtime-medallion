"""
Lesson 4: Gold — Batch aggregations from Silver.

Reads Silver Parquet (fact_orders, fact_order_items), runs Gold SQL aggregations,
writes to Gold paths. One entry point for all Gold tables (production pattern: multiple SQL, one runner).

Run (from repo root; Silver must have data first):
  spark-submit streaming/gold_batch.py
  BASE_PATH=/tmp/medallion spark-submit streaming/gold_batch.py

Requires: BASE_PATH set; Silver paths must exist (can be empty).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from streaming.config_loader import get_paths_config, load_config


def register_silver_views(spark: SparkSession, paths: dict) -> None:
    """Read Silver Parquet with mergeSchema, add order_date for fact_orders, create temp views."""
    silver_orders_path = paths.get("silver_orders")
    silver_order_items_path = paths.get("silver_order_items")

    if not silver_orders_path:
        raise ValueError("paths.silver_orders is required")

    # mergeSchema: older and newer Silver files may have different columns (e.g. new optional fields)
    orders_df = (
        spark.read.option("mergeSchema", "true")
        .parquet(silver_orders_path)
        .withColumn("order_date", F.to_date(F.col("order_timestamp")))
    )
    orders_df.createOrReplaceTempView("silver_fact_orders")

    if silver_order_items_path:
        items_df = spark.read.option("mergeSchema", "true").parquet(silver_order_items_path)
        items_df.createOrReplaceTempView("silver_fact_order_items")
    else:
        # If no order_items path, create empty view with expected schema so SQL doesn't fail
        from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType, TimestampType
        empty_schema = StructType([
            StructField("order_id", StringType()),
            StructField("order_timestamp", TimestampType()),
            StructField("item_id", StringType()),
            StructField("item_name", StringType()),
            StructField("category", StringType()),
            StructField("quantity", IntegerType()),
            StructField("unit_price", DoubleType()),
            StructField("subtotal", DoubleType()),
        ])
        spark.createDataFrame([], empty_schema).createOrReplaceTempView("silver_fact_order_items")


def run_gold_sql_and_write(
    spark: SparkSession,
    sql_path: Path,
    output_path: str,
    partition_by: list[str] | None = None,
) -> None:
    """Run a Gold SQL file and write result to output_path (overwrite)."""
    if not sql_path.is_file():
        raise FileNotFoundError(f"Gold SQL not found: {sql_path}")
    sql_text = sql_path.read_text()
    df = spark.sql(sql_text)
    writer = df.write.mode("overwrite")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.format("parquet").save(output_path)
    print(f"Gold written: {output_path}")


def main() -> None:
    config = load_config()
    paths = get_paths_config(config)

    spark = (
        SparkSession.builder.appName("gold_batch")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")  # Less noise; use "INFO" or "DEBUG" to troubleshoot

    sql_dir = _REPO_ROOT / "sql"
    register_silver_views(spark, paths)

    # Daily sales: partition by order_date for efficient date-range reads
    gold_daily_sales_path = paths.get("gold_daily_sales")
    if gold_daily_sales_path:
        run_gold_sql_and_write(
            spark,
            sql_dir / "gold_daily_sales.sql",
            gold_daily_sales_path,
            partition_by=["order_date"],
        )

    gold_customer_360_path = paths.get("gold_customer_360")
    if gold_customer_360_path:
        run_gold_sql_and_write(
            spark,
            sql_dir / "gold_customer_360.sql",
            gold_customer_360_path,
        )

    gold_restaurant_metrics_path = paths.get("gold_restaurant_metrics")
    if gold_restaurant_metrics_path:
        run_gold_sql_and_write(
            spark,
            sql_dir / "gold_restaurant_metrics.sql",
            gold_restaurant_metrics_path,
        )

    print("Gold batch completed.")


if __name__ == "__main__":
    main()
