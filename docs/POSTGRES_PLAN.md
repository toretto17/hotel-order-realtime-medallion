# Postgres for All Three Layers — Plan

This doc is the **plan** before implementation: account setup, flow, edge cases, and why Postgres.

---

## 1. Postgres vs other databases (free, scale to millions)

| Option | Free tier | Scale (millions of rows) | Best for |
|--------|-----------|---------------------------|----------|
| **Postgres** (Neon, Supabase, Aiven, self‑hosted) | Yes | Yes, with partitioning + indexes | Analytics, BI (Grafana), consistent store, ACID |
| **MySQL** (PlanetScale, etc.) | Yes | Yes | Similar to Postgres; Postgres often preferred for analytics |
| **Redis** | Yes | In‑memory; not for large fact tables | Cache, sessions; not primary store for Bronze/Silver/Gold |
| **MongoDB** | Free tier | Yes | Document store; less ideal for tabular analytics and BI tools |
| **SQLite** | Free | Single writer; not for Spark + app concurrency | Local dev only |

**Recommendation: Postgres.** Free (Neon, Supabase, Aiven Postgres), scales to millions with indexes and optional partitioning, ACID, and works well with Grafana and BI. Same provider (Aiven) can give you Kafka + Postgres for one place to manage.

---

## 2. Account and instance setup (free options)

Pick **one** Postgres provider and create one database.

| Provider | Free tier | Notes |
|----------|-----------|--------|
| **Aiven Postgres** | Free tier available | Same as your Kafka; one console for Kafka + Postgres |
| **Neon** | Free tier, serverless | Simple; get connection string in minutes |
| **Supabase** | Free tier | Postgres + optional APIs; good for apps + BI |
| **Local Postgres** | Free | For dev; not for “cloud, no laptop” |

**Steps (same idea for any):**

1. Sign up and create a Postgres service (or database).
2. Create a **database** (e.g. `order_medallion`) and a **user** with read/write.
3. Get the **connection string**:
   - JDBC (for Spark): `jdbc:postgresql://host:port/dbname?user=...&password=...`  
   - Or host, port, database, user, password for env vars.
4. Put it in `.env` (see section 6). No secrets in code.

We’ll use one schema (e.g. `medallion`) and tables: `bronze_orders`, `silver_orders`, `silver_order_items`, `gold_daily_sales`, `gold_customer_360`, `gold_restaurant_metrics`.

---

## 3. Flow: when each layer updates Postgres

Your understanding is right; we only write to Postgres when the corresponding layer **succeeds**.

| Layer | When it runs | Postgres update | Rule |
|-------|----------------|------------------|------|
| **Bronze** | Kafka → Parquet (per batch) | Insert batch into `bronze_orders` | Only after Parquet write succeeds; no insert if Bronze fails |
| **Silver** | Bronze Parquet → Silver Parquet (per batch) | Upsert into `silver_orders` and `silver_order_items` | MERGE / ON CONFLICT so no duplicates |
| **Gold** | Silver → Gold Parquet (batch) | Replace or upsert `gold_*` tables | After Gold Parquet write succeeds |

So:

- **Bronze processed** → Bronze Parquet written → **then** insert into Postgres (same batch).
- **Silver processed** → Silver Parquet written → **then** upsert into Postgres (merge on keys).
- **Gold processed** → Gold Parquet written → **then** write to Postgres (full refresh or upsert by business key).

---

## 4. Edge cases and redundancy

| Case | What we do |
|------|------------|
| **Bronze fails** (e.g. Kafka read or Parquet write fails) | Checkpoint not committed; **no** Parquet, **no** Postgres insert. Faulty batch is not persisted. |
| **Bronze succeeds, Postgres insert fails** | Option A: Fail the batch (no checkpoint commit) so we retry and stay consistent. Option B: Log and continue (Parquet only). **Plan: Option A** so we don’t have Parquet without Postgres. |
| **Silver fails** | Silver checkpoint not committed; **no** Silver Parquet update, **no** Silver Postgres update. Next run retries same batch. |
| **Silver succeeds, Postgres upsert fails** | **Plan:** Fail the Silver batch (no checkpoint commit) so we retry and keep Parquet and Postgres in sync. |
| **Duplicate Kafka message** (replay) | Bronze: use unique key `(_topic, _partition, _offset)` or `(order_id, _ingestion_ts)` and `INSERT ... ON CONFLICT DO NOTHING` (or DO UPDATE) so we don’t insert the same record twice. |
| **Same order_id in Silver twice** (e.g. status update) | Silver: upsert on `order_id` (and for items `(order_id, item_id)`) with `ON CONFLICT DO UPDATE` so latest wins (SCD Type 1). |
| **Postgres down** | Pipeline step fails; checkpoint not committed; next run retries. No half-updated state. |

So: **only successful layer writes lead to Postgres updates**, and we **fail the step** if Postgres write fails, so Parquet and Postgres stay aligned.

---

## 5. Table design and unique keys

**Bronze — `medallion.bronze_orders`**

- Columns: `value` (text/JSON), `_ingestion_ts`, `_source`, `_partition`, `_offset`, `_topic`, `_ingestion_date`.
- Unique key: `(_topic, _partition, _offset)` so the same Kafka message is never inserted twice (idempotent).
- Write: `INSERT ... ON CONFLICT (_topic, _partition, _offset) DO NOTHING` (or DO UPDATE if you want to overwrite).

**Silver — `medallion.silver_orders`**

- Columns: same as Silver Parquet (order_id, order_timestamp, restaurant_id, customer_id, order_type, total_amount, payment_method, order_status, discount_code, festival, seasonal_food, order_date, etc.).
- Unique key: `order_id` (one row per order; latest wins).
- Write: `INSERT ... ON CONFLICT (order_id) DO UPDATE SET ...` (merge/upsert).

**Silver — `medallion.silver_order_items`**

- Columns: order_id, order_timestamp, item_id, item_name, category, quantity, unit_price, subtotal, order_date.
- Unique key: `(order_id, item_id)` (one row per order line).
- Write: `INSERT ... ON CONFLICT (order_id, item_id) DO UPDATE SET ...`.

**Gold — `medallion.gold_daily_sales`**

- Columns: as in `sql/gold_daily_sales.sql` (order_date, restaurant_id, order_count, total_revenue, ...).
- Unique key: `(order_date, restaurant_id)`.
- Write: Full refresh (truncate + insert) **or** upsert on `(order_date, restaurant_id)`. Upsert is better so we can run Gold multiple times without wiping the table.

**Gold — `medallion.gold_customer_360`**

- Unique key: `customer_id`. Upsert on `customer_id`.

**Gold — `medallion.gold_restaurant_metrics`**

- Unique key: `restaurant_id`. Upsert on `restaurant_id`.

---

## 6. Config and env

**`.env`** (add, do not commit secrets):

```bash
# Postgres (for Bronze, Silver, Gold sync)
POSTGRES_JDBC_URL=jdbc:postgresql://host:port/dbname?user=xxx&password=xxx
# Or split:
POSTGRES_HOST=...
POSTGRES_PORT=5432
POSTGRES_DB=order_medallion
POSTGRES_USER=...
POSTGRES_PASSWORD=...
```

**`config/pipeline.yaml`** — extend `postgres` section:

```yaml
postgres:
  jdbc_url: "${POSTGRES_JDBC_URL}"
  schema: "medallion"
  tables:
    bronze_orders: "bronze_orders"
    silver_orders: "silver_orders"
    silver_order_items: "silver_order_items"
    gold_daily_sales: "gold_daily_sales"
    gold_customer_360: "gold_customer_360"
    gold_restaurant_metrics: "gold_restaurant_metrics"
  batch_size: 1000
```

Spark will use JDBC; we can build `POSTGRES_JDBC_URL` from host/port/db/user/password if you prefer separate env vars.

---

## 7. Implementation order

1. **Setup**
   - Create Postgres DB (Neon / Supabase / Aiven).
   - Add `POSTGRES_*` to `.env` and extend `config/pipeline.yaml`.
   - Add DDL script: `scripts/sql/postgres_schema.sql` (create schema + tables with unique constraints).

2. **Bronze → Postgres**
   - Option A: In Bronze, switch to `foreachBatch`: write batch to Parquet, then same batch to Postgres (same transaction semantics: both or neither for that batch).
   - Option B: Keep Bronze as-is; add a “sync” step after Bronze that reads the latest Bronze Parquet and inserts into Postgres with `ON CONFLICT DO NOTHING`.
   - **Plan: Option A** so faulty batches never touch Postgres and we don’t double-write on retries.

3. **Silver → Postgres**
   - Inside existing Silver `foreachBatch`: after writing to Silver Parquet, upsert the same batch to `silver_orders` and `silver_order_items` (JDBC or collect and execute MERGE/INSERT...ON CONFLICT). If Postgres write fails, let the batch fail so checkpoint is not committed.

4. **Gold → Postgres**
   - After each Gold Parquet write (daily_sales, customer_360, restaurant_metrics), write the same DataFrame to Postgres (upsert by business key). If Postgres write fails, fail the Gold job so we can retry.

5. **Pipeline script**
   - No change to order: Bronze → Silver → Gold. Each step now includes its Postgres write; if any step (including Postgres) fails, the pipeline fails and can be re-run.

6. **Optional**
   - Health check: simple script or job that checks Postgres connectivity and table row counts.
   - Grafana (or similar) connecting to the same Postgres to visualize Gold (and optionally Silver/Bronze).

---

## 8. Summary

| Question | Answer |
|----------|--------|
| Which DB? | **Postgres** (free, scales to millions, good for BI). |
| When does Bronze update Postgres? | Only when a Bronze batch is successfully written to Parquet; then we insert that batch into `bronze_orders` (idempotent on topic/partition/offset). |
| When does Silver update Postgres? | Only when a Silver batch is successfully written to Parquet; then we upsert that batch into `silver_orders` and `silver_order_items` (merge, no duplicates). |
| When does Gold update Postgres? | Only when Gold has successfully written each aggregation to Parquet; then we upsert into the corresponding `gold_*` tables. |
| If Bronze fails? | No Parquet, no Postgres; no faulty records. |
| If Silver fails? | No Silver Parquet, no Silver Postgres; retry next run. |
| If Postgres write fails? | Fail the step (no checkpoint commit for that layer) so we retry and keep Parquet and Postgres in sync. |

Next step is implementation: schema DDL, then Bronze → Postgres, then Silver → Postgres, then Gold → Postgres, and wiring in `pipeline.yaml` and `.env`.
