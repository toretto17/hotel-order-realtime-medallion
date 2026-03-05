# Realtime Order Medallion

**Production-grade real-time order processing using Medallion Architecture (Bronze, Silver, Gold).**  
Cloud-agnostic · Kafka + Spark Structured Streaming · PostgreSQL optional.

---

## Project name

**Repository / project name:** `realtime-order-medallion`

- **realtime** — streaming, near real-time analytics  
- **order** — domain (order processing and analytics)  
- **medallion** — Bronze → Silver → Gold architecture  

Use this same name when cloning, creating a new repo, or referring to the project.

---

## Where the main docs live

| Document | Location | Purpose |
|----------|----------|--------|
| **Architecture & design** | [ARCHITECTURE.md](./ARCHITECTURE.md) | High-level diagram, tech stack, Medallion layers, data models, exactly-once, checkpointing, DLQ, CI/CD, IaC, production checklist. |
| **Video analysis** | [docs/VIDEO_ANALYSIS.md](./docs/VIDEO_ANALYSIS.md) | Breakdown of the Databricks E2E video: best practices, gaps, and mapping to this (generic) design. |
| **How to create this project** | [docs/PROJECT_STRUCTURE.md](./docs/PROJECT_STRUCTURE.md) | How to create a new project with the correct name and add these two files. |
| **File-by-file guide** | [docs/FILE_BY_FILE_GUIDE.md](./docs/FILE_BY_FILE_GUIDE.md) | What each file does, with code examples and end-to-end flow. |
| **Setup and run (new users)** | [docs/SETUP_AND_RUN.md](./docs/SETUP_AND_RUN.md) | Step-by-step: install, configure, run Lesson 1–2, and later lessons. |
| **Order flow, timing & Kafka SSL** | [docs/FLOW_AND_KAFKA_SSL.md](./docs/FLOW_AND_KAFKA_SSL.md) | What happens when you order; when to run Bronze/Silver/Gold; how Kafka + SSL work; “bad certificate” fix; production-level notes. |
| **Session context (handoff)** | [docs/CONTEXT_V1.md](./docs/CONTEXT_V1.md), [docs/CONTEXT_V2.md](./docs/CONTEXT_V2.md) | What we did, where we are, steps to run (Makefile flow). Start here when continuing in a new chat. |
| **Next steps & future goals** | [docs/NEXT_STEPS_AND_FUTURE_GOALS.md](./docs/NEXT_STEPS_AND_FUTURE_GOALS.md) | Postgres (queryable tables), free hosting + domain, orchestrated pipeline, streaming vs latency. |
| **Render website hosting (step-by-step)** | [docs/RENDER_WEBSITE_HOSTING_STEP_BY_STEP.md](./docs/RENDER_WEBSITE_HOSTING_STEP_BY_STEP.md) | Free website + domain; deploy so friends/users can order from a live URL. |
| **Product scope** | [docs/PRODUCT_SCOPE.md](./docs/PRODUCT_SCOPE.md) | What we’re building: single restaurant (hotel) app vs Zomato/Swiggy-style aggregator; when restaurant_id matters. |

---

## Learning path (step-by-step)

**Build and learn incrementally:** [docs/LEARNING_PATH.md](./docs/LEARNING_PATH.md) defines a lesson-by-lesson curriculum. Start with Lesson 1 (data contract & config), then Bronze → Silver → Gold → DLQ → exactly-once → orchestration. Each lesson has clear concepts and deliverables so you learn deeply and can speak to it in interviews.

## Requirements (one-place summary)

- **Python:** `requirements.txt` — run `pip3 install -r requirements.txt` or `make install`.
- **Java 11+:** For Spark; not in pip. See [docs/SETUP_AND_RUN.md](./docs/SETUP_AND_RUN.md#4-install-java-required-for-spark--lesson-2).
- **Spark Kafka connector:** In `config/pipeline.yaml` (`spark_packages`); used by `make bronze` / `./scripts/run_bronze.sh`.
- **Kafka:** This project uses **Aiven Kafka only** (no local Docker). Configure `.env` with Aiven credentials; see [docs/AIVEN_SETUP_STEP_BY_STEP.md](./docs/AIVEN_SETUP_STEP_BY_STEP.md) and [SETUP_AND_RUN.md](./docs/SETUP_AND_RUN.md).

## Quick run (Makefile) — Aiven Kafka only

From the project root after `make install` and **configuring `.env` with Aiven Kafka credentials** ([docs/AIVEN_SETUP_STEP_BY_STEP.md](./docs/AIVEN_SETUP_STEP_BY_STEP.md)):

```bash
make wait-kafka      # Wait until Aiven Kafka is ready
make topics-create   # Create topic 'orders' on Aiven
make bronze          # Terminal 1: run Bronze job (leave running)
make produce         # Terminal 2: send one test order (or make web for the website)
make silver          # After Bronze has data
make gold            # After Silver has data
make web             # Hotel ordering website (localhost:5000); orders → Aiven Kafka → Bronze
```

Or: **`make run`** to wait for Aiven and create the topic; then run `make bronze` (T1) and `make produce` or `make web` (T2). See `make help`.

**Hotel website:** Run **`make web`** (with **`make bronze`** running in another terminal). Open http://127.0.0.1:5000; orders go to Aiven Kafka and Bronze processes them. See [docs/SETUP_AND_RUN.md](./docs/SETUP_AND_RUN.md).

## Future project goals

- **Source / ingester:** A system (script, API, or app) that produces **varied order events** — different `order_id`s, food names, quantities, amounts — so the pipeline is exercised with realistic, diverse data (not only the single test order).
- **Hotel ordering website (localhost):** Implemented: run **`make web`**; place orders in the browser → Kafka → Bronze → Silver → Gold. **Your orders** tab shows orders for the current session; **Admin** tab (set `ADMIN_PASSWORD` in env) lets the owner view all orders and **Mark done** (status update is sent to Kafka so Silver/Gold reflect completed/done). No sign-in for customers; session identifies "your" orders.
- **Dashboard (later):** A dashboard (e.g. BI or simple UI) that reads from Gold (and/or Silver) to show orders, sales, or other metrics. Optional; part of the project roadmap.
- **Live hosting:** This project uses **Aiven Kafka** (persistent). For zero-cost: free Kafka ([Aiven](https://aiven.io/free-kafka)) + free web host ([Render](https://render.com)) — **docs/FREE_HOSTING.md**.

- **Postgres (queryable tables):** Optional serving layer — sink Gold (and optionally Silver) to Postgres. **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §1.
- **Free website + domain:** Render free subdomain or custom domain. **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §2.
- **Orchestrated pipeline:** Trigger Bronze → Silver → Gold automatically (micro-batch + orchestrator). **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §3.
- **Streaming vs latency:** Long-running vs triggered; Zomato/IPO-style. **docs/NEXT_STEPS_AND_FUTURE_GOALS.md** §4.

**Full next steps and production choices:** **docs/NEXT_STEPS_AND_FUTURE_GOALS.md**. Production approach: **docs/VIDEO_ANALYSIS.md** §6–7 and **ARCHITECTURE.md**.

---

## Quick start (learning)

1. Read **ARCHITECTURE.md** for the full design.  
2. Read **docs/LEARNING_PATH.md** and start with **Lesson 1**.  
3. Read **docs/VIDEO_ANALYSIS.md** to see how the reference video maps to this repo.  
4. Use **docs/PROJECT_STRUCTURE.md** to spin up a new project with the same layout and docs.
