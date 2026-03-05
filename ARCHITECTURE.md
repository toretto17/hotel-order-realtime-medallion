# Production-Grade Real-Time Order Processing — Medallion Architecture

**Cloud-agnostic design · Exactly-once · Fault-tolerant · Interview-ready**

---

## 1. High-Level Architecture (Text Diagram)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                                 │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐                    │
│  │  Order Events     │    │  PostgreSQL      │    │  (Optional)      │                    │
│  │  (POS / API)      │    │  (CDC / Batch)   │    │  REST / Files     │                    │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘                    │
│           │                        │                        │                              │
└───────────┼────────────────────────┼────────────────────────┼──────────────────────────────┘
            │                        │                        │
            ▼                        ▼                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                                                    │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐         ┌─────────────────────┐                                   │
│  │  Kafka (Orders)     │         │  Debezium /         │         Kafka Connect              │
│  │  Topic: orders      │         │  Kafka Connect     │         (PostgreSQL CDC)           │
│  └─────────┬───────────┘         └─────────┬───────────┘                                   │
└────────────┼────────────────────────────────┼───────────────────────────────────────────────┘
             │                                │
             └────────────────┬───────────────┘
                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                    STREAMING ENGINE (Spark Structured Streaming)                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  Checkpoint Dir (S3/GCS/ABFS)  │  Watermark  │  Trigger: availableNow / 1 min      │   │
│  └─────────────────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                         MEDALLION LAYERS (Object Storage)                                 │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│  BRONZE (Raw)              SILVER (Cleaned)              GOLD (Aggregated)                  │
│  ┌─────────────────┐       ┌─────────────────┐          ┌─────────────────┐               │
│  │ orders_raw      │ ───► │ fact_orders      │          │ daily_sales     │               │
│  │ order_items_raw │      │ fact_order_items │ ───────► │ customer_360    │               │
│  │ (Parquet/Delta) │      │ fact_reviews     │          │ restaurant_metrics│              │
│  │ + _metadata     │      │ dim_* (from CDC) │          │ (Partitioned)    │               │
│  └─────────────────┘       └─────────────────┘          └────────┬────────┘               │
└─────────────────────────────────────────────────────────────────┼─────────────────────────┘
                                                                  │
             ┌────────────────────────────────────────────────────┼─────────────────────────┐
             │                    SERVING                         ▼                         │
             │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────────┐ │
             │  │ PostgreSQL   │  │ REST API    │  │ BI / Dashboards (Metabase, Superset)   │ │
             │  │ (Materialized│  │ (Optional)  │  │ or Query Engine (Trino/Presto)         │ │
             │  │  views/sync) │  │             │  │                                        │ │
             │  └──────────────┘  └──────────────┘  └──────────────────────────────────────┘ │
             └───────────────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY: Prometheus + Grafana │ Dead Letter Queue (Kafka topic) │ Alerting (PagerDuty)│
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

**AWS equivalents (when needed):**
- Kafka → **Amazon MSK** (managed Kafka)
- Object storage → **S3**
- Spark → **EMR Serverless** or **EKS + Spark on K8s**
- Orchestration → **AWS Step Functions** or **Airflow (MWAA)**

---

## 2. Video Analysis (Databricks E2E Project — Afaque Ahmad)

**Source:** [Databricks End-To-End Project | Zero-To-Expert | Streaming, AI, Lakeflow…](https://www.youtube.com/watch?v=vy4G86q1rQY)

### What the Video Covers (Best Practices to Extract)

| Area | Video approach | Takeaway for generic design |
|------|----------------|-----------------------------|
| **Medallion** | Bronze (raw) → Silver (star schema) → Gold (aggregates) | Keep layer boundaries; Bronze = immutable raw, Silver = typed + deduped, Gold = business aggregates. |
| **Streaming source** | Azure Event Hub (Kafka API) | Use Kafka (or MSK) as canonical streaming bus; same semantics. |
| **Batch source** | Azure SQL + LakeFlow Connect CDC | Use **Debezium + Kafka Connect** for PostgreSQL CDC → Kafka → Bronze/Silver. |
| **Streaming ingestion** | Spark Declarative Pipelines (Databricks) | Replace with **Spark Structured Streaming** + explicit checkpoint + trigger. |
| **Silver model** | fact_orders, fact_order_items, fact_reviews + dim_* | Same star schema; implement in Spark SQL/DataFrame. |
| **Gold** | Daily sales summary, customer_360, restaurant reviews | Same aggregates; use batch reads from Silver + partition by date. |
| **Data quality** | `expect_all_or_drop` style checks | Implement as **filter + DLQ**: invalid rows → DLQ topic or table. |
| **Orchestration** | Databricks Workflows (pipelines in sequence) | Use **Airflow/Step Functions** to run streaming job + periodic Silver/Gold batch. |
| **One-time backfill** | INSERT INTO streaming table from historical | Support backfill via **batch read + merge** into same path with idempotency keys. |

### Missing / Weak for Production (and How We Address Them)

| Gap | Risk | Our design |
|-----|------|------------|
| No explicit **exactly-once** strategy | Duplicates or loss on failure | Idempotent sink (merge by key), checkpoint, and transactional WAL. |
| No **late-arriving data** policy | Incorrect aggregates | Event-time watermark + allowed lateness; separate “late” topic or batch correction. |
| No **DLQ** for bad records | Bad data blocks pipeline or is dropped silently | All invalid rows → DLQ (Kafka topic or table); alert on DLQ depth. |
| No **offset/checkpoint** story | Restart from wrong place | Checkpoint on object storage; never delete checkpoint dir; document recovery. |
| No **partitioning** strategy | Hot partitions, slow reads | Bronze by `ingestion_date`; Silver by `order_date`; Gold by `order_date` or `snapshot_date`. |
| No **schema evolution** | Breaking changes | Bronze: schema-on-read (JSON/AVRO); Silver: explicit schema + evolution (add column). |
| No **cost/compute** control | Runaway Spark jobs | Trigger interval, maxFilesPerTrigger, cluster autoscaling limits. |
| No **IaC / CI/CD** | Manual, inconsistent envs | Terraform/Pulumi for infra; CI for tests and deploy. |

---

## 3. Technology Stack Justification

| Component | Choice | Why (cloud-agnostic) |
|-----------|--------|----------------------|
| **Streaming engine** | **Apache Spark Structured Streaming** | Portable (on-prem, EMR, EKS, Databricks). Exactly-once with Kafka + checkpoint. No vendor lock-in. |
| **Message bus** | **Apache Kafka** | De facto standard; AWS = MSK, Azure = Event Hub (Kafka API), GCP = Confluent or similar. |
| **Storage (Bronze/Silver/Gold)** | **Delta Lake** or **Parquet on S3/GCS/ABFS** | Delta: ACID, time travel, merge. Parquet: simple, cheap. Both work with Spark. |
| **Source DB** | **PostgreSQL** | Given; CDC via Debezium. |
| **Sink (serving)** | **PostgreSQL** (optional) | For low-latency APIs; sync via batch job or Kafka Connect. |
| **Orchestration** | **Apache Airflow** or **Kubernetes CronJobs** | DAG for batch Silver/Gold + backfills; streaming runs 24/7. |
| **Monitoring** | **Prometheus + Grafana** | Spark metrics, Kafka lag, custom pipeline metrics. |
| **Config** | **YAML/Env** | Pipeline config (topics, paths, watermark) in code repo; 12-factor. |

**Alternatives considered:**
- **Flink:** Strong event-time and state; steeper ops. Use if you need complex CEP or very low latency.
- **Kafka Streams:** Good for simple transforms; less suited to full medallion + large batch merges.

---

## 4. Medallion Layer Design

### 4.1 Bronze — Ingestion

- **Role:** Immutable raw copy of every event.
- **Format:** Parquet or Delta; one partition key = `ingestion_date` (and optionally `hour`).
- **Schema:** 
  - Preserve raw payload (e.g. `value` as string or parsed JSON).
  - Add: `_ingestion_ts` (processing time), `_source` (e.g. `kafka`), `_partition`, `_offset`.
- **Schema evolution:** Store as single JSON/string column + schema registry for parsing in Silver; new fields added in Silver only.
- **Idempotency:** Same `(topic, partition, offset)` written once; checkpoint guarantees no double read from Kafka.

### 4.2 Silver — Cleansing & Model

- **Role:** Typed, deduplicated, business-ready star schema.
- **Deduplication:** By business key (e.g. `order_id` for orders) using `window` + `row_number()` or `dropDuplicates` with watermark.
- **Watermarking:** `order_timestamp` or `event_timestamp`; e.g. `withWatermark("order_timestamp", "10 minutes")`.
- **Output:** fact_orders, fact_order_items, fact_reviews; dim_customer, dim_restaurant, dim_menu_item (from CDC or batch).
- **Data quality:** Expectations (non-null, ranges) → pass to next step; fail → DLQ.

### 4.3 Gold — Aggregations & Serving

- **Role:** Pre-aggregated tables for dashboards and APIs.
- **Examples:** daily_sales_summary (by order_date), customer_360 (one row per customer), restaurant_review_metrics (by restaurant).
- **Refresh:** Batch job reading from Silver (triggered daily or every N hours); or streaming aggregate if latency requirement is strict.
- **Partitioning:** By `order_date` or `snapshot_date` for efficient pruning.
- **Execution (production):** One Gold table = one SQL file (or one aggregation step) for separation of concerns; **one** batch script (e.g. `gold_batch.py`) runs all Gold steps and writes to their paths. Single entry point for ops (`make gold`); see **docs/VIDEO_ANALYSIS.md** §7.

### 4.4 Schema evolution & merge schema

- **Bronze:** Raw JSON in `value` — no schema; any new field (e.g. `discount_code`, `festival`, `seasonal_food`) is already stored. Nothing to change.
- **Silver:** We parse with a fixed Spark schema (`ORDER_JSON_SCHEMA`). To support new columns:
  - Add them as **nullable** fields in the schema so old events (without the field) still parse; new events populate them.
  - Select the new columns into fact_orders (and fact_order_items if they live on items). Do not drop new columns; add them explicitly when the source starts sending them.
- **Merge schema (read path):** When **reading** Silver Parquet (e.g. for Gold or Postgres sync), use `spark.read.option("mergeSchema", "true").parquet(silver_path)` so that older files (fewer columns) and newer files (more columns) merge; missing columns in old data become null.
- **Do not remove columns** from the schema for backward compatibility; only add optional (nullable) columns.

### 4.5 Postgres / serving tables (target model)

For a full serving or analytics layer in Postgres, the target tables align with Silver + dimensions:

| Table | Purpose | Source |
|-------|---------|--------|
| **fact_orders** | One row per order (order_id, timestamps, amounts, payment, status, optional discount/festival/seasonal) | Silver fact_orders |
| **fact_order_items** | One row per line item (order_id, item_id, name, category, qty, price, subtotal) | Silver fact_order_items |
| **dim_product** / **dim_food** | Product/food master (item_id, name, category, active, etc.) | Reference data or from items |
| **dim_restaurant** | Restaurant master (restaurant_id, name, etc.) | Reference data or CDC |
| **dim_customer** | Customer master (customer_id, etc.) | Reference data or CDC |
| **payments** / **dim_payment** | Payment method or transaction details if needed | From order payload or separate topic |

Currently the pipeline writes **Parquet only** (Bronze, Silver). Postgres sync (e.g. batch job or Kafka Connect) is optional and configured via `config/pipeline.yaml` under `postgres`; table DDL and sync job are to be added when the serving layer is implemented.

---

## 5. Data Modeling

### 5.1 Order Event Schema (Kafka)

```json
{
  "order_id": "uuid",
  "order_timestamp": "2025-03-04T12:00:00Z",
  "restaurant_id": "string",
  "customer_id": "string",
  "order_type": "dine_in|takeaway|delivery",
  "items": [
    { "item_id": "string", "name": "string", "category": "string", "quantity": 1, "unit_price": 10.5, "subtotal": 10.5 }
  ],
  "total_amount": 25.50,
  "payment_method": "cash|card|wallet",
  "order_status": "pending|completed|ready"
}
```

### 5.2 Event-Driven + Idempotency

- **Idempotency key:** `order_id` (and for items: `(order_id, item_id)`).
- **Silver:** Merge/upsert by `order_id` so same event replayed (e.g. after failure) overwrites; no duplicate rows.
- **Bronze:** Append-only; idempotency enforced at Silver when merging.

---

## 6. Exactly-Once Processing Strategy

1. **Source:** Kafka with committed offsets only after successful sink write (Spark does this with checkpoint).
2. **Processing:** Single Spark streaming query; deterministic transformations.
3. **Sink:** 
   - **Delta/Parquet:** Use **transactional write** (Delta) or **partition + overwrite by batch id** so re-run writes same output.
   - **PostgreSQL:** Use **INSERT ON CONFLICT (id) DO UPDATE** or **merge by key** so duplicate writes are idempotent.
4. **Checkpoint:** Stored on object storage; never delete; one checkpoint dir per query.

---

## 7. Late-Arriving Data

- **Watermark:** e.g. `withWatermark("order_timestamp", "10 minutes")`; events later than 10 min are dropped in that window.
- **Allowed lateness:** For aggregations, use `allowedLateness` (e.g. 1 hour) and update state for late keys.
- **Out-of-order handling:** In Silver dedup, order by `event_timestamp` and keep latest per key; in Gold, run periodic batch that re-aggregates last N days if needed.

---

## 8. Checkpointing & Offset Management

- **Location:** e.g. `s3://bucket/checkpoints/orders_bronze/` (per pipeline stage).
- **Contents:** Spark manages commits and offsets; do not edit manually.
- **Recovery:** Restart job with same checkpoint; Spark resumes from last committed offset.
- **Reset:** Only for dev; delete checkpoint (lose exactly-once from that point).

---

## 9. Partitioning Strategy

| Layer  | Partition keys       | Rationale |
|--------|-----------------------|-----------|
| Bronze | `ingestion_date`, hour| Even spread; retention by date. |
| Silver | `order_date`          | Align with queries and Gold. |
| Gold   | `order_date` or `snapshot_date` | Report by day; partition pruning. |

---

## 10. Error Handling & DLQ

- **Invalid records:** Filter in Silver; write failed rows to DLQ (Kafka topic `orders_dlq` or table `bronze.dlq_orders`).
- **Schema failures:** Log to DLQ with raw payload + error message; alert on DLQ depth.
- **Retries:** Spark task retries; after N failures, use DLQ and continue.

---

## 11. CI/CD and Deployment

- **Build:** Scala/Java or PySpark; unit tests for transformations; integration test with embedded Kafka.
- **Deploy:** Spark job submitted to cluster (EMR, K8s, YARN); config from env or S3.
- **Pipeline:** CI runs tests; CD deploys job definition and starts streaming job (or updates DAG in Airflow).

---

## 12. Infrastructure as Code

- **Recommendation:** **Terraform** (or Pulumi) for: Kafka (or MSK), S3 buckets, IAM, EMR/K8s, Airflow.
- **Separate state** per env (dev/staging/prod); use remote backend (S3 + DynamoDB or equivalent).

---

## 13. Production Readiness Checklist

- [ ] Checkpoint on durable storage; backup/retention policy.
- [ ] Alerts on consumer lag (Kafka), job failure, DLQ depth.
- [ ] Idempotent Silver/Gold writes (merge keys defined).
- [ ] Watermark and late-data policy documented and tuned.
- [ ] Resource limits (executor memory, max trigger size) to avoid OOM.
- [ ] Schema evolution process (add column in Silver; backfill if needed).
- [ ] Runbooks for: restart, reset offset, backfill, schema change.
- [ ] Cost controls: cluster autoscaling bounds, retention on Bronze.

---

## 14. Future project goals (roadmap)

- **Source ingester / website:** Implemented: producer script and hotel website produce varied orders; pipeline runs Bronze → Silver → Gold.
- **Postgres (serving layer):** Optional: sink Gold (and optionally Silver) to Postgres for queryable tables (dashboards, APIs). Parquet remains for processing. See **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §1.
- **Free website hosting + domain:** Render free tier (subdomain or custom domain). **docs/FREE_HOSTING.md**; **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §2.
- **Orchestrated pipeline:** Trigger Bronze → Silver → Gold automatically (micro-batch + Airflow/Prefect/cron) for cost-effective, hands-off runs. **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §3.
- **Streaming vs latency:** Document and support both long-running streaming (low latency) and triggered micro-batch (cost-effective); Zomato/IPO-style latency expectations. **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §4.
- **Dashboard (later):** BI or UI reading from Gold (or Postgres).

This aligns with the reference video (source → ingestion → Medallion → consumption). See **README.md**, **docs/NEXT_STEPS_AND_FUTURE_GOALS.md**, and **docs/VIDEO_ANALYSIS.md** §5.

---

*Next: See `docs/VIDEO_ANALYSIS.md` for detailed video vs design mapping, and `README.md` for runbook and repo layout.*
