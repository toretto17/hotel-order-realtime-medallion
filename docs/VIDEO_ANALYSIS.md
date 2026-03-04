# Video Deep-Dive: Databricks E2E → Generic Production Design

**Video:** [Databricks End-To-End Project | Zero-To-Expert | Streaming, AI, Lakeflow…](https://www.youtube.com/watch?v=vy4G86q1rQY)  
**Channel:** Afaque Ahmad · ~4h · Restaurant Analytics on Databricks

## 1. Video Architecture (Condensed)

- **Sources:** Azure Event Hub (streaming orders), Azure SQL (customers, menus, historical orders, reviews).
- **Ingestion:** LakeFlow Connect (CDC from SQL → Bronze/Silver), Spark Declarative Pipelines (Event Hub → Bronze).
- **Layers:** Unity Catalog with schemas `landing`, `bronze`, `silver`, `gold`; Medallion.
- **Silver:** fact_orders, fact_order_items, fact_reviews; dim_customers, dim_restaurants, dim_menu_items (star schema).
- **Gold:** daily_sales_summary, customer_360, restaurant_review_metrics (materialized views).
- **Orchestration:** Databricks Workflows (Event Hub pipeline → Silver → Gold).
- **Consumption:** AI/BI dashboards in Databricks; Mosaic AI for sentiment on reviews.

## 2. Best Practices Extracted

| Practice | In video | Generic equivalent |
|----------|----------|---------------------|
| Medallion boundaries | Bronze = raw, Silver = typed/dim, Gold = aggregates | Same; enforce in paths and naming. |
| Single backfill merge | INSERT INTO streaming table from historical SQL | Batch read + merge into same table with `order_id` key. |
| DQ on Silver | expect_all_or_drop (valid order_id, item_count > 0, etc.) | Filter + DLQ; never drop silently. |
| Gold incremental | Materialized view; only changed partitions | Batch job reading Silver, overwrite by partition or merge by key. |
| Config over code | Spark config for EH namespace, connection string | YAML/env for Kafka bootstrap, topic, paths. |
| One pipeline DAG | Workflow: ingest → silver → gold | Airflow DAG or K8s: streaming always-on + scheduled Silver/Gold. |

## 3. Gaps vs Production (and Improvements)

| Gap | Improvement in this repo |
|-----|---------------------------|
| No explicit exactly-once | Checkpoint + idempotent merge in Silver/Gold; doc in ARCHITECTURE.md. |
| No DLQ | Invalid rows → Kafka topic or Delta table; alert on depth. |
| No late-data policy | Watermark 10 min; allowedLateness for aggregations; doc. |
| No checkpoint story | Dedicated section; path on S3/GCS; no manual delete in prod. |
| Vendor-specific (LakeFlow, SDP) | Replaced by Kafka + Spark Structured Streaming + standard storage. |
| No IaC | Terraform examples for Kafka, S3, IAM. |
| No cost controls | Trigger interval, maxFilesPerTrigger, cluster limits in config. |

## 4. Mapping: Video → This Repo

| Video component | This repo |
|-----------------|-----------|
| Event Hub | Kafka topic `orders` |
| LakeFlow Connect (SQL CDC) | Debezium + Kafka Connect → Kafka → Bronze (optional pipeline). |
| Spark Declarative Pipeline (Bronze) | `streaming/bronze_orders.py` (Structured Streaming). |
| Silver fact_orders / fact_order_items | `streaming/silver_fact_orders.py`, `silver_fact_order_items.py`. |
| Gold daily_sales_summary | `sql/gold_daily_sales_summary.sql` + Spark batch or streaming aggregate. |
| Gold customer_360 | `sql/gold_customer_360.sql`. |
| Gold restaurant_review_metrics | `sql/gold_restaurant_review_metrics.sql`. |
| Workflows | Airflow DAG or K8s CronJob for batch Gold. |

## 5. Alignment with this repo’s future goals

The video’s end-to-end flow (sources → ingestion → Bronze → Silver → Gold → dashboards) matches this repo’s intended direction:

| Video | This repo (future) |
|-------|---------------------|
| Order events from Event Hub / source systems | **Source ingester** producing varied orders (different order_id, food, quantity, amount). |
| Events flow into Bronze → Silver → Gold | Same: every order flows **Bronze → Silver → Gold** so the record exists in all three layers. |
| BI / dashboards consuming Gold | **Dashboard** (later): local or BI tool reading from Gold (and/or Silver) for orders, sales, metrics. |
| Restaurant / order domain | **Hotel ordering website (localhost):** place orders by food name and quantity; booked orders are sent into the pipeline and appear in Bronze, Silver, and Gold. |

So: a localhost **hotel ordering website** (order by food + quantity) → Kafka → Bronze → Silver → Gold → (later) **dashboard** is the target end-to-end flow, consistent with the video’s architecture.

---

## 6. Production approach & senior-level bar (do we follow the video exactly?)

**No.** We use the video as a **reference for patterns and concepts**, not a prescription to copy tooling or implementation.

| Question | Answer |
|----------|--------|
| Same *design* as video? | Yes: Medallion (Bronze → Silver → Gold), Silver fact/dim, Gold aggregates, DQ, orchestration. |
| Same *tooling*? | No: we use Kafka + Spark + Parquet (cloud-agnostic); video uses Databricks, LakeFlow, Unity Catalog. |
| Production-level? | Yes: config-driven, checkpoint, watermark, dedup, schema evolution, and we add DLQ, exactly-once doc, observability. |
| Senior / big-product bar? | We follow **principles** (correct semantics, operability, clear boundaries, Gold for business aggregates, orchestration, observability); implementation is stack-agnostic. |

**What we do:** Adopt the video’s **architecture and best practices**; implement with **our stack** and **explicit production concerns** (DLQ, exactly-once, runbooks, metrics). That is the correct approach for a production-level, interview-ready project. See **ARCHITECTURE.md** for full design; **LEARNING_PATH.md** for the lesson order (Gold → DLQ → exactly-once → orchestration → observability).

---

## 7. Gold layer: multiple SQL files vs one script (production pattern)

**Video:** Separate materialized views / SQL per aggregate (daily_sales_summary, customer_360, restaurant_review_metrics).

**This repo (production-level):**

- **Multiple SQL files (or equivalent logic)** — One file or one aggregation per business output (e.g. `sql/gold_daily_sales.sql`, `sql/gold_customer_360.sql`, `sql/gold_restaurant_metrics.sql`). This gives **separation of concerns**: each Gold table has clear, testable logic; adding a new aggregate = add one file + one step in the runner.
- **One Gold batch job / entry point** — A single script (e.g. `streaming/gold_batch.py` or `scripts/run_gold.sh`) that **runs all Gold steps in one go**: read Silver, run each aggregation, write to the corresponding Gold path. So ops runs **one** job (e.g. `make gold` or one scheduled run), not three separate crons.
- **Same as video conceptually** — Multiple aggregates, same as the video’s Gold layer. **Different execution model** — One batch job that runs all of them (same schedule, one checkpoint/log stream, simpler ops). Optionally later: split into separate DAG tasks if different Gold tables need different schedules.

So: **multiple SQL (or DataFrame) definitions + one Gold “DAG”/script** is the correct production pattern. We do **not** need one giant SQL file; we **do** need one entry point that runs all Gold steps. See **LEARNING_PATH.md** Lesson 4 for deliverables (`sql/gold_*.sql` + batch runner).

**Gold metrics implemented (real-world / daily usage):**

| Gold table | Metrics (production-style) |
|------------|-----------------------------|
| **daily_sales** | order_date, restaurant_id, order_count, total_revenue, avg_order_value, unique_customers; payment breakdown (card/cash/other); order_type (delivery/pickup/other); orders_with_discount, orders_during_festival, orders_with_seasonal_item; completed_count, other_status_count. Partitioned by order_date. |
| **customer_360** | customer_id, order_count, total_spend, avg_order_value, first_order_date, last_order_date, preferred_payment_method (mode), favorite_restaurant_id (mode), orders_with_discount, orders_during_festival. |
| **restaurant_metrics** | restaurant_id, order_count, total_revenue, avg_order_value, unique_customers, total_items_sold, unique_items_ordered, top_selling_category. |
