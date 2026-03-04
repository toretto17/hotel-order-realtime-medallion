# File-by-File Guide — What Each File Does and How the Flow Works

This document explains **every file** in the project: **why it exists**, **what it must provide**, **how the code works**, and **how it fits in the end-to-end flow**. Use it for deep understanding and interview prep.

---

## 1. End-to-End Flow (Big Picture)

Before diving into files, here is how data and config move through the system **today** (Lesson 1) and **where they will go** (Lessons 2–9).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  SOURCES (future)                                                                │
│  POS/API → order events  │  PostgreSQL (CDC)  │  Optional: REST/Files            │
└──────────────────────────┴───────────────────┴──────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  KAFKA  (topic: orders)   ←── config/pipeline.yaml (topic_orders, bootstrap)     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          ▼                             ▼                             ▼
┌──────────────────┐    ┌──────────────────────────────┐    ┌──────────────────┐
│ config/          │    │ streaming/                    │    │ streaming/        │
│ pipeline.yaml    │───►│ config_loader.py              │    │ schemas/          │
│ (all knobs)      │    │ (reads YAML, env substitute)  │    │ order_events.py   │
└──────────────────┘    └──────────────────────────────┘    │ (parse, validate) │
          │                             │                    └──────────────────┘
          │                             │                             │
          │                             │    Every job uses config + schema
          ▼                             ▼                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  BRONZE (Lesson 2)  →  Spark reads Kafka, writes raw + metadata to Parquet        │
│  SILVER (Lesson 3)  →  Read Bronze, dedupe, watermark, write fact_orders       │
│  GOLD (Lesson 4+)   →  Batch from Silver → daily_sales, customer_360, etc.     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Right now (Lesson 1):** We have **config**, **schema**, and a **check script**. No Kafka or Spark jobs yet. The flow above shows where those pieces will plug in.

---

## 2. Repository Layout (What Lives Where)

```
realtime-order-medallion/
├── README.md                    # Entry point; links to architecture and learning path
├── ARCHITECTURE.md              # Full design: diagram, stack, Medallion, exactly-once, etc.
├── requirements.txt             # Python deps: PySpark, Kafka, YAML, Postgres, pytest
├── config/
│   └── pipeline.yaml            # Single config file: Kafka, streaming, paths, Postgres
├── docs/
│   ├── FILE_BY_FILE_GUIDE.md   # This file
│   ├── LEARNING_PATH.md        # Step-by-step curriculum (Lesson 0 → 9)
│   ├── PROJECT_STRUCTURE.md     # How to create a new project with this layout
│   └── VIDEO_ANALYSIS.md       # Databricks video → this repo mapping
├── streaming/
│   ├── __init__.py             # Package marker
│   ├── config_loader.py        # Load pipeline.yaml + env substitution
│   ├── lesson1_check.py        # Runnable check: config + schema work
│   └── schemas/
│       ├── __init__.py         # Re-exports OrderEvent, OrderItem, enums, etc.
│       └── order_events.py     # Order event + item schema; validation; enums
└── sql/
    └── __init__.py             # Placeholder for Gold SQL (Lesson 4+)
```

---

## 3. Each File Explained (Purpose, Requirements, Code, Example)

### 3.1 `README.md`

| What | Detail |
|------|--------|
| **Purpose** | Entry point for the repo: project name, one-line description, where to read next. |
| **Why we created it** | So anyone (or any LLM) knows the project name, the architecture doc, and the learning path in one place. |
| **Required from it** | Clear project name (`realtime-order-medallion`), links to ARCHITECTURE.md, VIDEO_ANALYSIS.md, PROJECT_STRUCTURE.md, and LEARNING_PATH.md. |

**Flow role:** Points you to the design (ARCHITECTURE) and the step-by-step build (LEARNING_PATH). It does not run; it orients.

---

### 3.2 `ARCHITECTURE.md`

| What | Detail |
|------|--------|
| **Purpose** | Single source of truth for the whole system: diagram, tech choices, Medallion layers, exactly-once, checkpointing, DLQ, partitioning, CI/CD, IaC, production checklist. |
| **Why we created it** | So the design is written down once; every lesson and every file can align to it. Interview-ready: you can walk through this doc and explain each decision. |
| **Required from it** | High-level diagram (text), technology justification, Bronze/Silver/Gold design, data models, exactly-once strategy, late data, checkpointing, partitioning, error handling, CI/CD, IaC, production checklist. |

**Flow role:** Defines *what* we build. Config and schema (and later jobs) implement this design.

---

### 3.3 `requirements.txt`

| What | Detail |
|------|--------|
| **Purpose** | List of Python dependencies so the project can run (locally or in a container). |
| **Why we created it** | One place to install deps; same versions across dev and CI. |
| **Required from it** | pyspark, confluent-kafka (or kafka client), pyyaml, psycopg2, pytest — with version pins where needed. |

**Example:**

```bash
pip install -r requirements.txt
```

**Flow role:** Nothing runs without these; `config_loader` needs `pyyaml`; later jobs need `pyspark` and Kafka.

---

### 3.4 `config/pipeline.yaml`

| What | Detail |
|------|--------|
| **Purpose** | **All pipeline knobs in one file:** Kafka, streaming behavior, paths (Bronze/Silver/Gold, checkpoints), optional Postgres. No topic names or paths hardcoded in Python. |
| **Why we created it** | Config-over-code: change environment (dev/staging/prod) by env vars, not code. Same binary everywhere (12-factor). |
| **Required from it** | Keys: `kafka` (bootstrap, topics, group, starting offsets), `streaming` (trigger, watermark, lateness, fail_on_data_loss), `paths` (base, checkpoints, bronze/silver/gold), optional `postgres`. Values can use `${VAR:-default}`. |

**Code example (excerpt):**

```yaml
kafka:
  bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
  topic_orders: "orders"
  topic_dlq: "orders_dlq"
  consumer_group: "order-medallion-v1"
  starting_offsets: "latest"

paths:
  base: "${BASE_PATH:-s3://your-bucket/data}"
  checkpoint_bronze: "${BASE_PATH}/checkpoints/bronze_orders"
  bronze_orders: "${BASE_PATH}/bronze/orders"
  # ...
```

**Flow role:** Every job will call `config_loader.load_config()` and use these values. Env vars override defaults (e.g. `BASE_PATH`, `KAFKA_BOOTSTRAP_SERVERS`).

---

### 3.5 `streaming/config_loader.py`

| What | Detail |
|------|--------|
| **Purpose** | Load `config/pipeline.yaml`, substitute `${VAR:-default}` with environment variables, and expose the result so any job can get Kafka, streaming, or paths config without duplicating logic. |
| **Why we created it** | One place that knows where the config file is and how to expand env vars; jobs stay simple and testable (e.g. pass a different path in tests). |
| **Required from it** | `load_config(path?)` → full dict; `get_kafka_config()`, `get_streaming_config()`, `get_paths_config()` for convenience; substitution must recurse into nested dicts/lists. |

**How the code works:**

1. **`_ENV_PATTERN`** — Regex for `${VAR}` or `${VAR:-default}`.  
2. **`_substitute_env(value)`** — If `value` is a string, replace all matches with `os.environ.get(key, default)`; if dict/list, recurse.  
3. **`load_config(config_path)`** — Default path = repo root + `config/pipeline.yaml`. Read YAML, then run `_substitute_env` on the whole tree.  
4. **`get_kafka_config(config?)`** — Return `config["kafka"]` or load config if not passed. Same idea for streaming and paths.

**Example:**

```python
from streaming.config_loader import load_config, get_kafka_config, get_paths_config

config = load_config()
# Without env set: base = "s3://your-bucket/data", bootstrap = "localhost:9092"
# With BASE_PATH=/data and KAFKA_BOOTSTRAP_SERVERS=kafka:9092:
#   base = "/data", bootstrap = "kafka:9092"

kafka = get_kafka_config(config)
print(kafka["topic_orders"])   # "orders"
print(kafka["bootstrap_servers"])

paths = get_paths_config(config)
print(paths["bronze_orders"])  # "${BASE_PATH}/bronze/orders" → expanded
```

**Flow role:** Bronze/Silver/Gold jobs will start with `config = load_config()` and pass sections to Spark (Kafka options, checkpoint path, output path).

---

### 3.6 `streaming/schemas/order_events.py`

| What | Detail |
|------|--------|
| **Purpose** | **Single source of truth for the order event:** structure (OrderEvent, OrderItem), allowed values (enums), validation (non-empty, timestamp UTC, amount ≥ 0, min one item). Invalid payloads raise; valid ones are parsed into typed objects. |
| **Why we created it** | So the pipeline knows exactly what an order is, what is valid, and what is the idempotency key (`order_id`). Production DQ at parse time; no freeform text where we need enums. |
| **Required from it** | (1) OrderEvent and OrderItem with `from_dict` / `to_dict`. (2) Enums for order_type, payment_method, order_status. (3) Validation: non-empty IDs, ISO8601 timestamp → UTC, items length ≥ 1, total_amount ≥ 0. (4) Optional order_id pattern. (5) JSON schema for docs/Spark. |

**How the code works:**

1. **Enums** — `OrderType`, `PaymentMethod`, `OrderStatus`: only allowed values; `from_dict` uses them and raises if invalid.  
2. **`_require_non_empty(s, field_name)`** — Strip and reject empty string; used for order_id, restaurant_id, customer_id, item_id.  
3. **`_parse_utc_timestamp(ts)`** — Parse ISO8601, normalize to UTC, return ISO8601 string; used for event-time and watermarking.  
4. **`_validate_order_id(order_id)`** — Non-empty; if `ORDER_ID_PATTERN` is set (e.g. `re.compile(r"^ord-\d{8}$")`), must match.  
5. **`OrderItem.from_dict(d)`** — Build item; require non-empty `item_id`.  
6. **`OrderEvent.from_dict(d)`** — Validate enums, items length ≥ 1, total_amount ≥ 0; call the helpers above; return `OrderEvent`.  
7. **`OrderEvent.to_dict()`** — Serialize back to dict (enum → `.value`).  
8. **`ORDER_EVENT_JSON_SCHEMA`** — For documentation or Spark schema-on-read; not used in Python validation.

**Example:**

```python
from streaming.schemas.order_events import OrderEvent, OrderType, OrderStatus

good = {
    "order_id": "ord-00000001",
    "order_timestamp": "2025-03-04T12:00:00Z",
    "restaurant_id": "R1",
    "customer_id": "C1",
    "order_type": "delivery",
    "items": [{"item_id": "I1", "name": "Burger", "category": "main", "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}],
    "total_amount": 10.0,
    "payment_method": "card",
    "order_status": "completed",
}
event = OrderEvent.from_dict(good)
assert event.order_id == "ord-00000001"
assert event.order_type == OrderType.DELIVERY
assert event.to_dict()["order_type"] == "delivery"

# Invalid: empty customer_id
bad = {**good, "customer_id": "  "}
OrderEvent.from_dict(bad)  # ValueError: customer_id must be non-empty
```

**Flow role:** In Bronze we might store raw JSON; in Silver we will parse with `OrderEvent.from_dict`. Valid rows go to fact tables; invalid rows go to DLQ (Lesson 6).

---

### 3.7 `streaming/schemas/__init__.py`

| What | Detail |
|------|--------|
| **Purpose** | Re-export the public API of the schemas package so callers can do `from streaming.schemas import OrderEvent, OrderItem, OrderType, ...` instead of importing from `order_events` directly. |
| **Why we created it** | Clean imports; one place to see what is “public” (OrderEvent, OrderItem, enums, ORDER_EVENT_JSON_SCHEMA). |
| **Required from it** | Import from `order_events` and set `__all__` so `from streaming.schemas import *` is predictable. |

**Example:**

```python
from streaming.schemas import OrderEvent, OrderItem, OrderType, PaymentMethod, OrderStatus
```

**Flow role:** Any module that needs the order contract imports from `streaming.schemas`.

---

### 3.8 `streaming/lesson1_check.py`

| What | Detail |
|------|--------|
| **Purpose** | **Runnable proof** that Lesson 1 is wired: config loads (with env substitution), a sample order parses and round-trips. No Kafka or Spark. |
| **Why we created it** | So you can run one command and see that config + schema work; catches path or import mistakes early. |
| **Required from it** | (1) Load config and print Kafka/paths. (2) Parse a sample order with `OrderEvent.from_dict`. (3) Round-trip `event.to_dict()` and assert order_id matches. Exit 0 if all pass. |

**How the code works:**

1. Ensures repo root is on `sys.path` so `streaming.config_loader` and `streaming.schemas` resolve.  
2. Calls `load_config()`, `get_kafka_config()`, `get_paths_config()` and prints a few values.  
3. Builds a minimal valid order dict and calls `OrderEvent.from_dict(sample)`.  
4. Calls `event.to_dict()` and asserts `back["order_id"] == sample["order_id"]`.  
5. Prints “Lesson 1 check passed.”

**Example (run from repo root):**

```bash
pip install pyyaml
python -m streaming.lesson1_check
```

**Flow role:** Validates that the foundation (config + schema) is correct before you add Bronze/Silver jobs.

---

### 3.9 `streaming/__init__.py`

| What | Detail |
|------|--------|
| **Purpose** | Marks `streaming` as a Python package so you can `import streaming.config_loader` and `from streaming.schemas import OrderEvent`. |
| **Why we created it** | Without it, Python does not treat `streaming` as a package and imports break. |
| **Required from it** | File exists (content is optional; we added a short comment). |

**Flow role:** Enables all `streaming.*` and `from streaming.schemas import ...` imports.

---

### 3.10 `sql/__init__.py`

| What | Detail |
|------|--------|
| **Purpose** | Placeholder for the `sql` package where Gold-layer SQL and batch scripts will live (Lesson 4+). |
| **Why we created it** | So the repo layout matches the architecture (streaming + sql) and we can add `sql/gold_daily_sales.sql` etc. without restructuring. |
| **Required from it** | Nothing yet; just a package marker. |

**Flow role:** Future: Gold SQL files and a small runner that reads Silver and writes Gold tables.

---

### 3.11 `docs/LEARNING_PATH.md`

| What | Detail |
|------|--------|
| **Purpose** | Step-by-step curriculum: Lesson 0 (orientation) through Lesson 9 (observability). Each lesson has goal, concepts, deliverables, and interview angle. |
| **Why we created it** | So you build in order (config/schema → Bronze → Silver → Gold → DLQ → exactly-once → orchestration → observability) and know what “done” looks like for each step. |
| **Required from it** | Clear lesson list, deliverables per lesson, and “how to use this path” (one lesson at a time, run and experiment). |

**Flow role:** Tells you what to build next and how it fits the flow.

---

### 3.12 `docs/PROJECT_STRUCTURE.md`

| What | Detail |
|------|--------|
| **Purpose** | Instructions for creating a *new* project with the same name and layout (where to put ARCHITECTURE.md, VIDEO_ANALYSIS.md, etc.). |
| **Why we created it** | Reproducibility: clone or fork and know exactly where docs and config go. |
| **Required from it** | Project name, folder layout, and steps to add ARCHITECTURE.md and VIDEO_ANALYSIS.md. |

**Flow role:** Meta: how to spin up another repo that follows this design.

---

### 3.13 `docs/VIDEO_ANALYSIS.md`

| What | Detail |
|------|--------|
| **Purpose** | Map the Databricks E2E video (Afaque Ahmad) to this repo: what’s equivalent (Event Hub → Kafka, LakeFlow → Debezium + Kafka Connect), what we improved (exactly-once, DLQ, checkpoint, etc.). |
| **Why we created it** | So the design is generic and tool-agnostic; you learn concepts, not only Databricks. |
| **Required from it** | Video architecture summary, best-practices table, gaps vs production, and mapping table (video component → this repo). |

**Flow role:** Bridges “what the video does” to “what we implement in code and config.”

---

## 4. How the Pieces Connect (Flow Summary)

| Step | What happens | Files involved |
|------|----------------|----------------|
| 1 | You run a job (today: `lesson1_check`; later: Bronze/Silver) | Entry script (e.g. `streaming/lesson1_check.py` or `streaming/bronze_orders.py`) |
| 2 | Job loads config | `config/pipeline.yaml` → `streaming/config_loader.load_config()` |
| 3 | Job needs topic names, paths, checkpoint dir | `get_kafka_config()`, `get_paths_config()`, etc. from config_loader |
| 4 | Job receives raw event (e.g. from Kafka or from Bronze file) | Raw JSON string or dict |
| 5 | Job parses and validates event | `streaming.schemas.order_events.OrderEvent.from_dict(payload)` |
| 6 | If valid: use event (e.g. write to Silver). If invalid: send to DLQ. | Silver job (Lesson 3) / DLQ (Lesson 6) |
| 7 | Event time for watermarking/partitioning | `event.order_timestamp` (already UTC string from schema) |
| 8 | Idempotency in Silver | Merge/upsert by `event.order_id` (defined and validated in schema) |

So: **Config** drives where we read/write and how we connect. **Schema** defines what an order is and what we accept. **Lesson 1 check** proves both work. Later lessons add the actual read/write (Kafka, Parquet, Delta) on top of this same config and schema.

---

## 5. Quick Reference: “What do I use where?”

| Need | Use |
|------|-----|
| Topic name, bootstrap servers, consumer group | `get_kafka_config()` from config_loader |
| Checkpoint path, Bronze/Silver/Gold paths | `get_paths_config()` from config_loader |
| Trigger interval, watermark delay | `get_streaming_config()` from config_loader |
| Parse and validate one order JSON | `OrderEvent.from_dict(d)` from schemas |
| Serialize order back to dict/JSON | `event.to_dict()` |
| Allowed values for order_type / payment_method / order_status | Enums in `streaming.schemas` (OrderType, PaymentMethod, OrderStatus) |
| Prove config + schema work | `python -m streaming.lesson1_check` |

---

*Next:* Lesson 2 adds `streaming/bronze_orders.py`, which uses this config and (optionally) this schema to read from Kafka and write to Bronze storage.
