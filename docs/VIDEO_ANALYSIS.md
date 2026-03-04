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
