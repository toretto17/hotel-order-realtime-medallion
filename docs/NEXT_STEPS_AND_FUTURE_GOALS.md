# Next steps & future goals (production-level)

This doc covers: **Postgres** (queryable Bronze/Silver/Gold), **free website hosting with domain**, **orchestrated pipeline** (trigger Bronze → Silver → Gold automatically, cost-effective), and **streaming patterns & latency** (when order is received, how fast it should be processed — Zomato/IPO style). It reflects production-level choices and trade-offs.

---

## 1. Postgres: do we need it for Bronze, Silver, Gold?

**Short answer:** Not required for the pipeline to work. Postgres is **optional** and used as a **serving layer** when you want **queryable tables** (e.g. for dashboards, APIs, or ad-hoc SQL).

| Layer   | Current storage        | Optional: Postgres (or other DB)      |
|---------|------------------------|---------------------------------------|
| Bronze  | Parquet (files)        | Possible but rare; usually keep Parquet for raw. |
| Silver  | Parquet (files)        | Can sync to Postgres for queryable cleaned data. |
| Gold    | Parquet (files)        | **Common:** sink Gold tables to Postgres for BI, APIs, reporting. |

**Why Parquet today:** Cheap, scalable, and works well with Spark. Bronze/Silver/Gold are written as Parquet under `BASE_PATH`. You can query them with Spark, Trino, or similar.

**When to add Postgres:**
- You want to **query** orders or metrics with **SQL** (e.g. from a dashboard, Grafana, or internal tool) without spinning up Spark.
- You want a **serving layer**: e.g. Gold tables (`daily_sales`, `customer_360`, `restaurant_metrics`) in Postgres so a BI tool or API can read them.
- You need **ACID** and **indexes** for low-latency lookups (e.g. “show this customer’s orders”).

**Next steps (future goal):**
- Add a **Gold → Postgres** sink (batch or streaming): after Gold job runs, write/upsert `daily_sales`, `customer_360`, `restaurant_metrics` to Postgres. Config already has `postgres` section in `pipeline.yaml` for this.
- Optionally: **Silver → Postgres** for queryable order/order_items tables if you want to query cleaned data without Spark.

So: **Bronze/Silver/Gold stay in Parquet for processing.** Postgres is for **queryable storage** (mainly Gold, optionally Silver), not for replacing Parquet.

---

## 2. Free website hosting with a “correct” domain

**Current:** Website can be hosted on [Render](https://render.com) (free tier) — see **docs/FREE_HOSTING.md**. Render gives you a **free subdomain** like `your-app.onrender.com`.

**“Correct” or custom domain (free of cost):**
- **Free subdomain:** `your-app.onrender.com` is a valid, free URL. No custom domain needed.
- **Custom domain (e.g. `orders.myhotel.com`):** You need to **own** the domain (purchase from a registrar, or use a free registrar if available). Render allows **adding a custom domain** on the free tier: in the Render dashboard → your Web Service → Settings → Custom Domain → add your domain and follow the CNAME/DNS steps. The **hosting** stays free; the **domain** may cost a few dollars per year unless you use a free option (e.g. Freenom historically; or GitHub Pages with a free subdomain like `username.github.io`).

**Next steps (future goal):**
- Deploy website to Render (or similar) using **docs/FREE_HOSTING.md**.
- Use the free Render subdomain, or attach a custom domain you own for a “proper” URL.

---

## 3. Orchestrated pipeline: trigger Bronze → Silver → Gold automatically (cost-effective)

**Today:** You run `make bronze` (leave running), then later `make silver`, then `make gold` manually. Good for learning; not ideal for “when I order, I want everything to process and stop without me running three jobs.”

**What you want:** When an order lands from the web, **Bronze runs and processes** (then stops), then **Silver runs** on the new Bronze data (then stops), then **Gold runs** on the new Silver data. No long-running streaming jobs; **triggered, cost-effective** runs.

**Two main production patterns:**

| Pattern | How it works | Latency | Cost | When to use |
|--------|----------------|---------|------|-------------|
| **Long-running streaming** | Bronze (and optionally Silver) run 24/7; process events as they arrive. | Low (seconds) | Higher (always-on) | High volume, need low latency (e.g. Zomato live dashboards). |
| **Triggered / micro-batch** | A scheduler or event triggers a job; it processes “what’s new” then exits. Next job (Silver) runs after Bronze; Gold after Silver. | Batch interval (e.g. 1–5 min) | Lower (pay per run) | Low/medium volume, cost-sensitive; analytics can be near real-time (e.g. 1–5 min). |

**For “order received → process and stop”:**
- **Option A — Event-driven orchestration:** When a message lands in Kafka (or when a web order is placed), trigger a **pipeline run**: run Bronze (micro-batch: read new messages, write to Bronze, exit) → then trigger Silver (read new Bronze, write Silver, exit) → then trigger Gold (read Silver, write Gold, exit). Tools: **Airflow**, **Prefect**, **Dagster**, or a simple **cron + script** that runs every 1–5 minutes.
- **Option B — Short-interval streaming:** Keep Bronze as a **streaming** job but with a **short trigger** (e.g. every 10–30 seconds or “availableNow”). It stays running but processes in small batches; then a separate scheduled job runs Silver and Gold every 1–5 min. Lower “hands-off” than full trigger chain but still automated.

**Next steps (future goal):**
- Add an **orchestrator** (e.g. Airflow DAG or a single script) that: (1) runs Bronze in micro-batch mode (process new Kafka messages, then exit), (2) runs Silver on new Bronze data, (3) runs Gold on Silver. Schedule it (e.g. every 2–5 min) or trigger it on “new data” (e.g. Kafka consumer lag or webhook).
- Document **micro-batch** mode for Bronze (e.g. `TRIGGER_AVAILABLE_NOW=1` or a short trigger interval) so each run processes only available messages and exits.

---

## 4. Streaming deep-dive: latency and how fast orders should be processed

**Order acceptance (user-facing):** When a customer places an order on the **website**, the response should be **immediate** (sub-second). That is already the case: the web app produces to Kafka and returns “Order placed.” Kafka and the pipeline do **not** block the user.

**Analytics / backend (when does Bronze/Silver/Gold need to reflect the order?):**
- **Zomato / Swiggy / IPO-style:** “Order received” is instant (Kafka). For **live ops dashboards** (e.g. “orders in last 5 min”), companies often use:
  - **Streaming** with short triggers (e.g. 10–30 s) so Bronze/Silver update often; or
  - **Kafka + real-time layer** (e.g. ksqlDB or Flink) for sub-minute visibility, and batch Gold every 5–15 min.
- **Typical latency targets:**
  - **Order visible in “recent orders” (Bronze):** seconds to ~1 minute (streaming or micro-batch every 1 min).
  - **Order in cleaned / Silver:** 1–5 minutes is acceptable for many use cases.
  - **Order in Gold (daily_sales, etc.):** 5–15 min or hourly is common; not sub-second.

**So:** Keeping **streaming** for Bronze (with a short trigger) gives you **low latency** (new orders show up in Bronze within a trigger interval). For **cost-effective** “run and stop” behavior, use **triggered micro-batch** plus an orchestrator so Bronze → Silver → Gold run in sequence without you manually starting each job. Both are production-valid; choice depends on volume and cost vs latency.

---

## 5. Summary: next steps and future goals (checklist)

| Goal | What to do | Doc / reference |
|------|------------|------------------|
| **Postgres for queryable tables** | Add Gold (and optionally Silver) sink to Postgres; use for dashboards/APIs. | `config/pipeline.yaml` has `postgres` section; add write step in Gold job or a separate sync job. |
| **Free website + domain** | Deploy to Render; use free subdomain or attach custom domain you own. | **docs/FREE_HOSTING.md** |
| **Orchestrated pipeline** | Automate Bronze → Silver → Gold (triggered/micro-batch); run via Airflow/Prefect/cron or event. | This doc §3; add DAG or `scripts/run_pipeline_batch.sh`. |
| **Streaming vs micro-batch** | Choose: long-running Bronze (low latency) or triggered Bronze (cost-effective); document trigger interval and latency. | This doc §4 |
| **Bronze micro-batch mode** | Support “process available messages then exit” (e.g. `TRIGGER_AVAILABLE_NOW=1`) for orchestrated runs. | Already in place via env; document in SETUP_AND_RUN. |

These are the **next steps** and **future goals** for a production-level, cost-effective, and (optionally) low-latency order pipeline with queryable storage and hosted website.
