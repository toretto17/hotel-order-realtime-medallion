"""
Lesson 2: Bronze — Raw ingestion from Kafka to object storage (Parquet).

Reads from Kafka topic (orders), adds metadata columns (_ingestion_ts, _source,
_partition, _offset), and writes append-only to Bronze path. Checkpoint ensures
exactly-once semantics: Spark commits Kafka offset only after successful write.

Aiven Kafka only. Requires .env with KAFKA_BOOTSTRAP_SERVERS and SSL cert paths (see docs/AIVEN_SETUP_STEP_BY_STEP.md).
Run from repo root: make bronze (uses scripts/run_bronze.sh which loads .env and spark-submit with Kafka connector).
One-shot micro-batch: TRIGGER_AVAILABLE_NOW=1 make bronze
Spark 3.x: set spark_packages in config/pipeline.yaml to spark-sql-kafka-0-10_2.12:3.5.0.
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
from streaming.postgres_sink import is_enabled as postgres_enabled, write_bronze_batch


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

    # Optional: SSL/SASL for managed Kafka (Aiven, Confluent Cloud)
    security_protocol = (kafka.get("security_protocol") or "").strip().upper()
    if security_protocol in ("SSL", "SASL_SSL", "SASL_PLAINTEXT"):
        read_opts.append(("kafka.security.protocol", security_protocol))
    if security_protocol in ("SSL", "SASL_SSL"):
        ca = (kafka.get("ssl_ca_location") or "").strip()
        if ca:
            read_opts.append(("kafka.ssl.truststore.location", ca))
            read_opts.append(("kafka.ssl.truststore.type", "PEM"))
        # Client certificate (e.g. Aiven service.cert + service.key). Kafka Java client expects
        # PEM *content* for keystore.certificate.chain and keystore.key, not file paths.
        cert_path = (kafka.get("ssl_cert_location") or "").strip()
        key_path = (kafka.get("ssl_key_location") or "").strip()
        if cert_path and key_path:
            cert_path = Path(cert_path)
            key_path = Path(key_path)
            if cert_path.is_file() and key_path.is_file():
                cert_pem = cert_path.read_text()
                key_pem = key_path.read_text()
                read_opts.append(("kafka.ssl.keystore.type", "PEM"))
                read_opts.append(("kafka.ssl.keystore.certificate.chain", cert_pem))
                read_opts.append(("kafka.ssl.keystore.key", key_pem))
            else:
                raise FileNotFoundError(
                    f"SSL cert/key files not found: cert={cert_path!s} key={key_path!s}. "
                    "Set KAFKA_SSL_CERT_LOCATION and KAFKA_SSL_KEY_LOCATION in .env to PEM file paths."
                )
    if security_protocol in ("SASL_SSL", "SASL_PLAINTEXT"):
        mechanism = (kafka.get("sasl_mechanism") or "PLAIN").strip()
        read_opts.append(("kafka.sasl.mechanism", mechanism))
        username = (kafka.get("sasl_username") or "").strip()
        password = (kafka.get("sasl_password") or "").strip()
        if username and password:
            if mechanism in ("SCRAM-SHA-256", "SCRAM-SHA-512"):
                jaas = (
                    'org.apache.kafka.common.security.scram.ScramLoginModule required '
                    f'username="{username}" password="{password}";'
                )
            else:
                jaas = (
                    'org.apache.kafka.common.security.plain.PlainLoginModule required '
                    f'username="{username}" password="{password}";'
                )
            read_opts.append(("kafka.sasl.jaas.config", jaas))

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
    # 3. Write to Bronze (Parquet + optional Postgres) with checkpoint
    # -------------------------------------------------------------------------
    pg_enabled = postgres_enabled(config)

    def _foreach_batch(batch_df, batch_id):  # noqa: B008
        # Parquet first (same as before)
        batch_df.write.mode("append").partitionBy("_ingestion_date").parquet(bronze_path)
        # Postgres sync (idempotent: ON CONFLICT DO NOTHING)
        if pg_enabled:
            write_bronze_batch(batch_df, config)

    write_stream = (
        stream.writeStream.outputMode("append")
        .foreachBatch(_foreach_batch)
        .option("checkpointLocation", checkpoint_path)
    )
    if use_available_now:
        query = write_stream.trigger(availableNow=True).start()
    else:
        query = write_stream.trigger(processingTime=trigger_interval).start()

    print(f"Bronze job started: reading from Kafka topic '{topic}', writing to {bronze_path}")
    if pg_enabled:
        print("  Postgres sync: enabled (medallion.bronze_orders)")
    print(f"Checkpoint: {checkpoint_path}")
    query.awaitTermination()

    # -------------------------------------------------------------------------
    # 4. Report how many rows were actually written this run
    # -------------------------------------------------------------------------
    total_rows = sum(int(p.get("numInputRows", 0)) for p in (query.recentProgress or []))

    # Write signal file so run_pipeline.sh knows whether to continue to Silver
    signal_file = Path(checkpoint_path) / ".last_run_rows"
    signal_file.parent.mkdir(parents=True, exist_ok=True)
    signal_file.write_text(str(total_rows))

    divider = "─" * 62
    if total_rows == 0:
        print(f"\n{divider}")
        print("  Bronze: no new messages found in Kafka topic.")
        print("  The topic is fully up to date — nothing written to Bronze.")
        print(f"{divider}\n")
    else:
        print(f"\n{divider}")
        print(f"  Bronze: wrote {total_rows} new row(s) → {bronze_path}")
        print(f"{divider}\n")


def main() -> None:
    config = load_config()
    spark = (
        SparkSession.builder.appName("bronze_orders")
        .config("spark.sql.streaming.checkpointLocation", get_paths_config(config).get("checkpoint_bronze", "/tmp/check"))
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")  # Less noise; use "INFO" or "DEBUG" to troubleshoot
    create_bronze_stream(spark, config)


if __name__ == "__main__":
    main()
