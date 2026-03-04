# Session context (v2) — handoff for next chat/session

**Use this file at the start of your next session. Continue from CONTEXT_V1; this adds Makefile, docker-compose, and run flow.**

---

## What changed in v2 (since v1)

- **Makefile** added as the single entry point: `make install`, `make kafka-up`, `make wait-kafka`, `make topics-create`, `make bronze`, `make produce`, `make run`, `make help`.
- **docker-compose.yml** added: one Kafka broker (KRaft) on port 9092 so `make kafka-up` starts Kafka without manual `docker run`.
- **scripts/create_topic.py**: creates topic `orders` via confluent_kafka AdminClient (idempotent); used by `make topics-create`.
- **scripts/wait_for_kafka.py**: waits until Kafka is reachable; used by `make wait-kafka`.
- **Producer default** set to `localhost:9092` when using project Kafka; for Confluent set `KAFKA_BOOTSTRAP_SERVERS=localhost:29092`.
- **“Why did it fail?”** — When you stop the Bronze job with **Ctrl+C**, you see Py4JError / “Error while sending or receiving”. That is **normal**: the JVM shuts down while Python is still in `awaitTermination()`. The job and checkpoint are fine. See SETUP_AND_RUN.md §11 (Py4JError when stopping Bronze).

---

## Steps to run (production-like flow)

**First-time**
1. `make install` — Python deps + Java check.
2. Install Java 11+ if not already (see docs/SETUP_AND_RUN.md §4).

**Every run (project Kafka on 9092)**
1. `make kafka-up` — start Kafka (docker-compose).
2. `make wait-kafka` — wait until broker is ready.
3. `make topics-create` — create topic `orders`.
4. Terminal 1: `make bronze` — run Bronze streaming job (leave running).
5. Terminal 2: `make produce` — send one test order.

**Or:** `make run` — does steps 1–3 and prints instructions for steps 4–5.

**Using Confluent Kafka (e.g. 29092)**  
Do **not** run `make kafka-up`. Set:
`export KAFKA_BOOTSTRAP_SERVERS=localhost:29092`  
Then: `make topics-create`, `make bronze`, `make produce`.

---

## Key files (v2)

| What | Path |
|------|------|
| **Makefile** | `Makefile` (run all targets from project root) |
| Docker Kafka | `docker-compose.yml` |
| Create topic | `scripts/create_topic.py` |
| Wait for Kafka | `scripts/wait_for_kafka.py` |
| Pipeline config | `config/pipeline.yaml` |
| Bronze job | `streaming/bronze_orders.py` |
| Run Bronze | `scripts/run_bronze.sh` |
| Produce test order | `scripts/produce_test_order.py` |
| Setup guide | `docs/SETUP_AND_RUN.md` (§8.0 Makefile flow) |

---

## Where we are / next plan

- **Lesson 1–2:** Done. Bronze runs via `make bronze`; use Makefile for full flow.
- **Next:** Lesson 3 (Silver), Lesson 4 (Gold), Lesson 6 (DLQ); update FILE_BY_FILE_GUIDE for new scripts.

**Instruction for next session:** Read CONTEXT_V1.md + this file. Use `make help` and docs/SETUP_AND_RUN.md §8.0 for the run flow. Update or create CONTEXT_V3 after more progress.

---

*Last updated: v2 — Makefile, docker-compose, create_topic, wait_for_kafka; Py4JError on Ctrl+C explained.*
