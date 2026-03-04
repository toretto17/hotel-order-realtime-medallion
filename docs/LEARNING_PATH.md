# Step-by-Step Learning Path — Realtime Order Medallion

This document is your **curriculum**. We build one concept at a time, with code and production context, so you learn deeply and can speak to it in MAANG-level interviews.

**Reference:** [ARCHITECTURE.md](../ARCHITECTURE.md) for the full design. [VIDEO_ANALYSIS.md](./VIDEO_ANALYSIS.md) maps the Databricks video to this generic design.

---

## How to Use This Path

- **One lesson per step.** Do not skip ahead; each step uses the previous one.
- **Run and experiment.** After each lesson, run the code, change one thing, see what breaks.
- **Interview prep:** At each step, you should be able to explain *why* we did it that way and what happens if we don’t.

---

## Lesson 0: Orientation (You Are Here)

**Goal:** Know the end-to-end flow and where each lesson fits.

**Concepts:**
- Data flow: Source → Kafka → Bronze (raw) → Silver (cleaned, star schema) → Gold (aggregates) → Serving.
- Your repo: `config/` (pipeline config), `streaming/` (Spark jobs), `sql/` (Gold SQL), `docs/` (design).

**Deliverable:** You’ve read ARCHITECTURE.md and this LEARNING_PATH. No code yet.

---

## Lesson 1: Data Contract & Pipeline Config

**Goal:** Define *what* flows through the system and *how* the pipeline is configured. No streaming yet.

**Concepts:**
- **Event schema:** Order event JSON — why `order_id` is the idempotency key; why we have `order_timestamp` (event time) vs processing time.
- **Schema evolution:** New fields in the source should not break Bronze; we add them in Silver.
- **Config over code:** All topic names, paths, watermarks live in `config/pipeline.yaml`; jobs read this so we can change behavior without code changes.

**Deliverables:**
- `streaming/schemas/order_events.py` — canonical order (and order_item) schema + comments.
- `streaming/config_loader.py` — load and validate `config/pipeline.yaml`; used by every job later.

**Interview angle:** “How do you ensure the same order isn’t processed twice?” → Idempotency key. “How do you handle a new field in the event?” → Schema-on-read in Bronze; explicit column in Silver.

---

## Lesson 2: Bronze — Raw Ingestion from Kafka

**Goal:** Read from Kafka and write raw events to object storage (Parquet) with metadata. One micro-batch at a time.

**Concepts:**
- **Structured Streaming + Kafka:** `spark.readStream.format("kafka")`, subscribe to topic, options (bootstrap, group, starting offsets).
- **Bronze table:** Append-only; columns = raw payload (e.g. `value` as string or parsed JSON) + `_ingestion_ts`, `_source`, `_partition`, `_offset`.
- **Checkpoint:** Why we set `checkpointLocation` and never delete it in production.

**Deliverables:**
- `streaming/bronze_orders.py` — stream from Kafka → write to Bronze path (Parquet) with checkpoint; use config from Lesson 1.
- `streaming/lesson2_check.py` — config + Spark sanity check (no Kafka required).

**Run:** Config check: `python -m streaming.lesson2_check`. Bronze job (Kafka required): `BASE_PATH=/tmp/medallion spark-submit streaming/bronze_orders.py`. One-shot: `TRIGGER_AVAILABLE_NOW=1` with same command.

**Interview angle:** “What is Bronze?” → Immutable raw copy; replayable. “How do you avoid duplicate reads from Kafka?” → Checkpoint; Spark commits offset only after successful write.

---

## Lesson 3: Silver — Cleansing, Dedup, Watermark

**Goal:** Read from Bronze, parse JSON, deduplicate by `order_id`, apply watermark, write Silver fact tables.

**Concepts:**
- **Deduplication:** `dropDuplicates(["order_id"])` with `withWatermark("order_timestamp", "10 minutes")` — only latest event per key within watermark.
- **Watermark:** Event-time vs processing-time; why we need it for late data and state cleanup.
- **Data quality:** Filter invalid rows (e.g. missing `order_id`); send failures to DLQ (we’ll implement DLQ in Lesson 6).

**Deliverables:**
- `streaming/silver_fact_orders.py` — Bronze → fact_orders (and optionally fact_order_items); dedupe + watermark; use config.

**Run:** After Bronze has written data: `make silver` or `./scripts/run_silver.sh`. One-shot: `TRIGGER_AVAILABLE_NOW=1 make silver`. Silver reads from `$BASE_PATH/bronze/orders`, writes to `$BASE_PATH/silver/orders` and `$BASE_PATH/silver/order_items`.

**Interview angle:** “How do you deduplicate in streaming?” → Watermark + dropDuplicates. “What if an event arrives 15 minutes late?” → Dropped in that window unless we use allowedLateness; we’ll cover in Lesson 5.

---

## Lesson 4: Gold — Aggregations (Batch from Silver)

**Goal:** Batch job that reads Silver and writes Gold tables (daily_sales, customer_360, restaurant_metrics). SQL-first so you see the business logic clearly.

**Concepts:**
- **Gold = pre-aggregated:** By date, by customer, by restaurant. Partitioned by `order_date` for fast reads.
- **Refresh strategy:** Daily or every N hours; orchestrated by Airflow/Cron later. For now: single batch run.
- **Structure (production):** Multiple SQL files (one per Gold table) for separation of concerns; **one** batch script (e.g. `gold_batch.py`) that runs all of them and writes to Gold paths. One entry point (`make gold`), not one giant SQL file and not three separate cron jobs. See **VIDEO_ANALYSIS.md** §7.

**Deliverables:**
- `sql/gold_daily_sales.sql` — aggregate from Silver fact_orders by order_date.
- `sql/gold_customer_360.sql` — one row per customer (orders count, total spend, etc.).
- `sql/gold_restaurant_metrics.sql` — by restaurant (optional: with reviews).
- One Spark batch script (e.g. `streaming/gold_batch.py`) that runs these and writes to Gold paths; single entry point for ops.

**Interview angle:** “Why batch for Gold and not streaming?” → Consistency, cost, and most reporting is daily; streaming Gold only if latency requirement is strict.

---

## Lesson 5: Late-Arriving Data & Allowed Lateness

**Goal:** Understand and implement a policy for events that arrive after the watermark.

**Concepts:**
- **Watermark vs allowedLateness:** Watermark drops late data after threshold; `allowedLateness` keeps state and updates aggregates for late keys.
- **Trade-off:** More state, more cost; use only where business needs it (e.g. order corrections).

**Deliverables:**
- Document in code/comments how we use `allowedLateness` in Silver (or in a streaming Gold aggregate if we add one).
- Optional: small test with “late” events to see behavior.

**Interview angle:** “How do you handle late data?” → Watermark + allowedLateness; separate “late” topic or batch correction for very late data.

---

## Lesson 6: Error Handling & DLQ

**Goal:** Invalid records never block the pipeline; they go to a Dead Letter Queue and we alert on depth.

**Concepts:**
- **DLQ:** Kafka topic or table; rows that fail validation (null key, parse error, schema mismatch) are written here with raw payload + error message.
- **Pattern:** In Silver, split stream into “valid” and “invalid”; write invalid to DLQ; pass valid downstream.

**Deliverables:**
- Extend Silver job: on parse/validation failure, write to DLQ (Kafka topic `orders_dlq` or a Delta/Parquet DLQ table); use config for DLQ path/topic.

**Interview angle:** “What happens to bad data?” → DLQ; we don’t drop silently; we alert on DLQ depth.

---

## Lesson 7: Exactly-Once & Checkpoint Deep Dive

**Goal:** Tie together: Kafka offset commit, checkpoint, and idempotent Silver/Gold writes.

**Concepts:**
- **Exactly-once:** Source (Kafka) + deterministic processing + idempotent sink. Spark: offset committed only after sink write; checkpoint stores offset.
- **Idempotent sink:** Silver/Gold: merge/upsert by key (e.g. `order_id`) so replaying the same batch doesn’t duplicate.

**Deliverables:**
- Short doc or comments in code: “Exactly-once in this pipeline” (source, processing, sink, checkpoint).
- If we use Delta: use merge in Silver write. If Parquet: overwrite by partition + batch id.

**Interview angle:** “How do you achieve exactly-once?” → Three parts: commit after write, checkpoint, idempotent sink.

---

## Lesson 8: Orchestration & CI/CD (Concept + Placeholders)

**Goal:** How the streaming job and batch Gold job are run in production; how we deploy safely.

**Concepts:**
- **Orchestration:** Streaming job runs 24/7; batch Gold runs on schedule (Airflow DAG or Cron). Same config, different entrypoints.
- **CI/CD:** Tests (unit for transforms, integration with embedded Kafka); deploy job to cluster (EMR, K8s, etc.); config from env/S3.

**Deliverables:**
- Placeholder script or doc: “Run Bronze/Silver streaming”; “Run Gold batch”; env vars for config override.
- Optional: one unit test for a transformation (e.g. parse order JSON → Row).

**Interview angle:** “How do you deploy a streaming job?” → Build artifact, submit to cluster, config from env; checkpoint for resume.

---

## Lesson 9: Observability & Production Checklist

**Goal:** Metrics, alerts, and a final checklist so the system is production-ready.

**Concepts:**
- **Metrics:** Consumer lag (Kafka), pipeline throughput, DLQ depth, processing delay (event time vs processing time).
- **Alerts:** Lag above threshold, job failure, DLQ depth > 0 (or > N).
- **Checklist:** From ARCHITECTURE.md — checkpoint backup, partitioning, resource limits, runbooks.

**Deliverables:**
- List of metrics and alerts we’d add (Prometheus/Grafana or cloud equivalent).
- Production checklist (from ARCHITECTURE) with “done” placeholders.

---

## Summary Table

| Lesson | Focus                    | Main deliverable(s)                          |
|--------|--------------------------|----------------------------------------------|
| 0      | Orientation              | Read docs                                    |
| 1      | Data contract & config    | Schemas, config_loader                       |
| 2      | Bronze ingestion         | bronze_orders.py                             |
| 3      | Silver cleanse & dedup    | silver_fact_orders.py                        |
| 4      | Gold aggregations        | gold_*.sql + batch runner                    |
| 5      | Late data                | Watermark + allowedLateness usage            |
| 6      | DLQ                      | Invalid rows → DLQ in Silver                 |
| 7      | Exactly-once             | Doc + idempotent sink                        |
| 8      | Orchestration & CI/CD    | Run scripts, one test                        |
| 9      | Observability            | Metrics list, checklist                      |

---

**Next:** Start with **Lesson 1** — we’ll add the event schema and config loader so every later lesson builds on them.
