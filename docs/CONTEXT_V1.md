# Session context (v1) — handoff for next chat/session

**Use this file at the start of your next session so the AI (or you) has full context. Update it (e.g. to CONTEXT_V2.md) after major progress and note "continue from CONTEXT_V1" or the latest version.**

---

## 1. What we did so far

### Lesson 0–1: Foundation
- **Project:** Realtime Order Medallion (Medallion: Bronze → Silver → Gold), cloud-agnostic, Kafka + Spark.
- **Docs:** ARCHITECTURE.md, VIDEO_ANALYSIS.md, LEARNING_PATH.md, FILE_BY_FILE_GUIDE.md, SETUP_AND_RUN.md, PROJECT_STRUCTURE.md.
- **Config:** `config/pipeline.yaml` — Kafka, streaming, paths, `spark_packages`; env substitution (`${VAR:-default}`).
- **Config loader:** `streaming/config_loader.py` — loads YAML, substitutes env vars; `get_kafka_config()`, `get_paths_config()`, `get_streaming_config()`, `get_spark_packages()`.
- **Schema:** `streaming/schemas/order_events.py` — OrderEvent, OrderItem; enums (OrderType, PaymentMethod, OrderStatus); validation (non-empty IDs, UTC timestamp, min 1 item, total_amount >= 0); optional ORDER_ID_PATTERN.
- **Checks:** `streaming/lesson1_check.py`, `streaming/lesson2_check.py` — config + schema, config + Spark (no Kafka).

### Lesson 2: Bronze
- **Bronze job:** `streaming/bronze_orders.py` — Spark Structured Streaming: read from Kafka topic `orders` → add columns `value`, `_ingestion_ts`, `_source`, `_partition`, `_offset`, `_topic`, `_ingestion_date` → write Parquet to Bronze path, partitioned by `_ingestion_date`, with checkpoint.
- **Fix applied:** Kafka connector not in Spark by default → use `--packages` (value in `config/pipeline.yaml` under `spark_packages`: `org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2`).
- **Fix applied:** `options()` in PySpark expects kwargs → use `.options(**dict(read_opts))`.
- **Scripts:** `scripts/setup.sh` (pip install + Java check), `scripts/run_bronze.sh` (reads `spark_packages` from config, sets BASE_PATH/KAFKA_BOOTSTRAP_SERVERS, runs spark-submit). `scripts/produce_test_order.py` — produce one test order from **host** (Python + confluent_kafka).
- **Single-place deps:** `requirements.txt` header documents Python + Java + Spark Kafka (in config); `config/pipeline.yaml` has `spark_packages`; README and SETUP_AND_RUN point to one-place summary.

### Other
- **Git/Repo:** User pushed to GitHub repo `hotel-order-realtime-medallion`; docs/PUSH_TO_GITHUB.md and SETUP_AND_RUN.md updated.
- **Java:** User on macOS; installed OpenJDK 17 via Homebrew; PATH and JAVA_HOME set in ~/.zshrc. SETUP_AND_RUN has full Java install steps (macOS/Linux/Windows).
- **Kafka:** User has **Confluent Kafka** (containers kafka-broker-1/2/3 on host ports 29092, 39092, 49092). The single `apache/kafka` container (port 9092) was Exited. Bronze was run with **KAFKA_BOOTSTRAP_SERVERS=localhost:29092** and succeeded (batch 0 committed, 0 rows because topic was empty).
- **Producing test data:** `docker exec ... kafka-console-producer` from inside a broker container failed (metadata pointed to another broker at localhost:49092, not reachable from inside container). **Fix:** Produce from host: `KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python3 scripts/produce_test_order.py`.

---

## 2. Where we are now

- **Lesson 1:** Done (config, schema, checks).
- **Lesson 2 (Bronze):** Done and verified — job connects to Kafka (Confluent at 29092), subscribes to `orders`, commits checkpoint and writes to `/tmp/medallion/bronze/orders`. Topic was empty so batch 0 had 0 rows; job idles waiting for data.
- **Next in LEARNING_PATH:** Lesson 3 (Silver — cleanse, dedup, watermark), then Lesson 4 (Gold SQL), 5 (late data), 6 (DLQ), 7 (exactly-once), 8 (orchestration/CI), 9 (observability).
- **Repo state:** All code in place; user may need to run `chmod +x scripts/*.sh`; Kafka for local dev is Confluent at 29092 (not 9092).

---

## 3. Current errors / known issues (as of end of v1)

| Issue | Status / fix |
|-------|----------------|
| Kafka on 9092 | Not in use. Confluent brokers on 29092, 39092, 49092. Use `KAFKA_BOOTSTRAP_SERVERS=localhost:29092` for Bronze and producer. |
| Produce test message from inside Docker | Fails (metadata returns leader on another broker; localhost inside container ≠ other brokers). **Fix:** Produce from host: `python3 scripts/produce_test_order.py` with same bootstrap. |
| Scripts not executable | Run `chmod +x scripts/setup.sh scripts/run_bronze.sh` if needed. |

No unresolved code errors. Bronze pipeline is working.

---

## 4. Steps to run the project (quick reference)

**One-time setup**
1. Clone repo, `cd` to project root.
2. `pip install -r requirements.txt` (or `./scripts/setup.sh`).
3. Install Java 11+; set JAVA_HOME (see SETUP_AND_RUN.md §4).
4. `chmod +x scripts/setup.sh scripts/run_bronze.sh` if needed.

**Kafka (user has Confluent)**
- Brokers: localhost:29092, 39092, 49092. Create topic: e.g.  
  `docker exec kafka-broker-1 kafka-topics --bootstrap-server localhost:29092 --create --topic orders --partitions 1 --replication-factor 1`  
  (exact command may vary by Confluent image.)

**Run Bronze**
- `export BASE_PATH=/tmp/medallion` (or leave default in run_bronze.sh).
- `KAFKA_BOOTSTRAP_SERVERS=localhost:29092 ./scripts/run_bronze.sh`  
  (or set env and run script; script uses config for `spark_packages`.)

**Produce one test order (from host)**
- `KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python3 scripts/produce_test_order.py`

**Checks (no Kafka)**
- `python3 -m streaming.lesson1_check`
- `python3 -m streaming.lesson2_check`

---

## 5. Next plan (for next session)

1. **Lesson 3 — Silver:** Implement `streaming/silver_fact_orders.py`: read from Bronze (Parquet), parse JSON, dedupe by `order_id` with watermark, write Silver fact_orders (and optionally fact_order_items); use config (paths, watermark from pipeline.yaml).
2. **Lesson 4 — Gold:** Add `sql/gold_daily_sales.sql`, `gold_customer_360.sql`, `gold_restaurant_metrics.sql` and a small batch runner (Spark or SQL runner) that reads Silver and writes Gold.
3. **Lesson 6 — DLQ:** In Silver, route invalid rows to DLQ (Kafka topic or table); config already has `topic_dlq`.
4. **Docs:** Update SETUP_AND_RUN.md and FILE_BY_FILE_GUIDE.md as new scripts and steps are added.
5. **Optional:** Add Confluent Kafka (port 29092) as an option in SETUP_AND_RUN.md so future users with Confluent know to set KAFKA_BOOTSTRAP_SERVERS accordingly.

---

## 6. Key file locations

| What | Path |
|------|------|
| Pipeline config | `config/pipeline.yaml` |
| Config loader | `streaming/config_loader.py` |
| Order schema | `streaming/schemas/order_events.py` |
| Bronze job | `streaming/bronze_orders.py` |
| Run Bronze | `scripts/run_bronze.sh` |
| Produce test order | `scripts/produce_test_order.py` |
| Setup guide | `docs/SETUP_AND_RUN.md` |
| Learning path | `docs/LEARNING_PATH.md` |
| Architecture | `ARCHITECTURE.md` |

---

## 7. Instruction for next session

**When continuing development:** Read this file (and optionally the latest CONTEXT_V*.md) first. Then continue from "Next plan" above. Update this file or create CONTEXT_V2.md after significant progress so the next session has an up-to-date handoff.

---

*Last updated: end of session v1 (Lesson 2 Bronze done; Confluent Kafka at 29092; produce from host).*
