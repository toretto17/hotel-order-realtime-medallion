"""
Lesson 3: Silver — Cleansing, deduplication, partition-aware upsert.

Reads from Bronze (Parquet stream), parses JSON, deduplicates by order_id keeping
the LATEST event (so status updates like pending→done always win), and writes to
Silver using foreachBatch + partition-aware upsert.

Why foreachBatch + partition-aware upsert (not streaming groupBy/agg):
  - groupBy + agg in streaming requires outputMode("update"), but Parquet sink
    does not support "update" in Spark 4.x. foreachBatch sidesteps all output
    mode restrictions by treating each micro-batch as a plain batch write.
  - Partition-aware: Silver is partitioned by order_date. Each trigger only reads
    and rewrites the affected date partitions (not the whole table), so this scales
    to millions of rows without a full-table scan every trigger.
  - Dynamic partition overwrite (spark.sql.sources.partitionOverwriteMode=dynamic)
    ensures only partitions present in the new data are overwritten; historical
    partitions are untouched.

Upsert logic per micro-batch:
  1. Parse + clean new Bronze records.
  2. Dedupe within the new batch by order_id → keep latest by order_timestamp_ts
     (handles bursts of 10,000+ orders where the same order_id may appear twice).
  3. Add order_date partition column.
  4. Broadcast the small new-batch order_ids (anti-join key).
  5. For each affected order_date partition:
       - Read existing Silver rows for that date only.
       - Anti-join: drop existing rows whose order_id appears in the new batch
         (they will be replaced by the latest version).
       - Union with new batch rows for that date.
  6. Write merged result — dynamic partition overwrite touches only affected dates.

Run (from repo root; Bronze must have written data first):
  make silver                             # continuous streaming
  TRIGGER_AVAILABLE_NOW=1 make silver     # one micro-batch then exit (use in make pipeline)

Requires: BASE_PATH set (e.g. /tmp/medallion); Bronze path must exist and have Parquet data.
First run after changing from old Silver: make clean-silver first to drop stale checkpoints.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pyspark.sql import DataFrame, SparkSession
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
from streaming.postgres_sink import is_enabled as postgres_enabled, write_silver_items_batch, write_silver_orders_batch

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

# Bronze Parquet schema: Spark requires explicit schema for readStream on files.
# Partition column: Bronze uses "ingestion_date" (no leading _) so Spark file source
# sees the path (Hadoop excludes dirs starting with "_").
BRONZE_PARQUET_SCHEMA = StructType([
    StructField("value", StringType(), nullable=True),
    StructField("_ingestion_ts", TimestampType(), nullable=False),
    StructField("_source", StringType(), nullable=False),
    StructField("_partition", IntegerType(), nullable=True),
    StructField("_offset", LongType(), nullable=True),
    StructField("_topic", StringType(), nullable=True),
    StructField("_ingestion_date", StringType(), nullable=True),
    StructField("ingestion_date", StringType(), nullable=True),  # partition path column (new Bronze)
])

# Order JSON schema: nullable=True on optional fields for schema evolution.
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
    StructField("discount_code", StringType(), nullable=True),
    StructField("festival", StringType(), nullable=True),
    StructField("seasonal_food", BooleanType(), nullable=True),
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_orders(bronze_df: DataFrame) -> DataFrame:
    """Parse Bronze value JSON → flat order-level columns with typed order_timestamp."""
    parsed = bronze_df.select(
        F.from_json(F.col("value"), ORDER_JSON_SCHEMA).alias("o"),
        F.col("_ingestion_ts"),
        F.col("_partition"),
        F.col("_offset"),
    )
    orders = parsed.select(
        F.col("o.order_id").alias("order_id"),
        F.col("o.order_timestamp").alias("order_timestamp_raw"),
        F.col("o.restaurant_id").alias("restaurant_id"),
        F.col("o.customer_id").alias("customer_id"),
        F.col("o.order_type").alias("order_type"),
        F.col("o.total_amount").alias("total_amount"),
        F.col("o.payment_method").alias("payment_method"),
        F.col("o.order_status").alias("order_status"),
        F.col("o.items").alias("items"),
        F.col("o.discount_code").alias("discount_code"),
        F.col("o.festival").alias("festival"),
        F.col("o.seasonal_food").alias("seasonal_food"),
        F.col("_ingestion_ts"),
        F.col("_partition"),
        F.col("_offset"),
    )
    # Parse order_timestamp string → timestamp (strip Z / +00:00 suffixes).
    ts_str = F.regexp_replace(
        F.regexp_replace(F.col("order_timestamp_raw"), "Z$", ""),
        "\\+00:00$", "",
    )
    orders = orders.withColumn(
        "order_timestamp",
        F.coalesce(
            F.try_to_timestamp(ts_str, F.lit("yyyy-MM-dd'T'HH:mm:ss.SSS")),
            F.try_to_timestamp(ts_str, F.lit("yyyy-MM-dd'T'HH:mm:ss")),
        ),
    ).drop("order_timestamp_raw")
    return orders


def _dedup_batch_latest(batch_df: DataFrame) -> DataFrame:
    """
    Within a single micro-batch, keep the LATEST row per order_id.
    Uses window function (row_number) so it works as a plain batch operation
    inside foreachBatch — no streaming aggregation, no output mode conflict.
    """
    from pyspark.sql.window import Window
    w = Window.partitionBy("order_id").orderBy(F.col("order_timestamp").desc_nulls_last())
    return (
        batch_df
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


def _upsert_partition_aware(
    spark: SparkSession,
    new_df: DataFrame,
    silver_path: str,
    partition_col: str = "order_date",
    dedup_key: str = "order_id",
    ts_col: str = "order_timestamp",
) -> None:
    """
    Partition-aware upsert into Silver (plain Parquet, no Delta Lake).

    Strategy:
      1. Add partition column (order_date) to the new batch.
      2. Dedupe new batch: keep latest row per dedup_key (latest status wins).
      3. Find affected partitions (order_date values in the new batch).
      4. For each affected partition:
           a. Read existing Silver rows for that partition only (not full table).
           b. Broadcast new-batch order_ids (small set) → anti-join to drop
              stale existing rows (they will be replaced by the new version).
           c. Union existing (without stale) + new batch for that partition.
      5. Write merged result with dynamic partition overwrite:
           - Only the affected date partitions are overwritten.
           - Historical partitions are completely untouched.

    Scales well even with 10,000+ orders per trigger because:
      - We only read/rewrite the 1-2 date partitions in the current batch.
      - The broadcast is on the small new-batch ids, not the large Silver table.
    """
    silver_exists = Path(silver_path).exists() and any(Path(silver_path).iterdir())

    # Add order_date partition column from the timestamp column.
    new_df = new_df.withColumn(partition_col, F.to_date(F.col(ts_col)))

    # Dedupe within the new batch: latest row per dedup_key.
    new_df = _dedup_batch_latest(new_df)

    if not silver_exists:
        # First run: no existing Silver; just write the new data.
        (
            new_df.write
            .mode("overwrite")
            .partitionBy(partition_col)
            .parquet(silver_path)
        )
        print(f"[Silver] First write: {new_df.count()} rows → {silver_path}")
        return

    # Affected partition values in the new batch (typically 1-2 dates).
    affected_dates = [
        row[partition_col]
        for row in new_df.select(partition_col).distinct().collect()
        if row[partition_col] is not None
    ]

    if not affected_dates:
        print("[Silver] No valid order_date in batch; skipping write.")
        return

    # Build the merged DataFrame for all affected partitions in one pass.
    # We collect affected-date frames and union them with existing Silver frames.
    merged_parts = []

    for date_val in affected_dates:
        date_str = str(date_val)
        partition_path = f"{silver_path.rstrip('/')}/{partition_col}={date_str}"

        # New rows for this date.
        new_part = new_df.filter(F.col(partition_col) == date_val)

        existing_path = Path(partition_path)
        if existing_path.exists() and any(existing_path.iterdir()):
            # Read only this date's partition (not the whole Silver table).
            existing_part = (
                spark.read
                .option("mergeSchema", "true")
                .parquet(partition_path)
            )
            # Broadcast the small new-batch order_ids for the anti-join.
            # This avoids shuffling the large existing partition.
            new_ids = new_part.select(dedup_key).distinct()
            existing_without_updated = existing_part.join(
                F.broadcast(new_ids),
                on=dedup_key,
                how="left_anti",
            )
            # unionByName: match columns by name, not position — safe against
            # any column-order differences between old parquet files and new batch.
            merged_part = existing_without_updated.unionByName(
                new_part.drop(partition_col), allowMissingColumns=True
            )
        else:
            merged_part = new_part.drop(partition_col)

        # Re-attach the partition column value (needed for partitionBy write).
        merged_part = merged_part.withColumn(partition_col, F.lit(date_val).cast("date"))
        merged_parts.append(merged_part)

    # unionByName across partitions too — column order may vary per date partition.
    if not merged_parts:
        return
    merged = merged_parts[0]
    for part in merged_parts[1:]:
        merged = merged.unionByName(part, allowMissingColumns=True)

    # Dynamic partition overwrite: only overwrite the partitions present in merged.
    # Historical partitions (other dates) are left untouched.
    (
        merged.write
        .mode("overwrite")
        .option("partitionOverwriteMode", "dynamic")
        .partitionBy(partition_col)
        .parquet(silver_path)
    )
    print(f"[Silver] Upserted {len(affected_dates)} partition(s) {affected_dates} → {silver_path}")


def _upsert_items_partition_aware(
    spark: SparkSession,
    new_items: DataFrame,
    silver_items_path: str,
    partition_col: str = "order_date",
) -> None:
    """
    Same partition-aware upsert for fact_order_items.
    Dedup key: (order_id, item_id) — one row per order line.
    """
    silver_exists = (
        Path(silver_items_path).exists()
        and any(Path(silver_items_path).iterdir())
    )

    new_items = new_items.withColumn(partition_col, F.to_date(F.col("order_timestamp")))

    # Dedupe within new batch: for same (order_id, item_id) keep latest by order_timestamp.
    from pyspark.sql.window import Window
    w = Window.partitionBy("order_id", "item_id").orderBy(F.col("order_timestamp").desc_nulls_last())
    new_items = (
        new_items
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )

    if not silver_exists:
        (
            new_items.write
            .mode("overwrite")
            .partitionBy(partition_col)
            .parquet(silver_items_path)
        )
        return

    affected_dates = [
        row[partition_col]
        for row in new_items.select(partition_col).distinct().collect()
        if row[partition_col] is not None
    ]
    if not affected_dates:
        return

    merged_parts = []
    for date_val in affected_dates:
        date_str = str(date_val)
        partition_path = f"{silver_items_path.rstrip('/')}/{partition_col}={date_str}"

        new_part = new_items.filter(F.col(partition_col) == date_val)

        existing_path = Path(partition_path)
        if existing_path.exists() and any(existing_path.iterdir()):
            existing_part = spark.read.option("mergeSchema", "true").parquet(partition_path)
            new_keys = new_part.select("order_id", "item_id").distinct()
            existing_clean = existing_part.join(
                F.broadcast(new_keys),
                on=["order_id", "item_id"],
                how="left_anti",
            )
            # unionByName: match columns by name, not position.
            merged_part = existing_clean.unionByName(
                new_part.drop(partition_col), allowMissingColumns=True
            )
        else:
            merged_part = new_part.drop(partition_col)

        merged_part = merged_part.withColumn(partition_col, F.lit(date_val).cast("date"))
        merged_parts.append(merged_part)

    if not merged_parts:
        return
    merged = merged_parts[0]
    for part in merged_parts[1:]:
        merged = merged.unionByName(part, allowMissingColumns=True)

    (
        merged.write
        .mode("overwrite")
        .option("partitionOverwriteMode", "dynamic")
        .partitionBy(partition_col)
        .parquet(silver_items_path)
    )
    print(f"[Silver items] Upserted {len(affected_dates)} partition(s) {affected_dates} → {silver_items_path}")


# ---------------------------------------------------------------------------
# Main stream builder
# ---------------------------------------------------------------------------

def create_silver_stream(spark: SparkSession, config: dict) -> None:
    """
    Bronze (Parquet stream) → parse → foreachBatch upsert → Silver (partitioned Parquet).

    foreachBatch approach:
      - Sidesteps all Spark streaming output-mode restrictions (no groupBy/agg in stream).
      - Each micro-batch is a plain batch operation: read Bronze new files, upsert Silver.
      - Partition-aware: only affected order_date partitions are read/rewritten.
      - Dynamic partition overwrite: historical partitions are never touched.
      - Scales to large hotels / high-volume bursts (10,000+ orders per trigger).
    """
    paths = get_paths_config(config)
    streaming_cfg = get_streaming_config(config)

    bronze_path = paths["bronze_orders"]
    silver_orders_path = paths["silver_orders"]
    silver_order_items_path = paths.get("silver_order_items")
    checkpoint_orders = paths["checkpoint_silver"]
    checkpoint_order_items = checkpoint_orders.rstrip("/") + "_order_items"

    trigger_option = os.environ.get("TRIGGER_AVAILABLE_NOW", "").strip().lower()
    use_available_now = trigger_option in ("1", "true", "yes")
    trigger_interval = streaming_cfg.get("trigger_interval", "1 minute")

    # Enable dynamic partition overwrite so only affected date partitions
    # are overwritten; all other partitions on disk are left untouched.
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

    # -------------------------------------------------------------------------
    # 1. Read Bronze as a file stream (only new files since last checkpoint).
    #    recursiveFileLookup=true so partition subdirs (e.g. ingestion_date=...) are scanned.
    # -------------------------------------------------------------------------
    bronze_stream = (
        spark.readStream
        .schema(BRONZE_PARQUET_SCHEMA)
        .format("parquet")
        .option("recursiveFileLookup", "true")
        .load(bronze_path)
    )

    # -------------------------------------------------------------------------
    # 2. Parse JSON → flat order columns + typed timestamp.
    # -------------------------------------------------------------------------
    parsed_stream = _parse_orders(bronze_stream)

    # -------------------------------------------------------------------------
    # 3. fact_orders: foreachBatch upsert (partition-aware, latest-wins dedup).
    # -------------------------------------------------------------------------
    fact_orders_stream = parsed_stream.select(
        "order_id", "order_timestamp", "restaurant_id", "customer_id",
        "order_type", "total_amount", "payment_method", "order_status",
        "discount_code", "festival", "seasonal_food",
        "_ingestion_ts", "_partition", "_offset",
    )

    def upsert_fact_orders(batch_df: DataFrame, batch_id: int) -> None:
        if batch_df.isEmpty():
            print(f"[Silver] Batch {batch_id}: empty, skipping.")
            return
        print(f"[Silver] Batch {batch_id}: processing rows from Bronze.")
        _upsert_partition_aware(
            spark=spark,
            new_df=batch_df,
            silver_path=silver_orders_path,
        )
        # Postgres sync: only after Parquet write succeeds. Fail batch if Postgres fails (no checkpoint).
        if postgres_enabled(config):
            orders_with_date = batch_df.withColumn("order_date", F.to_date(F.col("order_timestamp")))
            write_silver_orders_batch(orders_with_date, config)

    write_orders = (
        fact_orders_stream.writeStream
        .foreachBatch(upsert_fact_orders)
        .option("checkpointLocation", checkpoint_orders)
    )
    if use_available_now:
        query_orders = write_orders.trigger(availableNow=True).start()
    else:
        query_orders = write_orders.trigger(processingTime=trigger_interval).start()

    print(f"[Silver] fact_orders stream started.")
    print(f"  Bronze path : {bronze_path}")
    print(f"  Silver path : {silver_orders_path} (partitioned by order_date)")
    if postgres_enabled(config):
        print("  Postgres sync: enabled (medallion.silver_orders, silver_order_items)")
    print(f"  Checkpoint  : {checkpoint_orders}")
    print(f"  Trigger     : {'availableNow' if use_available_now else trigger_interval}")

    query_orders.awaitTermination()

    # -------------------------------------------------------------------------
    # 4. fact_order_items: run after orders complete (sequential to avoid NPE
    #    when process exits while the second stream is still running).
    # -------------------------------------------------------------------------
    if silver_order_items_path:
        bronze_stream2 = (
            spark.readStream
            .schema(BRONZE_PARQUET_SCHEMA)
            .format("parquet")
            .option("recursiveFileLookup", "true")
            .load(bronze_path)
        )
        parsed_stream2 = _parse_orders(bronze_stream2)

        items_stream = parsed_stream2.select(
            F.col("order_id"),
            F.col("order_timestamp"),
            F.explode(F.col("items")).alias("item"),
        ).select(
            F.col("order_id"),
            F.col("order_timestamp"),
            F.col("item.item_id").alias("item_id"),
            F.col("item.name").alias("item_name"),
            F.col("item.category").alias("category"),
            F.col("item.quantity").alias("quantity"),
            F.col("item.unit_price").alias("unit_price"),
            F.col("item.subtotal").alias("subtotal"),
        )

        def upsert_fact_items(batch_df: DataFrame, batch_id: int) -> None:
            if batch_df.isEmpty():
                return
            _upsert_items_partition_aware(
                spark=spark,
                new_items=batch_df,
                silver_items_path=silver_order_items_path,
            )
            # Postgres sync: only after Parquet write succeeds.
            if postgres_enabled(config):
                items_with_date = batch_df.withColumn("order_date", F.to_date(F.col("order_timestamp")))
                write_silver_items_batch(items_with_date, config)

        write_items = (
            items_stream.writeStream
            .foreachBatch(upsert_fact_items)
            .option("checkpointLocation", checkpoint_order_items)
        )
        if use_available_now:
            query_items = write_items.trigger(availableNow=True).start()
        else:
            query_items = write_items.trigger(processingTime=trigger_interval).start()

        print(f"[Silver] fact_order_items stream started → {silver_order_items_path}")
        query_items.awaitTermination()

    # -------------------------------------------------------------------------
    # 5. Report input rows processed and signal the pipeline.
    #    query.recentProgress is Spark's built-in progress tracking — no extra
    #    scan, no shuffle, zero cost. numInputRows = rows read from Bronze this run.
    # -------------------------------------------------------------------------
    total_rows = sum(int(p.get("numInputRows", 0)) for p in (query_orders.recentProgress or []))
    signal_file = Path(checkpoint_orders) / ".last_run_rows"
    signal_file.parent.mkdir(parents=True, exist_ok=True)
    signal_file.write_text(str(total_rows))

    divider = "─" * 62
    if total_rows == 0:
        print(f"\n{divider}")
        print("  Silver: no new Bronze data to process.")
        print("  All Bronze records were already processed in a previous run.")
        print("  (If Bronze just wrote rows in the same run, this can be file-stream timing;")
        print("   run_pipeline.sh will retry Silver once, or run: make pipeline again.)")
        print(f"{divider}\n")
    else:
        print(f"\n{divider}")
        print(f"  Silver: wrote {total_rows} order row(s) → {silver_orders_path}")
        print(f"{divider}\n")


def main() -> None:
    config = load_config()
    spark = (
        SparkSession.builder
        .appName("silver_fact_orders")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    create_silver_stream(spark, config)


if __name__ == "__main__":
    main()
