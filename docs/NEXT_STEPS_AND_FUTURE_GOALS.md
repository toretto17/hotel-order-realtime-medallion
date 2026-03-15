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

**Status:** ✅ **Done.** Bronze, Silver, and Gold all sync to Postgres (`medallion.bronze_orders`, `silver_orders`, `silver_order_items`, `gold_daily_sales`, `gold_customer_360`, `gold_restaurant_metrics`). Use `make postgres-schema` once, then `make pipeline`; optional `make postgres-backfill` if Bronze Parquet existed before Postgres was set up. See **docs/POSTGRES_SETUP_STEP_BY_STEP.md**.

---

## 2. Free website hosting with a “correct” domain

**Current:** Website can be hosted on [Render](https://render.com) (free tier) — see **docs/FREE_HOSTING.md**. Render gives you a **free subdomain** like `your-app.onrender.com`.

**“Correct” or custom domain (free of cost):**
- **Free subdomain:** `your-app.onrender.com` is a valid, free URL. No custom domain needed.
- **Custom domain (e.g. `orders.myhotel.com`):** You need to **own** the domain (purchase from a registrar, or use a free registrar if available). Render allows **adding a custom domain** on the free tier: in the Render dashboard → your Web Service → Settings → Custom Domain → add your domain and follow the CNAME/DNS steps. The **hosting** stays free; the **domain** may cost a few dollars per year unless you use a free option (e.g. Freenom historically; or GitHub Pages with a free subdomain like `username.github.io`).

**Status:** ✅ **Done.** Website is deployed on Render (free tier); live URL (e.g. `your-app.onrender.com`). Optional: attach a custom domain you own via Render → Settings → Custom Domain. See **docs/RENDER_WEBSITE_HOSTING_STEP_BY_STEP.md** and **docs/FREE_HOSTING.md**.

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

**Status:** ✅ **Done.** Single command **`make pipeline`** runs Bronze (micro-batch) → Silver → Gold in sequence, then exits. Bronze uses `TRIGGER_AVAILABLE_NOW=1` so it processes available Kafka messages and stops; Silver and Gold run once each. Optional: schedule `make pipeline` via Render Cron (or cron on a server) every few minutes for hands-off processing. See **scripts/run_pipeline.sh**.

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

## 5. Summary: goals and vision — achieved vs remaining

| Goal | Status | Notes |
|------|--------|------|
| **Postgres for queryable tables** | ✅ Done | Bronze, Silver, Gold all sync to Postgres. Schema: `make postgres-schema`. Backfill: `make postgres-backfill`. Doc: **docs/POSTGRES_SETUP_STEP_BY_STEP.md**. |
| **Free website + domain** | ✅ Done | Website on Render (free); live URL. Custom domain optional. Doc: **docs/RENDER_WEBSITE_HOSTING_STEP_BY_STEP.md**. |
| **Orchestrated pipeline** | ✅ Done | `make pipeline` runs Bronze → Silver → Gold once, then exits. Optional: schedule via Render Cron. |
| **Bronze micro-batch mode** | ✅ Done | `TRIGGER_AVAILABLE_NOW=1` in pipeline; process available messages and exit. |
| **Streaming vs micro-batch** | ✅ Documented | §4 in this doc; choice is config/env. |
| **Custom domain (your own URL)** | ⬜ Optional | Use Render subdomain or attach your domain in Render → Custom Domain. |
| **Fully hands-off trigger (e.g. cron every N min)** | ⬜ Optional | Render Cron (or server cron) can run `make pipeline` periodically so you don’t run it manually. |
| **Pipeline in cloud — no laptop (Oracle VM free)** | ⬜ Optional | Run the pipeline on a **free Oracle Cloud Always Free VM** with cron (e.g. every 10–15–30 min). Orders at 3 AM get processed; you see data in the morning. Step-by-step: **docs/PIPELINE_IN_CLOUD_FREE.md** (includes creating `cron_run.sh` if missing and verification). |
| **Dashboard / BI (Grafana, etc.)** | ⬜ Future | Postgres tables are ready; connect a BI tool or build a simple dashboard. |
| **Full runbook (start to end)** | ⬜ Planned | Single document from account creation → VM + cron → verification and common ops so any operator can track and reproduce setup. To be created once the project is complete; **docs/PIPELINE_IN_CLOUD_FREE.md** is the authoritative pipeline-in-cloud section. |

**Achieved so far:** Medallion pipeline (Bronze → Silver → Gold) with Aiven Kafka, Parquet + Postgres sync for all layers, hosted website on Render, and one-command pipeline run. Orders are visible in Postgres. **Remaining (optional):** custom domain, scheduled pipeline trigger, **Oracle (or other) free VM + cron** for “no laptop” runs, a BI dashboard, and a **full runbook**.

---

## 6. Full runbook (planned)

**Goal:** Once the project is complete, create a **single runbook (start to end)** so any operator can:

- Follow one document from account creation through VM + cron setup and verification.
- Track exactly what was done and reproduce the same setup.
- Use it for handover, onboarding, or creating a second environment.

**Content (planned):** Account sign-up → Oracle (or other) VM creation → install stack (Java, Python, Spark, repo) → configure `.env` and certs → ensure `cron_run.sh` exists and set up cron → verification (crontab, log, data). Optional: common ops (view logs, trigger run from Mac, check Postgres).

**Today:** **docs/PIPELINE_IN_CLOUD_FREE.md** is the authoritative step-by-step for the pipeline-in-cloud part and is written so it can be used as that section of the future runbook.
