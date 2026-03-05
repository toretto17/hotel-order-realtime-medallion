# Setup and Run Guide — For New Users Who Fork This Repo

This document is the **single place** for configuring and running this project. Follow the steps in order. Use it when you fork the repo or onboard someone new.

---

## Who This Is For

- You forked or cloned this repository and want to run the same code.
- You need to know exactly what to install, how to configure, and in what order to run things.
- You want a reference for **all steps now and for future lessons** (Silver, Gold, DLQ, etc.).

---

## One-place dependency summary

| What | Where | How to install / use |
|------|--------|----------------------|
| **Python packages** | `requirements.txt` | `pip3 install -r requirements.txt` or `make install` |
| **Java 11+** | System (not in pip) | See [Section 4](#4-install-java-required-for-spark--lesson-2); macOS: `brew install openjdk@17` |
| **Spark Kafka connector** | `config/pipeline.yaml` → `spark_packages` | Used automatically by `make bronze` / `./scripts/run_bronze.sh` |
| **Kafka (broker)** | Aiven only (no local Docker) | Configure `.env` with Aiven credentials; see [docs/AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md). |

**Recommended: use the Makefile** (from project root): `make install` → configure `.env` (Aiven) → `make wait-kafka` → `make topics-create` → in terminal 1: `make bronze` → in terminal 2: `make produce`. See [Section 8.0](#80-first-time-run-step-by-step).

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone / Fork and Open Project](#2-clone--fork-and-open-project)
3. [Install Python Dependencies](#3-install-python-dependencies)
4. [Install Java (Required for Spark / Lesson 2+)](#4-install-java-required-for-spark--lesson-2)
5. [Configure the Pipeline](#5-configure-the-pipeline)
6. [Verify Setup (No Kafka Needed)](#6-verify-setup-no-kafka-needed)
7. [Run Lesson 1 — Data Contract & Config](#7-run-lesson-1--data-contract--config)
8. [Run Lesson 2 — Bronze Ingestion (Kafka Required)](#8-run-lesson-2--bronze-ingestion-kafka-required)
   - [8.0 Run with Makefile (recommended)](#80-run-with-makefile-recommended)
   - [8.1 Set up Kafka locally](#81-set-up-kafka-locally-required-for-lesson-2)
9. [Coming Later: Lessons 3–9](#9-coming-later-lessons-39)
10. [Environment Variables Reference](#10-environment-variables-reference)
11. [Troubleshooting](#11-troubleshooting)
12. [Live hosting & persistent Kafka (future scope)](#12-live-hosting--persistent-kafka-future-scope)

---

## 1. Prerequisites

| Requirement | Used for | How to check |
|-------------|----------|--------------|
| **Python 3.9+** | All lessons; config loader, schemas, checks | `python3 --version` |
| **pip** | Installing Python packages | `pip3 --version` |
| **Java 11 or 17** | Lesson 2+ (PySpark / Bronze, Silver, Gold jobs) | `java -version` |
| **Kafka** (optional for Lesson 1) | Lesson 2: Bronze reads from Kafka topic `orders` | Have Kafka running and topic created |
| **Git** | Clone/fork | `git --version` |

- **Lesson 1 only:** Python + pip + PyYAML. No Java or Kafka.
- **Lesson 2 (Bronze) full run:** Python + Java + **Kafka** (topic `orders`). You cannot run the Bronze job without Kafka; see Section 8.1 to set it up.

---

## 2. Clone / Fork and Open Project

**If you forked on GitHub:**

1. On GitHub, click **Fork** on the repo.
2. Clone your fork (replace `YOUR_USERNAME` with your GitHub username):

   ```bash
   git clone https://github.com/YOUR_USERNAME/realtime-order-medallion.git
   cd realtime-order-medallion
   ```

**If you cloned someone else’s repo:**

```bash
git clone https://github.com/toretto17/hotel-order-realtime-medallion.git
cd hotel-order-realtime-medallion
```

**Important:** All commands below assume you are in the **project root** (the folder that contains `config/`, `streaming/`, `docs/`, `README.md`).

---

## 3. Install Python Dependencies

All Python dependencies are in **`requirements.txt`** (single file). From the project root:

```bash
pip3 install -r requirements.txt
```

Or run the setup script (installs deps + checks Java):

```bash
./scripts/setup.sh
```

Or minimal for Lesson 1 only:

```bash
pip3 install pyyaml
```

This installs (among others): `pyspark`, `pyyaml`, `confluent-kafka`, `psycopg2-binary`, `pytest`.

---

## 4. Install Java (Required for Spark / Lesson 2+)

PySpark needs a Java Runtime (JVM). Without it, Lesson 2 check and Bronze job will fail. Follow these steps in order: **install** → **configure (PATH + JAVA_HOME)** → **reload shell** → **verify**.

### 4.1 Install the JDK

**macOS (Homebrew):**

```bash
brew install openjdk@17
```

**Windows:**  
Download and install [Eclipse Temurin (Adoptium)](https://adoptium.net/) — Java 17. Note the install directory (e.g. `C:\Program Files\Eclipse Adoptium\jdk-17`).

**Linux (e.g. Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install openjdk-17-jdk
```

**Linux (RHEL/CentOS/Fedora):**

```bash
sudo dnf install java-17-openjdk-devel
```

### 4.2 Configure PATH and JAVA_HOME

After installing, the shell must find `java` and PySpark needs `JAVA_HOME` set. Add these to your shell config (`~/.zshrc` or `~/.bashrc` on macOS/Linux; System Properties → Environment Variables on Windows), then **reload** the shell (see 4.3).

**macOS (Homebrew, openjdk@17):**  
Homebrew installs openjdk@17 as “keg-only”, so it is not added to PATH automatically. Add both PATH and JAVA_HOME:

```bash
# Add to ~/.zshrc (or ~/.bash_profile)
echo 'export PATH="/opt/homebrew/opt/openjdk@17/bin:$PATH"' >> ~/.zshrc
echo 'export JAVA_HOME="/opt/homebrew/opt/openjdk@17"' >> ~/.zshrc
```

On **Intel Mac** the path is usually `/usr/local/opt/openjdk@17`:

```bash
echo 'export PATH="/usr/local/opt/openjdk@17/bin:$PATH"' >> ~/.zshrc
echo 'export JAVA_HOME="/usr/local/opt/openjdk@17"' >> ~/.zshrc
```

**Linux (Ubuntu/Debian):**

```bash
echo 'export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"' >> ~/.bashrc
echo 'export PATH="$JAVA_HOME/bin:$PATH"' >> ~/.bashrc
```

(On ARM use `java-17-openjdk-arm64` if that is the path under `/usr/lib/jvm/`.)

**Windows (PowerShell, one-time per session):**

```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
```

Or set `JAVA_HOME` and add `%JAVA_HOME%\bin` to PATH via System Properties → Environment Variables (permanent).

### 4.3 Reload your shell

So the new PATH and JAVA_HOME are active in the current terminal:

**macOS / Linux (zsh):**

```bash
source ~/.zshrc
```

**macOS / Linux (bash):**

```bash
source ~/.bashrc
```

### 4.4 Verify Java

Run:

```bash
java -version
echo $JAVA_HOME
```

You should see Java 17 (or 11) and `JAVA_HOME` printed. On Windows use `echo %JAVA_HOME%` in cmd or `echo $env:JAVA_HOME` in PowerShell.

### 4.5 Optional (macOS only): system Java wrappers

If you want the system “Java” app to use this JDK, you can run the symlink that Homebrew suggests (optional; not required for PySpark):

```bash
sudo ln -sfn /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk
```

Then `export JAVA_HOME=$(/usr/libexec/java_home 2>/dev/null)` will also work. The PATH and JAVA_HOME steps in 4.2 are enough for this project.

**Summary (any platform):** Install JDK 11 or 17 → set `JAVA_HOME` and add the JDK `bin` directory to `PATH` → reload shell → run `java -version` and `echo $JAVA_HOME` to confirm. PySpark will then start correctly for Lesson 2.

---

## 5. Configure the Pipeline

All pipeline settings are in **`config/pipeline.yaml`**. You do **not** need to edit the file for local runs if you use environment variables.

### 5.1 What the config file contains

- **Kafka:** bootstrap servers, topic names, consumer group, starting offsets.
- **Streaming:** trigger interval, watermark, max offsets per trigger, fail on data loss.
- **Paths:** base path, checkpoint paths, Bronze/Silver/Gold table paths.
- **Postgres (optional):** JDBC URL, sink table, batch size.

Any value like `"${VAR:-default}"` is replaced at runtime: if env `VAR` is set, that value is used; otherwise `default`.

### 5.2 Set environment variables (required for Kafka)

This project uses **Aiven Kafka only** (no local Docker Kafka). Copy `.env.example` to `.env` and fill in your Aiven Kafka credentials:

- **KAFKA_BOOTSTRAP_SERVERS** — from Aiven Console → your Kafka service → Connection information
- **KAFKA_SECURITY_PROTOCOL** — `SSL` (client certificate; use when Aiven SASL tab is disabled)
- **KAFKA_SSL_CA_LOCATION**, **KAFKA_SSL_CERT_LOCATION**, **KAFKA_SSL_KEY_LOCATION** — paths to `ca.pem`, `service.cert`, `service.key` (download from Aiven)

See [docs/AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md) for step-by-step. Optional: `BASE_PATH` (default `/tmp/medallion`), `KAFKA_TOPIC` (default `orders`), `POSTGRES_JDBC_URL` if you use the Postgres sink.

---

## 6. Verify Setup (No Kafka Needed)

Run these from the **project root** to confirm config and (if Java is installed) Spark.

**Lesson 1 check (config + schema):**

```bash
python3 -m streaming.lesson1_check
```

Expected: “Lesson 1 check passed” and config + sample order parsed.

**Lesson 2 check (config + Spark; no Kafka):**

```bash
python3 -m streaming.lesson2_check
```

Expected: Kafka/paths printed; “Spark session: OK” if Java is installed. If Java is missing, you’ll see “Spark session: skipped (Java not found)” and instructions to install Java; config part still passes.

---

## 7. Run Lesson 1 — Data Contract & Config

**Goal:** Confirm that the order event schema and pipeline config load correctly. No Kafka or Spark job runs.

**Steps:**

1. From project root:
   ```bash
   python3 -m streaming.lesson1_check
   ```
2. You should see:
   - Config loaded (Kafka bootstrap, topic, base path).
   - A sample order event parsed (order_id, order_timestamp, items, total_amount).
   - “Lesson 1 check passed.”

**If it fails:** Ensure `pyyaml` is installed (`pip3 install pyyaml`) and you’re in the project root so `streaming.config_loader` and `streaming.schemas` can be imported.

---

## 8. Run Lesson 2 — Bronze Ingestion (Kafka Required)

**Goal:** Read from Kafka topic `orders` and write raw events to Bronze storage (Parquet) with metadata and checkpoint. You need **Kafka running and the topic `orders` created** — the Bronze job cannot run without it.

---

### 8.0 First-time run (step by step)

**You already ran `make install`** and **configured `.env` with Aiven Kafka** (see [AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md)). Do the following in order. All commands are from the **project root**.

| Step | Where | Command | What it does |
|------|--------|---------|--------------|
| **1** | Same terminal | `make wait-kafka` | Waits until Aiven Kafka is reachable. |
| **2** | Same terminal | `make topics-create` | Creates the `orders` topic on Aiven. |
| **3** | **Terminal 1** (keep it open) | `make bronze` | Runs the Bronze streaming job; leave it running. |
| **4** | **Terminal 2** (new terminal, same project root) | `make produce` | Sends one test order to Aiven Kafka; Bronze will pick it up. |

**Copy-paste order (same terminal for 1–3):**

```bash
make kafka-up
make wait-kafka
make topics-create
```

Then **open a new terminal**, `cd` to the project root, and run:

```bash
make bronze
```

Leave that running. In **another terminal** (third one, or the first one after step 3), from project root:

```bash
make produce
```

- **Steps 1–3:** Run one after the other in the same terminal.  
- **Step 4:** Run in Terminal 1 and leave it running (you’ll see Spark logs).  
- **Step 5:** Run in Terminal 2 (or the first terminal); it sends one event and exits.

(Optional: **`make run`** does wait-kafka + topics-create, then prompts you to run `make bronze` and `make produce` or `make web` in two terminals.)

---

### 8.0b Makefile reference

- **One-time:** `make install`; configure `.env` with Aiven (see [AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md)).
- **Prepare Aiven:** `make wait-kafka` → `make topics-create`. Or `make run` to do both.
- **Run pipeline:** Terminal 1: `make bronze` (leave running). Terminal 2: `make produce` or `make web`.
- **Help:** `make help`

**Restart from scratch (remove all Bronze, Silver, Gold data and checkpoints):**  
Stop any running Bronze/Silver jobs (Ctrl+C). Then run **`make clean-data`**. This deletes everything under `$BASE_PATH` (bronze, silver, gold, checkpoints). After that, run **`make wait-kafka`** → **`make topics-create`** → **`make bronze`** (T1) → **`make produce-orders N=100`** (or 500, 1000) in another terminal.

**Clean only one layer (e.g. fix Gold without touching Silver):**  
- **`make clean-gold`** — Remove only Gold tables. Then run **`make gold`** again to recompute aggregations from existing Silver data.  
- **`make clean-silver`** — Remove only Silver data + Silver checkpoints; then re-run Silver (and then Gold).  
- **`make clean-bronze`** — Remove only Bronze data + Bronze checkpoint; then re-run Bronze (and Silver, Gold as needed).

---

### 8.0c Produce many orders at once (100, 500, 1000)

To populate Bronze → Silver → Gold with many records in one shot:

1. **Bronze must be running** (Kafka up, topic created, `make bronze` in one terminal).
2. In another terminal: **`make produce-orders N=100`** (or `N=500`, `N=1000`). Default is 10 if you omit `N`.
3. Each order gets a unique `order_id`, random restaurant/customer, and **random selection from a food list** (30 items) with **quantity 1–10** and **random unit price 2–30** per line. Orders are spread over 14 days so Gold daily_sales has multiple dates (e.g. 20 one day, 50 another).

So: one command creates 100 (or 500, 1000) orders with varied combinations; no manual list needed.

**Order ID continuity:** The producer saves the last used order index under `$BASE_PATH/.produce_orders_last_id`. So if you run **`make produce-orders N=100`** today (order_id 1–100), then **tomorrow** run **`make produce-orders N=100`** again, the new orders will be **ord-00000101 .. ord-00000200** (starts from 101). After **`make clean-data`**, that state file is removed so the next produce starts from 1 again. To force start from 1 without full clean: **`make produce-orders-reset N=100`**.

---

### 8.0d Start everything again (full restart: clean all → Bronze → records → Silver → Gold)

Use this when you want to **clean all Bronze, Silver, and Gold** and run the full pipeline again from scratch.

| Step | Where | Command |
|------|--------|---------|
| 1 | One terminal | **`make clean-data`** — Stop Bronze/Silver first (Ctrl+C) if running. Removes all layer data, checkpoints, and order-index state (next produce starts from 1). |
| 2 | Same terminal | **`make wait-kafka`** → **`make topics-create`** |
| 3 | **Terminal 1** (leave open) | **`make bronze`** |
| 4 | **Terminal 2** | **`make produce-orders N=100`** — Creates 100 orders in Bronze. Wait ~1 min for Bronze to write. |
| 5 | Terminal 2 or 3 | **`TRIGGER_AVAILABLE_NOW=1 make silver`** — One micro-batch: reads Bronze, writes Silver. |
| 6 | Same terminal | **`make gold`** — Reads Silver, writes Gold aggregations. |
| 7 | Optional | **`python3 scripts/read_gold.py`** — Inspect Gold tables. |

**Copy-paste (run 1–2 in one terminal, then 3 in Terminal 1, 4–6 in another):**

```bash
make clean-data
make wait-kafka
make topics-create
# Then in Terminal 1: make bronze
# In Terminal 2: make produce-orders N=100
# After Bronze has data: TRIGGER_AVAILABLE_NOW=1 make silver
# Then: make gold
```

**Next day (without clean-data):** Run **`make produce-orders N=100`** again (with Bronze running) → new orders get IDs 101–200. Run Silver and Gold again to include them.

---

### 8.0e Hotel ordering website (localhost)

A web UI lets you place orders from a menu; each order is sent to the **same Kafka topic** (`orders`) that Bronze consumes. No sign-in/sign-up. After you submit an order you see a thank-you message and status; you can click **Order again** to place another. Only **new** records are processed incrementally by Bronze and Silver (same pipeline as `make produce-orders`).

**Run the website:**

| Step | Where | Command |
|------|--------|---------|
| 1 | Terminal 1 | **`make wait-kafka`**, **`make topics-create`**, then **`make bronze`** — leave running so it consumes orders from the website (and from `make produce` / `make produce-orders` if you use those too) |
| 3 | Terminal 2 | **`make web`** — starts Flask at **http://127.0.0.1:5000** |
| 4 | Browser | Open **http://127.0.0.1:5000**, add items (quantity), click **Place order** |
| 5 | After orders | Run **`TRIGGER_AVAILABLE_NOW=1 make silver`** then **`make gold`** to process new records into Silver and Gold (incremental: only new data) |

**Flow:** Website → Kafka topic `orders` → Bronze (streaming) → Silver (when you run it) → Gold (when you run it). Each order gets a unique `order_id` (e.g. `web-abc123...`). Bronze processes **only** the records that arrive on the topic (website orders, script orders, or both). Silver and Gold process incrementally when you run them (new Bronze/Silver data only).

**Install:** `pip install flask` (or `make install`; Flask is in `requirements.txt`).

**How to know a record came from the website (vs script):**  
Website orders use **`order_id`** starting with **`web-`** (e.g. `web-a1b2c3d4e5f6`) and **`customer_id`** = **`guest-web`**. Script orders use `order_id` like `ord-00000001` and `customer_id` like `C1`, `C2`. So in Silver or Bronze you can filter by `order_id LIKE 'web-%'` or `customer_id = 'guest-web'` to see only website orders.

**Restaurant for website orders:** All orders placed on the website use a **fixed** **`restaurant_id`** (default **`R1`** — the hotel’s restaurant). It is **not** random. Override with env **`HOTEL_RESTAURANT_ID`** (e.g. `R2`) if you have multiple venues.

**Read only website orders:**  
Run **`python3 scripts/read_web_orders.py`** (default: Silver). It shows only rows where `order_id` starts with `web-`. Use **`python3 scripts/read_web_orders.py bronze`** to see raw Bronze records for website orders, or **`python3 scripts/read_web_orders.py gold`** to see Gold tables (website orders contribute to the same aggregates; use customer_360 filtered by `guest-web` to see that customer’s row).

---

### 8.1 Set up Aiven Kafka (required for Lesson 2)

This project uses **Aiven Kafka only** (no local Docker Kafka). Follow:

- **[docs/AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md)** — Create an Aiven account, Kafka service, download certificates, and configure `.env`.

After `.env` is configured, run **`make wait-kafka`** and **`make topics-create`**, then **`make bronze`** and **`make produce`** or **`make web`**.

### 8.2 Set environment

Use `.env` with Aiven Kafka credentials (see [AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md)). Example: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL=SSL`, cert paths, `BASE_PATH=/tmp/medallion`.

### 8.3 Run Bronze job (streaming; runs until you stop it)

Spark does **not** include the Kafka data source by default. The Kafka connector package is defined in **`config/pipeline.yaml`** under `spark_packages`. Easiest: use the run script (reads config and passes `--packages`):

```bash
./scripts/run_bronze.sh
```

Or run spark-submit yourself (use the same package string as in `config/pipeline.yaml`):

```bash
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2 streaming/bronze_orders.py
```

(If your Spark is **3.x**, set `spark_packages` in `config/pipeline.yaml` to `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0` and match the version to your install.)

The job will read from Kafka, add columns `_ingestion_ts`, `_source`, `_partition`, `_offset`, `_ingestion_date`, and write Parquet under `$BASE_PATH/bronze/orders` with checkpoint under `$BASE_PATH/checkpoints/bronze_orders`. Stop with Ctrl+C.

### 8.4 Run Bronze job once (one micro-batch, then exit)

```bash
TRIGGER_AVAILABLE_NOW=1 ./scripts/run_bronze.sh
```

Use this to test without leaving the job running.

### 8.5 Produce test events (optional)

Send JSON order events to the `orders` topic (e.g. with `kafka-console-producer` or a small Python script using `confluent_kafka`). Schema must match the order event format in `streaming/schemas/order_events.py` (order_id, order_timestamp, restaurant_id, customer_id, order_type, items, total_amount, payment_method, order_status).

### 8.6 Where to see the processed order (Bronze output)

After the Bronze job has processed messages, data is written as **Parquet** under:

- **Path:** `$BASE_PATH/bronze/orders` (default: `/tmp/medallion/bronze/orders`)
- **Partitioning:** by `_ingestion_date` (date when the job ingested the row), e.g. `_ingestion_date=2026-03-04/`

**List files (from project root, with default BASE_PATH):**

```bash
ls -la /tmp/medallion/bronze/orders/
# You should see one folder per day, e.g. _ingestion_date=2026-03-04
ls -la /tmp/medallion/bronze/orders/_ingestion_date=*/
# Parquet part files will be inside
```

**Read the data (Python + PySpark or pandas):**

```bash
# With PySpark (from project root)
python3 -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName('read_bronze').getOrCreate()
df = spark.read.parquet('/tmp/medallion/bronze/orders')
df.show(truncate=False)
df.printSchema()
"
```

Each row has: `value` (raw JSON string of the order), `_ingestion_ts`, `_source`, `_partition`, `_offset`, `_topic`, `_ingestion_date`. The `value` column is the exact JSON that was sent to Kafka.

### 8.6b Run Silver (Lesson 3 — after Bronze has data)

Silver reads from Bronze Parquet, parses JSON, deduplicates by `order_id` with a watermark, and writes to Silver (fact_orders and fact_order_items). **No Kafka required** for Silver; it reads the files Bronze wrote.

1. Ensure Bronze has run and written data (e.g. you ran `make bronze` and `make produce` and see data under `$BASE_PATH/bronze/orders`).
2. From project root: **`make silver`** (or `./scripts/run_silver.sh`). Leave it running, or run once with **`TRIGGER_AVAILABLE_NOW=1 make silver`**.
3. Silver output: `$BASE_PATH/silver/orders` (fact_orders) and `$BASE_PATH/silver/order_items` (fact_order_items). Checkpoints: `$BASE_PATH/checkpoints/silver_orders` and `silver_orders_order_items`.

**What is TRIGGER_AVAILABLE_NOW=1?**  
When you set this env var, the Silver job uses Spark’s **`trigger(availableNow=True)`**: it processes **all data currently available** from the Bronze path in one or more micro-batches, then **exits** (instead of running forever with a periodic trigger). So you get a “run once, process what’s there, then stop” behavior. Without it, **`make silver`** runs continuously and processes new Bronze files as they appear.

**Why does Silver read only “incremental” data?**  
Silver’s **checkpoint** (under `$BASE_PATH/checkpoints/silver_orders`) stores which Bronze files (or offsets) have already been processed. On each run, Spark reads only **new** Bronze data that arrived after the last checkpoint. So the first time you run Silver it processes all existing Bronze data; the next times it processes only **new** Bronze files (incremental). The trigger (availableNow vs periodic) does not change that — it only controls whether the job exits after processing or keeps running.

**Re-process ALL Bronze data in Silver (full refresh):**  
To make Silver re-read **all** Bronze data from scratch (e.g. after a schema fix or backfill), clear Silver’s state so Spark doesn’t think anything was processed yet:

1. **`make clean-silver`** — Removes Silver output and **Silver checkpoints**. (Bronze data is unchanged.)
2. Run **`make silver`** or **`TRIGGER_AVAILABLE_NOW=1 make silver`** again. Silver will read from the **beginning** of the Bronze path and process every file.

So: **incremental** = default (checkpoint remembers progress). **Full refresh** = **`make clean-silver`** then run Silver again.

### 8.6c Where to see Silver output (check results)

After the Silver job has processed Bronze data, Parquet is written to:

- **fact_orders:** `$BASE_PATH/silver/orders` (default: `/tmp/medallion/silver/orders`)
- **fact_order_items:** `$BASE_PATH/silver/order_items` (default: `/tmp/medallion/silver/order_items`)

**List files (default BASE_PATH):**

```bash
ls -la /tmp/medallion/silver/orders/
ls -la /tmp/medallion/silver/order_items/
```

**Read and print Silver data (PySpark, from project root):**

```bash
# fact_orders (one row per order, deduplicated by order_id)
python3 -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName('read_silver').getOrCreate()
df = spark.read.parquet('/tmp/medallion/silver/orders')
df.show(truncate=False)
df.printSchema()
"

# fact_order_items (one row per line item)
python3 -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName('read_silver_items').getOrCreate()
df = spark.read.parquet('/tmp/medallion/silver/order_items')
df.show(truncate=False)
df.printSchema()
"
```

**fact_orders columns:** `order_id`, `order_timestamp`, `restaurant_id`, `customer_id`, `order_type`, `total_amount`, `payment_method`, `order_status`, `_ingestion_ts`, `_partition`, `_offset`.  
**fact_order_items columns:** `order_id`, `order_timestamp`, `item_id`, `item_name`, `category`, `quantity`, `unit_price`, `subtotal`.

### 8.6d Run Gold (Lesson 4 — after Silver has data)

Gold is a **batch** job: it reads Silver Parquet, runs three aggregations (daily_sales, customer_360, restaurant_metrics), and writes to Gold paths. **No Kafka required.**

**Important:** Gold does **not** GROUP BY order_id. It aggregates: many Silver rows become fewer Gold rows. Example: 100 orders in Silver → daily_sales has one row per (order_date, restaurant_id); customer_360 has one row per customer; restaurant_metrics has one row per restaurant. So you get far fewer rows in Gold (e.g. 4–20) than in Silver (100). That is the point of aggregation.

1. Ensure Silver has written data. To get **multiple orders** (so Gold has meaningful aggregates), use the record creator: **`make produce-orders`** or **`make produce-orders N=25`** (with Bronze running) to send many orders with varied order_id, customer_id, restaurant_id. Then run Silver, then Gold.
2. From project root: **`make gold`** or **`./scripts/run_gold.sh`**.
3. Gold output: `$BASE_PATH/gold/daily_sales`, `$BASE_PATH/gold/customer_360`, `$BASE_PATH/gold/restaurant_metrics`.

### 8.6e Where to see Gold output (check results)

After `make gold`, Parquet is written to:

- **daily_sales:** `$BASE_PATH/gold/daily_sales` (partitioned by `order_date`) — order count, revenue, payment/order-type breakdown, discount/festival metrics per day per restaurant.
- **customer_360:** `$BASE_PATH/gold/customer_360` — one row per customer: order count, total spend, first/last order date, preferred payment, favorite restaurant.
- **restaurant_metrics:** `$BASE_PATH/gold/restaurant_metrics` — one row per restaurant: order count, revenue, unique customers, total items sold, top category.

**List and read (default BASE_PATH):**

```bash
ls -la /tmp/medallion/gold/daily_sales/
ls -la /tmp/medallion/gold/customer_360/
ls -la /tmp/medallion/gold/restaurant_metrics/
```

```bash
python3 -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName('read_gold').getOrCreate()
for name, path in [('daily_sales', '/tmp/medallion/gold/daily_sales'), ('customer_360', '/tmp/medallion/gold/customer_360'), ('restaurant_metrics', '/tmp/medallion/gold/restaurant_metrics')]:
    print('---', name, '---')
    spark.read.parquet(path).show(20, truncate=False)
"
```

### 8.7 How to stop the system (when not processing orders)

- **Stop the Bronze (or Silver) streaming job:** In the terminal where `make bronze` or `make silver` is running, press **Ctrl+C**. The Spark job will shut down; you may see a Py4J error in the log — that is normal (see §11 troubleshooting). The checkpoint is saved; you can start Bronze again later and it will resume from the last committed offset.
- **No local Kafka to stop.** Aiven Kafka runs in the cloud; you only stop your own jobs (Bronze, Silver, Web) with Ctrl+C in each terminal.
- **Start again:** Run **`make wait-kafka`** → **`make topics-create`** (if needed) → **`make bronze`** (T1) → **`make produce`** or **`make web`** (T2).

---

## 9. Coming Later: Lessons 3–9

When these are implemented, follow the same pattern: **config from `config/pipeline.yaml` + env overrides**, then run the corresponding script or SQL.

| Lesson | What you’ll run (when available) | Prerequisites |
|--------|-----------------------------------|---------------|
| **3 — Silver** | `make silver` or `./scripts/run_silver.sh` | Bronze data written; reads Parquet from Bronze path |
| **4 — Gold** | `make gold` or `./scripts/run_gold.sh` (reads Silver, runs `sql/gold_*.sql`, writes Gold Parquet) | Silver tables populated |
| **5 — Late data** | No separate script; behavior in Silver/streaming config (watermark, allowedLateness) | Same as Silver |
| **6 — DLQ** | Silver job will write invalid rows to DLQ (topic or table); monitor DLQ depth | Silver job; DLQ topic or path in config |
| **7 — Exactly-once** | No new script; checkpoint + idempotent Silver/Gold writes | Same as Silver/Gold |
| **8 — Orchestration** | Run scripts (Bronze, Silver, Gold) via Airflow DAG or cron; CI runs tests | All jobs; Airflow or scheduler |
| **9 — Observability** | Metrics and alerts (e.g. Prometheus/Grafana); production checklist | All above |

After each lesson is added, this section will be updated with the exact command and any new env vars.

---

## 10. Environment Variables Reference

| Variable | Default (in pipeline.yaml) | Purpose |
|----------|----------------------------|--------|
| `BASE_PATH` | `s3://your-bucket/data` | Root for all paths: checkpoints, bronze, silver, gold. Set to e.g. `/tmp/medallion` for local. |
| `KAFKA_BOOTSTRAP_SERVERS` | (required in `.env`) | Aiven Kafka bootstrap URI for Bronze. |
| `TRIGGER_AVAILABLE_NOW` | (none) | Set to `1` or `true` to run Bronze (or Silver) once and exit (one micro-batch). |
| `POSTGRES_JDBC_URL` | (none) | Optional; for writing Gold or serving layer to Postgres. |
| `JAVA_HOME` | (system) | Required for PySpark; point to JDK 11 or 17. |

Config file path is fixed at `config/pipeline.yaml` relative to project root; override only if you use a different config path in code.

---

## 11. Troubleshooting

### “No module named 'yaml'” or “No module named 'streaming'”

- Run from the **project root** (directory containing `streaming/` and `config/`).
- Install deps: `pip3 install -r requirements.txt` (or at least `pip3 install pyyaml` for Lesson 1).

### “Unable to locate a Java Runtime” / “JAVA_GATEWAY_EXITED”

- PySpark needs Java. Install JDK 11 or 17 (see [Section 4](#4-install-java-required-for-spark--lesson-2)).
- Set `JAVA_HOME` and run `java -version` to confirm.

### “Config not found” or wrong paths

- Ensure `config/pipeline.yaml` exists in the project root.
- If you use a custom config path, the code must be updated to load it; by default only `config/pipeline.yaml` is used.
- Set `BASE_PATH` so that checkpoint and output paths are valid (e.g. local dir or S3/ABFS).

### “Failed to find data source: kafka”

- Spark does not bundle the Kafka connector. Add it with `--packages` when submitting:
  - **Spark 4.x (Scala 2.13):** `spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2 streaming/bronze_orders.py`
  - **Spark 3.x (Scala 2.12):** `spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 streaming/bronze_orders.py` (match the version to your Spark).
- The first run may download the package from Maven Central; ensure you have network access.

### Py4JError when stopping Bronze (Ctrl+C)

Stopping the Spark job with Ctrl+C is normal; the JVM shuts down while Python is still calling `awaitTermination()`, so Py4J may report "Error while sending or receiving". The job and checkpoint are still consistent. No fix needed.

### Bronze job: “Connection refused” or Kafka errors

- Kafka must be running and reachable at `KAFKA_BOOTSTRAP_SERVERS`.
- Topic `orders` must exist.
- For Docker Kafka, use host `localhost` and port `9092` (or the mapped port).

### Bronze job: no data written

- Confirm that messages are being produced to the `orders` topic in the expected JSON format.
- Use `starting_offsets: "earliest"` in config (or env) to read from the beginning of the topic.
- Check that `BASE_PATH` is writable (e.g. `/tmp/medallion` or an S3 path you can write to).

### Checkpoint errors (e.g. path not found or permission denied)

- Ensure `BASE_PATH` is set and the checkpoint directory is writable.
- Do not delete the checkpoint directory if you want to resume the same query; use a new path for a fresh start.

### Bronze: “Partition orders-0 offset was changed from 104 to 1” / STREAM_FAILED

### Too many Spark logs (Silver / Gold very verbose)

Silver and Gold use Spark; by default Spark prints **INFO** logs for every task, stage, and file read, so you see hundreds of lines for a few orders. **This is normal**, not an error. The jobs already set the log level to **WARN** so you get less output. If you need to debug, set `spark.sparkContext.setLogLevel("INFO")` in the Silver or Gold script. The "HashAggregateExec: codegened fast hashmap does not support this aggregate" message is an informational fallback, not a failure. **Why so many tasks?** Silver and Bronze write many small Parquet files (one or more per run/trigger). Gold reads all of them, so Spark creates many tasks. With few orders but many past runs, you get many files and thus many log lines. For a cleaner slate, use **`make clean-silver`** and **`make clean-gold`** then re-run.

This happens when **the Bronze checkpoint** (e.g. “last processed offset 104”) **does not match Kafka** (e.g. topic now starts at offset 1).

- **With Aiven Kafka:** Offsets normally persist. If you recreated the topic or the service was reset, run **`make clean-bronze`**, then **`make bronze`** to start fresh.
- We keep **`fail_on_data_loss: true`** in config so that if offsets ever reset, the job fails and you investigate instead of silently skipping records.

---

## 12. Live hosting (Aiven + Render)

This project uses **Aiven Kafka** (persistent). When you stop only your jobs (Bronze/Silver/Web), Kafka keeps running in the cloud. When you start Bronze again, it **resumes from the last checkpoint** — no "offset changed" error.

**Free setup:** [FREE_HOSTING.md](FREE_HOSTING.md) — Aiven (Kafka) + Render (website). Configure `.env` (or Render env vars) with Aiven credentials; keep **`fail_on_data_loss: true`** in config.

---

## Quick Command Summary

| Action | Command (from project root) |
|--------|-----------------------------|
| Configure Kafka | Copy `.env.example` to `.env`; add Aiven credentials. See [AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md) |
| Install Python deps | `pip3 install -r requirements.txt` or `make install` |
| Wait + create topic | `make wait-kafka` then `make topics-create` (or `make run`) |
| Lesson 1 check | `python3 -m streaming.lesson1_check` |
| Lesson 2 check | `python3 -m streaming.lesson2_check` |
| Bronze (streaming) | `make bronze` (loads .env; uses config/pipeline.yaml) |
| Bronze (one batch) | `TRIGGER_AVAILABLE_NOW=1 make bronze` |

---

**Doc version:** Covers Lesson 1 and Lesson 2 (Bronze). Lessons 3–9 will be added here as they are implemented.
