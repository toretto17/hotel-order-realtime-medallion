"""
Lesson 3: Silver — Cleansing, deduplication, watermark.

Reads from Bronze (Parquet), parses JSON order payload, deduplicates by order_id
with event-time watermark, writes to Silver fact_orders (and optionally fact_order_items).

Run (from repo root; Bronze must have written data first):
  spark-submit streaming/silver_fact_orders.py
  TRIGGER_AVAILABLE_NOW=1 spark-submit streaming/silver_fact_orders.py  # one micro-batch then exit

Requires: BASE_PATH set (e.g. /tmp/medallion); Bronze path must exist and have Parquet data.
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
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from streaming.config_loader import (
    get_paths_config,
    get_streaming_config,
    load_config,
)

# Bronze Parquet schema (required for readStream — Spark does not infer schema for file streams).
# When reading partitioned Parquet, Spark adds partition columns from the path; include _ingestion_date so schema matches.
BRONZE_PARQUET_SCHEMA = StructType([
    StructField("value", StringType(), nullable=True),
    StructField("_ingestion_ts", TimestampType(), nullable=False),
    StructField("_source", StringType(), nullable=False),
    StructField("_partition", IntegerType(), nullable=True),
    StructField("_offset", LongType(), nullable=True),
    StructField("_topic", StringType(), nullable=True),
    StructField("_ingestion_date", StringType(), nullable=True),  # from partition path
])

# Spark schema for order JSON (value column from Bronze).
# Schema evolution: add new optional fields here as nullable=True so old events still parse.
# New fields (e.g. discount_code, festival, seasonal_food) are then selected into fact_orders.
ORDER_JSON_SCHEMA = StructType([
    StructField("order_id", StringType(), nullable=False),
    StructField("order_timestamp", StringType(), nullable=False),
    StructField("restaurant_id", StringType(), nullable=False),
    StructField("customer_id", StringType(), nullable=False),
    StructField("order_type", StringType(), nullable=False),
    StructField("items", ArrayType(StructType([
        StructField("item_id", StringType()),
        StructField("name", StringType()),
        StructField("category", StringType()),
        StructField("quantity", IntegerType()),
        StructField("unit_price", DoubleType()),
        StructField("subtotal", DoubleType()),
    ])), nullable=False),
    StructField("total_amount", DoubleType(), nullable=False),
    StructField("payment_method", StringType(), nullable=False),
    StructField("order_status", StringType(), nullable=False),
    # Optional fields (schema evolution): source can send these later; old events have null.
    StructField("discount_code", StringType(), nullable=True),
    StructField("festival", StringType(), nullable=True),
    StructField("seasonal_food", BooleanType(), nullable=True),
])


def create_silver_stream(spark: SparkSession, config: dict) -> None:
    """
    Bronze (Parquet) -> parse JSON -> watermark + dedup by order_id -> Silver fact_orders.
    Uses config for paths, checkpoint, watermark delay, and trigger.
    """
    paths = get_paths_config(config)
    streaming_cfg = get_streaming_config(config)

    bronze_path = paths["bronze_orders"]
    silver_orders_path = paths["silver_orders"]
    silver_order_items_path = paths.get("silver_order_items")
    checkpoint_orders = paths["checkpoint_silver"]
    # Use a subdir so fact_orders and fact_order_items don't share the same checkpoint root
    checkpoint_order_items = checkpoint_orders.rstrip("/") + "_order_items"

    watermark_delay = streaming_cfg.get("watermark_delay", "10 minutes")

    # -------------------------------------------------------------------------
    # 1. Read from Bronze (file stream — new Parquet files as they appear)
    # Schema required: Spark does not infer schema for streaming file sources.
    # -------------------------------------------------------------------------
    bronze = spark.readStream.schema(BRONZE_PARQUET_SCHEMA).format("parquet").load(bronze_path)

    # -------------------------------------------------------------------------
    # 2. Parse JSON value and flatten order-level columns
    # -------------------------------------------------------------------------
    parsed = bronze.select(
        F.from_json(F.col("value"), ORDER_JSON_SCHEMA).alias("order"),
        F.col("_ingestion_ts"),
        F.col("_partition"),
        F.col("_offset"),
    )
    orders = parsed.select(
        F.col("order.order_id").alias("order_id"),
        F.col("order.order_timestamp").alias("order_timestamp"),
        F.col("order.restaurant_id").alias("restaurant_id"),
        F.col("order.customer_id").alias("customer_id"),
        F.col("order.order_type").alias("order_type"),
        F.col("order.total_amount").alias("total_amount"),
        F.col("order.payment_method").alias("payment_method"),
        F.col("order.order_status").alias("order_status"),
        F.col("order.items").alias("items"),
        F.col("order.discount_code").alias("discount_code"),
        F.col("order.festival").alias("festival"),
        F.col("order.seasonal_food").alias("seasonal_food"),
        F.col("_ingestion_ts").alias("_ingestion_ts"),
        F.col("_partition").alias("_partition"),
        F.col("_offset").alias("_offset"),
    )

    # Event-time column for watermark (must be timestamp type).
    # Strip timezone suffix (Z or +00:00) and parse date-time only to avoid Spark parse errors.
    order_ts_str = F.regexp_replace(
        F.regexp_replace(F.col("order_timestamp"), "Z$", ""),
        "\\+00:00$", "",
    )
    # try_to_timestamp returns NULL on parse failure so coalesce can try the next format (Spark 3.5+).
    # Format must be F.lit() so Spark treats it as a string literal, not a column name.
    orders = orders.withColumn(
        "order_timestamp_ts",
        F.coalesce(
            F.try_to_timestamp(order_ts_str, F.lit("yyyy-MM-dd'T'HH:mm:ss.SSS")),
            F.try_to_timestamp(order_ts_str, F.lit("yyyy-MM-dd'T'HH:mm:ss")),
        ),
    )

    # -------------------------------------------------------------------------
    # 3. Deduplicate by order_id (keep latest per key within watermark)
    # -------------------------------------------------------------------------
    deduped = (
        orders.withWatermark("order_timestamp_ts", watermark_delay)
        .dropDuplicates(["order_id"])
    )

    # Silver fact_orders: order-level columns (including optional schema-evolution fields)
    fact_orders = deduped.select(
        F.col("order_id"),
        F.col("order_timestamp_ts").alias("order_timestamp"),
        F.col("restaurant_id"),
        F.col("customer_id"),
        F.col("order_type"),
        F.col("total_amount"),
        F.col("payment_method"),
        F.col("order_status"),
        F.col("discount_code"),
        F.col("festival"),
        F.col("seasonal_food"),
        F.col("_ingestion_ts"),
        F.col("_partition"),
        F.col("_offset"),
    )

    # -------------------------------------------------------------------------
    # 4. Trigger: periodic or availableNow
    # -------------------------------------------------------------------------
    trigger_option = os.environ.get("TRIGGER_AVAILABLE_NOW", "").strip().lower()
    if trigger_option in ("1", "true", "yes"):
        use_available_now = True
    else:
        use_available_now = False
        trigger_interval = streaming_cfg.get("trigger_interval", "1 minute")

    # -------------------------------------------------------------------------
    # 5. Write fact_orders to Silver
    # -------------------------------------------------------------------------
    write_orders = (
        fact_orders.writeStream.outputMode("append")
        .format("parquet")
        .option("path", silver_orders_path)
        .option("checkpointLocation", checkpoint_orders)
    )
    if use_available_now:
        query_orders = write_orders.trigger(availableNow=True).start()
    else:
        query_orders = write_orders.trigger(processingTime=trigger_interval).start()

    print(f"Silver fact_orders started: reading from {bronze_path}, writing to {silver_orders_path}")
    print(f"Checkpoint: {checkpoint_orders}")
    print(f"Watermark: {watermark_delay} on order_timestamp")

    # Optional: fact_order_items (explode items; no dedup in this lesson)
    if silver_order_items_path:
        # Re-read Bronze for the items stream (same source, different transformation)
        bronze2 = spark.readStream.schema(BRONZE_PARQUET_SCHEMA).format("parquet").load(bronze_path)
        parsed2 = bronze2.select(
            F.from_json(F.col("value"), ORDER_JSON_SCHEMA).alias("order"),
        )
        parsed2 = parsed2.select(
            F.col("order.order_id").alias("order_id"),
            F.col("order.order_timestamp").alias("order_timestamp"),
            F.explode(F.col("order.items")).alias("item"),
        )
        order_ts_str = F.regexp_replace(
            F.regexp_replace(F.col("order_timestamp"), "Z$", ""),
            "\\+00:00$", "",
        )
        order_items = parsed2.select(
            F.col("order_id"),
            F.coalesce(
                F.try_to_timestamp(order_ts_str, F.lit("yyyy-MM-dd'T'HH:mm:ss.SSS")),
                F.try_to_timestamp(order_ts_str, F.lit("yyyy-MM-dd'T'HH:mm:ss")),
            ).alias("order_timestamp"),
            F.col("item.item_id").alias("item_id"),
            F.col("item.name").alias("item_name"),
            F.col("item.category").alias("category"),
            F.col("item.quantity").alias("quantity"),
            F.col("item.unit_price").alias("unit_price"),
            F.col("item.subtotal").alias("subtotal"),
        )
        # Deduplicate by (order_id, item_id) so one row per order-line, consistent with fact_orders.
        order_items = order_items.withWatermark("order_timestamp", watermark_delay).dropDuplicates(["order_id", "item_id"])
        write_items = (
            order_items.writeStream.outputMode("append")
            .format("parquet")
            .option("path", silver_order_items_path)
            .option("checkpointLocation", checkpoint_order_items)
        )
        if use_available_now:
            write_items.trigger(availableNow=True).start()
        else:
            write_items.trigger(processingTime=trigger_interval).start()
        print(f"Silver fact_order_items started: writing to {silver_order_items_path}")

    query_orders.awaitTermination()


def main() -> None:
    config = load_config()
    spark = (
        SparkSession.builder.appName("silver_fact_orders")
        .config("spark.sql.streaming.checkpointLocation", get_paths_config(config).get("checkpoint_silver", "/tmp/check_silver"))
        .getOrCreate()
    )
    create_silver_stream(spark, config)


if __name__ == "__main__":
    main()
