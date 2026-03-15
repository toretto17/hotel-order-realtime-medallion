# Postgres for Medallion — Step-by-step (same as Kafka)

Follow this **line by line**. One Postgres database for all three layers (Bronze, Silver, Gold). Same idea as Kafka: create the service once, get the URL and password, put them in `.env`, run the schema once, then run the pipeline.

---

## Part 1: Open Aiven and select your project

### Step 1.1 — Log in and pick the same project as Kafka

1. Open your browser and go to: **https://console.aiven.io**
2. Log in (same account you use for Kafka).
3. In the top bar or sidebar, open the **Project** dropdown.
4. Select the **same project** where your Kafka service lives (e.g. `realtime-order-medallion`).  
   You do **not** create a new project; Postgres and Kafka will be in the same project.

---

## Part 2: Create the Postgres service

### Step 2.1 — Start creating a service

1. In the left sidebar, click **Services**.
2. Click **Create service** (or **+ Create service**).

### Step 2.2 — Choose PostgreSQL and plan

1. You’ll see a list of products (Apache Kafka®, PostgreSQL®, etc.).
2. Select **PostgreSQL®** (or **Aiven for PostgreSQL®**).
3. Find **Service tier** or **Plan**.
4. Select **Free** if available, or the **cheapest** tier (e.g. Hobbyist / 1GB).
5. **Cloud / Region:** use the **same region** as your Kafka (e.g. **Asia Pacific** for India).  
   Same region = lower latency and simpler to remember.

### Step 2.3 — Service name and create

1. Find the **Service name** field. Aiven may pre-fill something like `pg-abc123`.
2. You can keep it or change it to something clear, e.g. **`order-medallion-pg`** or **`medallion-postgres`**.  
   Rules: **letters, numbers, hyphens only**; no spaces.
3. Scroll down, check the summary (PostgreSQL, plan, region, name).
4. Click **Create service** (or **Create**).

### Step 2.4 — Wait until the service is running

1. You’ll be on the new Postgres service page. Status will be **“Creating”** or **“Powering on”**.
2. Wait until the status is **“Running”** (often **1–3 minutes**). You can refresh the page.
3. When it says **Running**, do **Step 2.5** so your laptop can connect.

### Step 2.5 — Enable public access (required for connections from your machine)

By default, Aiven Postgres may **not** accept connections from the public internet. If you skip this, you’ll get **“Operation timed out”** when running `make postgres-schema`.

1. On the **Postgres service** page, in the left sidebar click **Service settings**.
2. In **Cloud and network**, click **Actions** → **More network configurations**.
3. Click **Add configuration options** and in the search box type **`public_access`**.
4. Find the **public_access** option for PostgreSQL and **enable** it (turn it on).
5. Click **Save configuration**.
6. Wait a short while if needed. In **Overview** → **Connection information** you should see **Access Route** with **Public** and **Dynamic**. Use the **Public** host/port for your JDBC URL (see Part 3).

Then go to Part 3.

---

## Part 3: Get connection details (host, port, database, user, password)

### Step 3.1 — Open connection information

1. Stay on the **Postgres service** page.
2. Open the **Overview** tab (or the first tab with connection info).
3. Find the **Connection information** (or **Connection details**) section.  
   You may see a box with a **Connection string** or separate fields.

### Step 3.2 — Note host, port, database, user

1. **Host:** something like `pg-order-medallion-xxx.aivencloud.com` or `order-medallion-pg-xxx.aivencloud.com`. Copy it.
2. **Port:** often **25432** or **5432** (Aiven often uses a non-default port). Note it.
3. **Database:** usually **`defaultdb`**. Note it.
4. **User:** usually **`avnadmin`**. Note it.

### Step 3.3 — Get or set the password

1. In the same **Connection information** area, find **Password**.
2. If you see **Show** or an eye icon, click it and **copy the password**.  
   Store it somewhere safe (e.g. password manager); you’ll put it in `.env` in Part 4.
3. If there is **no password** or **Reset password**:
   - Click **Reset password** (or **Users** in the left menu of the service → select `avnadmin` → reset password).
   - Set a new password and **copy it**. You won’t see it again.

**Important:** This password is **only** for this Postgres service. It is **not** the same as your Aiven account password or your Kafka password.

---

## Part 4: Build the JDBC URL and add it to `.env`

### Step 4.1 — JDBC URL format

Use this format (replace the placeholders with your values):

```text
jdbc:postgresql://HOST:PORT/DATABASE?user=USER&password=PASSWORD&ssl=true&sslmode=require
```

Example (fake values):

```text
jdbc:postgresql://pg-order-medallion-abc123.aivencloud.com:25432/defaultdb?user=avnadmin&password=MySecretPass123&ssl=true&sslmode=require
```

Rules:

- **No spaces** in the URL.
- Keep **`ssl=true`** and **`sslmode=require`** for Aiven.
- If the password has special characters (e.g. `@`, `#`, `&`), **URL-encode** them (e.g. `@` → `%40`, `#` → `%23`, `&` → `%26`).

### Step 4.2 — Add to `.env` in the project root

1. Open your project in the editor (e.g. `realtime-order-medallion`).
2. Open the **`.env`** file in the **project root** (same folder as `Makefile`, not inside `web/`).
3. Add **one line** (replace with your real URL):

```bash
POSTGRES_JDBC_URL=jdbc:postgresql://YOUR_HOST:YOUR_PORT/YOUR_DB?user=avnadmin&password=YOUR_PASSWORD&ssl=true&sslmode=require
```

4. Save the file.  
   **Do not commit `.env`** (it’s in `.gitignore`). Never put this URL in Git.

---

## Part 5: Create the schema and tables (run once)

### Step 5.1 — Install Python dependency (if not already)

From the **project root**:

```bash
pip install -r requirements.txt
```

(This installs `psycopg2-binary`, used by the schema script.)

### Step 5.2 — Run the schema script

From the **project root**:

```bash
make postgres-schema
```

This script:

- Reads `POSTGRES_JDBC_URL` from `.env`
- Connects to your Postgres
- Creates the **`medallion`** schema
- Creates all six tables: **`bronze_orders`**, **`silver_orders`**, **`silver_order_items`**, **`gold_daily_sales`**, **`gold_customer_360`**, **`gold_restaurant_metrics`**

You should see: **Schema created successfully.**

If you see **connection refused** or **password authentication failed**, check:

- Host, port, database, user, password in the URL
- That the Postgres service status is **Running** in Aiven
- That the password has no typos and special characters are URL-encoded

### Step 5.3 — (Optional) Verify tables

If you have `psql` or a Postgres client, connect and run:

```sql
\dt medallion.*
```

You should see the six tables. Or in Aiven, open the **Databases** or **Query** tab (if available) and list tables in the `medallion` schema.

---

## Part 6: Flow — how the three layers update Postgres

### One-time setup (you only do this once)

| Step | Command / action |
|------|-------------------|
| 1 | Create Postgres service in Aiven (Part 2). |
| 2 | Get host, port, database, user, password (Part 3). |
| 3 | Add `POSTGRES_JDBC_URL=...` to `.env` (Part 4). |
| 4 | Run `make postgres-schema` (Part 5). |

### Every time you run the pipeline

| Step | Command | What updates in Postgres |
|------|---------|---------------------------|
| 1 | `make pipeline` | Bronze reads Kafka → writes Parquet → **inserts into `medallion.bronze_orders`** (if `POSTGRES_JDBC_URL` is set). |
| (Silver runs next) | (inside same `make pipeline`) | Silver reads Bronze Parquet → writes Silver Parquet. **Silver → Postgres** is optional (see below). |
| (Gold runs next) | (inside same `make pipeline`) | Gold reads Silver Parquet → writes Gold Parquet. **Gold → Postgres** is optional (see below). |

So:

- **Bronze → Postgres** is already wired: as soon as `POSTGRES_JDBC_URL` is in `.env` and you’ve run `make postgres-schema`, each run of `make pipeline` will **insert new Bronze rows** into `medallion.bronze_orders` (idempotent: same Kafka message won’t duplicate).
- **Silver** and **Gold** tables exist in the schema; wiring them to sync from the pipeline (so `silver_orders`, `silver_order_items`, and the three gold tables are updated when you run the pipeline) is the next step. Until then, you can run SQL or BI tools against Bronze in Postgres; Silver and Gold in Postgres can be backfilled or wired later.

### Summary of commands

| What | Command |
|------|---------|
| Create schema + tables (once) | `make postgres-schema` |
| Run full pipeline (Bronze → Silver → Gold) | `make pipeline` |
| Run only Bronze (e.g. to test Postgres insert) | `make bronze` |

After **`make pipeline`** (with Postgres configured), query **`medallion.bronze_orders`** in any Postgres client or Grafana to see raw ingested orders.

---

## Troubleshooting

| Problem | What to check |
|--------|----------------|
| **Operation timed out** (connection to server ... failed) | **Enable public access:** Service settings → Cloud and network → Actions → More network configurations → Add configuration options → search `public_access` → enable → Save. Then use the **Public** host in your JDBC URL (see Step 2.5). |
| **Schema script: connection refused** | Postgres service is **Running** in Aiven; host and port in `POSTGRES_JDBC_URL` are correct; public access is enabled. |
| **Schema script: password authentication failed** | User and password in the URL; password URL-encoded if it has `@`, `#`, `&`. |
| **Schema script: relation "medallion.bronze_orders" already exists** | Normal. Tables are created with `IF NOT EXISTS`; safe to run `make postgres-schema` again. |
| **Bronze runs but no rows in Postgres** | `.env` has `POSTGRES_JDBC_URL`; you restarted or re-ran the pipeline after adding it; no errors in the Bronze log. |
| **Bronze Postgres is empty but Silver has data** | Bronze only inserts when **new** Kafka messages are consumed. Existing data in Bronze Parquet (from before Postgres was set up, or from runs with "no new messages") was never synced. **Fix:** run `make postgres-backfill` to copy existing Bronze Parquet → Postgres. Use `make postgres-backfill ALL=1` to backfill Bronze + Silver + Gold. |
| **Password with special characters** | In the URL, replace `@` → `%40`, `#` → `%23`, `&` → `%26`, `%` → `%25`. |

---

## Column order in Aiven PG Studio

Tables are created with **business/key columns first** (e.g. `order_id`, then other fields, then `_ingestion_ts`, `_partition`, `_offset`). You can confirm with:

```sql
SELECT column_name, ordinal_position
FROM information_schema.columns
WHERE table_schema = 'medallion' AND table_name = 'silver_orders'
ORDER BY ordinal_position;
```

`order_id` will be `ordinal_position = 1`. **Aiven PG Studio** (and some other SQL UIs) show result columns in **alphabetical order** in the results grid. That is a display choice of the UI, not the database. Aiven’s docs do not describe a setting to switch to definition order.

To always see columns in the order you want, run a query with an **explicit column list**:

**Silver orders (order_id first, audit columns last):**
```sql
SELECT order_id, order_timestamp, restaurant_id, customer_id, order_type, total_amount,
       payment_method, order_status, discount_code, festival, seasonal_food, order_date,
       _ingestion_ts, _partition, _offset
FROM medallion.silver_orders;
```

**Silver order items (order_id, item_id first):**
```sql
SELECT order_id, item_id, order_timestamp, item_name, category, quantity, unit_price, subtotal, order_date
FROM medallion.silver_order_items;
```

Save these in PG Studio as a snippet or default query if you use them often.

---

## Full reset (start everything from scratch)

If you want to wipe all data and start fresh (e.g. Bronze Parquet is gone, or you want to reload from Kafka only):

1. **Clean all Parquet and checkpoints** (so next pipeline run has no old data):
   ```bash
   make clean-data
   ```
2. **Truncate Postgres** (so Postgres matches empty layers):
   ```bash
   make postgres-truncate YES=1
   ```
3. **Re-create schema** (optional; only if you dropped tables): `make postgres-schema`
4. **Produce new orders** (so Kafka has messages again): `make produce-orders N=10` or use the website.
5. **Run pipeline**: `make pipeline`

After this, Bronze, Silver, and Gold (Parquet and Postgres) are in sync and only contain data from the new run. If you **don’t** truncate Postgres, Silver/Gold Postgres can still have old rows while Parquet is empty — so for a strict “everything from scratch” state, always run both `make clean-data` and `make postgres-truncate YES=1`.

---

## Quick reference

1. **Aiven Console:** https://console.aiven.io → same project as Kafka.
2. **Create:** Services → Create service → PostgreSQL® → Free (or cheapest) → same region → Create.
3. **Get:** Overview → Connection information → Host, Port, Database, User, Password.
4. **`.env`:** `POSTGRES_JDBC_URL=jdbc:postgresql://HOST:PORT/DB?user=USER&password=PASS&ssl=true&sslmode=require`
5. **Schema (once):** `make postgres-schema`
6. **Flow:** `make pipeline` → Bronze (and later Silver/Gold) update Parquet and Postgres.

Same pattern as Kafka: one service, one URL in `.env`, one schema command, then the pipeline keeps Postgres in sync.
