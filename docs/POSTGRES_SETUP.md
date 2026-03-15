# Postgres for Medallion — Setup (same style as Kafka)

Use **one** Postgres database for Bronze, Silver, and Gold tables. Same idea as Kafka: create the service once, get the connection details, put them in `.env`, run the schema once.

**Recommended: Aiven Postgres** (same console as your Kafka). Alternative: **Neon** (free tier, no card required).

---

## Option A: Aiven Postgres (same account as Kafka)

### 1. Open Aiven Console and project

1. Go to [https://console.aiven.io](https://console.aiven.io) and log in.
2. Select the **same project** where your Kafka service lives (e.g. `realtime-order-medallion`).

### 2. Create Postgres service

1. Click **Services** in the left sidebar.
2. Click **Create service**.
3. **Service type:** choose **PostgreSQL®**.
4. **Plan:** select **Free** (if available) or the cheapest tier.
5. **Cloud / Region:** same as Kafka (e.g. **Asia Pacific** for India).
6. **Service name:** e.g. `order-medallion-pg` or `medallion-postgres`.
7. Click **Create service**. Wait until status is **Running**.

### 3. Get connection details

1. Click your new Postgres service.
2. Open the **Overview** or **Connection information** tab.
3. Note:
   - **Host** (e.g. `pg-medallion-xxx.aivencloud.com`)
   - **Port** (usually `25432` or `5432`; Aiven often uses a non-default port)
   - **Database name** (default is often `defaultdb`)
   - **User** (e.g. `avnadmin`)
   - **Password** (click **Show** or use the one you set; if you didn’t set one, reset it in the service settings)

### 4. Build JDBC URL

Format:

```text
jdbc:postgresql://HOST:PORT/DATABASE?user=USER&password=PASSWORD&ssl=true&sslmode=require
```

Example (replace with your values):

```text
jdbc:postgresql://pg-medallion-xxx.aivencloud.com:25432/defaultdb?user=avnadmin&password=YOUR_PASSWORD&ssl=true&sslmode=require
```

**Important:** Aiven Postgres uses SSL. Keep `ssl=true` and `sslmode=require`. If the URL has special characters in the password, URL-encode them (e.g. `@` → `%40`).

### 5. Add to `.env`

In your project root, open `.env` and add (one line, no spaces around `=`):

```bash
POSTGRES_JDBC_URL=jdbc:postgresql://YOUR_HOST:YOUR_PORT/YOUR_DB?user=YOUR_USER&password=YOUR_PASSWORD&ssl=true&sslmode=require
```

Use the same credentials as in the Aiven console. Do not commit `.env`.

### 6. Run the schema once

Create the `medallion` schema and all tables (bronze_orders, silver_orders, silver_order_items, gold_*).

**Option 1 — Aiven Console (SQL tab):**

1. In the Postgres service page, open the **SQL** or **Query** tab (if available).
2. Copy the contents of `scripts/sql/postgres_schema.sql` from this repo.
3. Paste and run the script.

**Option 2 — Command line (psql):**

If you have `psql` and the connection string:

```bash
psql "postgresql://avnadmin:PASSWORD@HOST:PORT/defaultdb?sslmode=require" -f scripts/sql/postgres_schema.sql
```

**Option 3 — From repo root (recommended):**

```bash
make postgres-schema
```

This runs `scripts/run_postgres_schema.py`, which reads `POSTGRES_JDBC_URL` from `.env`. Ensure `psycopg2-binary` is installed (`pip install -r requirements.txt`).

After this, the pipeline (when Postgres sync is implemented) will write to these tables. You can query them with any Postgres client or Grafana.

---

## Option B: Neon (free tier, no card)

1. Go to [https://neon.tech](https://neon.tech) and sign up (GitHub or email).
2. Create a **project** and a **database** (e.g. `order_medallion`).
3. In the dashboard, open **Connection details** and copy the **connection string**.
4. Convert to JDBC:
   - Neon gives something like: `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`
   - JDBC form: `jdbc:postgresql://ep-xxx.region.aws.neon.tech:5432/neondb?user=USER&password=PASS&ssl=true&sslmode=require`
   - Use the host (without `postgresql://`), port `5432`, database name, user, and password from the Neon string.
5. Put `POSTGRES_JDBC_URL=...` in `.env`.
6. Run `scripts/sql/postgres_schema.sql` in Neon’s SQL Editor (or via psql / run script).

---

## Verify

- **From command line:**  
  `psql "YOUR_CONNECTION_STRING" -c "\dt medallion.*"`  
  You should see: `bronze_orders`, `silver_orders`, `silver_order_items`, `gold_daily_sales`, `gold_customer_360`, `gold_restaurant_metrics`.

- **From the pipeline:**  
  After Bronze/Silver/Gold sync is implemented, run `make pipeline` and then query `medallion.silver_orders` or `medallion.gold_daily_sales` to see data.

---

## Summary

| Step | What you did |
|------|-------------------------------|
| 1 | Created Postgres (Aiven or Neon). |
| 2 | Got host, port, database, user, password. |
| 3 | Built JDBC URL and set `POSTGRES_JDBC_URL` in `.env`. |
| 4 | Ran `scripts/sql/postgres_schema.sql` once. |
| 5 | Pipeline (when wired) will write to `medallion.*` tables. |

Same pattern as Kafka: one external service, one URL in `.env`, schema run once. No secrets in code.
