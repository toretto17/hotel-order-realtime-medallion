"""
Lesson 2: Bronze — Raw ingestion from Kafka to object storage (Parquet).

Reads from Kafka topic (orders), adds metadata columns (_ingestion_ts, _source,
_partition, _offset), and writes append-only to Bronze path. Checkpoint ensures
exactly-once semantics: Spark commits Kafka offset only after successful write.

Run (from repo root). You must add the Kafka connector with --packages (Spark does not include it by default):

  spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2 streaming/bronze_orders.py

With env and one-shot micro-batch:
  BASE_PATH=/tmp/medallion KAFKA_BOOTSTRAP_SERVERS=localhost:9092 spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2 streaming/bronze_orders.py
  TRIGGER_AVAILABLE_NOW=1 BASE_PATH=/tmp/medallion spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2 streaming/bronze_orders.py

If your Spark is 3.x, use spark-sql-kafka-0-10_2.12:3.5.0 (or match your Spark version).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root on path so we can import streaming.config_loader and streaming.schemas
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from streaming.config_loader import (
    get_kafka_config,
    get_paths_config,
    get_streaming_config,
    load_config,
)


def create_bronze_stream(spark: SparkSession, config: dict) -> None:
    """
    Build the Bronze streaming query: Kafka -> add metadata -> write Parquet.
    Uses config for Kafka options, paths, checkpoint, and trigger.
    """
    kafka = get_kafka_config(config)
    paths = get_paths_config(config)
    streaming_cfg = get_streaming_config(config)

    bootstrap = kafka["bootstrap_servers"]
    topic = kafka["topic_orders"]
    starting_offsets = kafka.get("starting_offsets", "latest")

    checkpoint_path = paths["checkpoint_bronze"]
    bronze_path = paths["bronze_orders"]

    # -------------------------------------------------------------------------
    # 1. Read from Kafka (Structured Streaming)
    # -------------------------------------------------------------------------
    read_opts = [
        ("kafka.bootstrap.servers", bootstrap),
        ("subscribe", topic),
        ("startingOffsets", starting_offsets),
        ("failOnDataLoss", streaming_cfg.get("fail_on_data_loss", True)),
    ]
    max_offsets = streaming_cfg.get("max_offsets_per_trigger")
    if max_offsets is not None:
        read_opts.append(("maxOffsetsPerTrigger", max_offsets))

    df = spark.readStream.format("kafka").options(**dict(read_opts)).load()

    # Kafka source schema: key, value (binary), topic, partition, offset, timestamp, timestampType
    # Cast value to string (we expect JSON); keep partition and offset for replay/debug
    stream = df.select(
        F.col("value").cast(StringType()).alias("value"),  # raw payload
        F.current_timestamp().alias("_ingestion_ts"),
        F.lit("kafka").alias("_source"),
        F.col("partition").alias("_partition"),
        F.col("offset").alias("_offset"),
        F.col("topic").alias("_topic"),
    )

    # Optional: partition Bronze by ingestion date for efficient reads and retention
    stream = stream.withColumn(
        "_ingestion_date",
        F.to_date(F.col("_ingestion_ts")),
    )

    # -------------------------------------------------------------------------
    # 2. Trigger: periodic (e.g. 1 minute) or availableNow for one-shot batch
    # -------------------------------------------------------------------------
    trigger_option = os.environ.get("TRIGGER_AVAILABLE_NOW", "").strip().lower()
    if trigger_option in ("1", "true", "yes"):
        use_available_now = True
    else:
        use_available_now = False
        trigger_interval = streaming_cfg.get("trigger_interval", "1 minute")

    # -------------------------------------------------------------------------
    # 3. Write to Bronze (Parquet) with checkpoint
    # -------------------------------------------------------------------------
    write_stream = (
        stream.writeStream.outputMode("append")
        .format("parquet")
        .option("path", bronze_path)
        .option("checkpointLocation", checkpoint_path)
        .partitionBy("_ingestion_date")
    )
    if use_available_now:
        query = write_stream.trigger(availableNow=True).start()
    else:
        query = write_stream.trigger(processingTime=trigger_interval).start()

    print(f"Bronze job started: reading from Kafka topic '{topic}', writing to {bronze_path}")
    print(f"Checkpoint: {checkpoint_path}")
    query.awaitTermination()


def main() -> None:
    config = load_config()
    spark = (
        SparkSession.builder.appName("bronze_orders")
        .config("spark.sql.streaming.checkpointLocation", get_paths_config(config).get("checkpoint_bronze", "/tmp/check"))
        .getOrCreate()
    )
    create_bronze_stream(spark, config)


if __name__ == "__main__":
    main()
