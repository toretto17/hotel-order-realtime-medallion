# Realtime Order Medallion — Aiven Kafka only (no local Docker Kafka)
# Use from project root. First time: make install. Configure .env with Aiven credentials (see docs/AIVEN_SETUP_STEP_BY_STEP.md).
# Then: make run (or make wait-kafka + make topics-create) → make bronze (T1), make produce or make web (T2) → make silver → make gold

.PHONY: install check clean clean-data clean-bronze clean-silver clean-gold wait-kafka topics-create bronze silver gold pipeline produce produce-orders produce-orders-reset web run stop test-kafka check-order postgres-schema postgres-backfill postgres-truncate vm-run login-ssh help

# Default target
help:
	@echo "Realtime Order Medallion — Aiven Kafka only"
	@echo ""
	@echo "First-time setup:"
	@echo "  1. make install       Install Python deps, check Java (run once)"
	@echo "  2. Configure .env    Copy .env.example to .env; fill Aiven Kafka credentials (see docs/AIVEN_SETUP_STEP_BY_STEP.md)"
	@echo ""
	@echo "Clean (restart or fix one layer):"
	@echo "  make clean            Same as clean-data (full restart)"
	@echo "  make clean-data       Remove all Bronze, Silver, Gold + checkpoints + producer state (next produce-orders → web-bulk-00000001)"
	@echo "  make clean-bronze     Remove only Bronze (+ checkpoint)"
	@echo "  make clean-silver     Remove only Silver (+ checkpoints)"
	@echo "  make clean-gold       Remove only Gold (then re-run make gold)"
	@echo ""
	@echo "Kafka (Aiven — .env required):"
	@echo "  make wait-kafka       Wait until Aiven Kafka is reachable"
	@echo "  make topics-create    Create topic 'orders' on Aiven"
	@echo "  make test-kafka       Test connection (produce + consume one message)"
	@echo ""
	@echo "Pipeline:"
	@echo "  make bronze           Run Bronze streaming job (Spark; keep running in one terminal)"
	@echo "  make silver           Run Silver job (reads Bronze Parquet; writes Silver)"
	@echo "  make gold             Run Gold batch (reads Silver; writes daily_sales, customer_360, restaurant_metrics)"
	@echo "  make pipeline         Run full pipeline once: Bronze → Silver → Gold (micro-batch each; no long-running jobs)"
	@echo "  ./run                 Same as make pipeline (one command from repo root; use this on VM after SSH)"
	@echo "  make vm-run           SSH into VM and run pipeline (one command from Mac; set VM_HOST and SSH_KEY in .env)"
	@echo "  make login-ssh        SSH into VM and open a shell in the repo (hotel-order-realtime-medallion); then run ./run or ./scripts/cron_run.sh"
	@echo "  make produce          Produce one test order to Aiven Kafka"
	@echo "  make produce-orders [N=100]  Produce N orders; order_id continues from last run"
	@echo "  make produce-orders-reset [N=100]  Produce N orders starting from order_id 1"
	@echo "  make check-order [ID=<order_id>]   Trace an order through Silver + Gold layers"
	@echo "  make web              Run hotel ordering website (localhost:5000); orders → Aiven Kafka → Bronze"
	@echo ""
	@echo "Postgres (optional — Bronze/Silver/Gold sync):"
	@echo "  make postgres-schema     Create medallion schema + tables (run once; set POSTGRES_JDBC_URL in .env). See docs/POSTGRES_SETUP.md"
	@echo "  make postgres-backfill   Backfill Postgres from existing Parquet (use if Bronze Postgres is empty but Parquet has data). Optional: postgres-backfill ALL=1 for full backfill"
	@echo "  make postgres-truncate   Truncate all medallion tables (full reset). Use with make clean-data to start completely fresh. Requires: make postgres-truncate YES=1"
	@echo ""
	@echo "Checks:"
	@echo "  make check            Run lesson1 + lesson2 checks (config, schema, Spark)"
	@echo ""
	@echo "Run flow (step by step):"
	@echo "  1. make install"
	@echo "  2. Configure .env with Aiven (bootstrap, SSL certs; see .env.example)"
	@echo "  3. make wait-kafka     # wait until Aiven is ready (e.g. after power-on)"
	@echo "  4. make topics-create"
	@echo "  5. make bronze        # Terminal 1 — leave running"
	@echo "  6. make produce       # Terminal 2 — or make web to use the website"
	@echo "  7. make silver        # after Bronze has data"
	@echo "  8. make gold          # after Silver has data"
	@echo ""
	@echo "One-shot pipeline (Bronze → Silver → Gold in one command):"
	@echo "  make pipeline        # or ./run from repo root (VM: ssh in, cd repo, ./run)"
	@echo "  make vm-run          # from Mac: SSH to VM and run pipeline (one command; set VM_HOST, SSH_KEY in .env)"
	@echo "  make login-ssh       # from Mac: SSH to VM, land in repo dir; then ./run or crontab -l etc."
	@echo "  Cron on VM: use scripts/cron_run.sh in crontab; pipeline then runs every 10–15 min automatically"
	@echo ""
	@echo "Quick start (after .env is set):"
	@echo "  make run              Same as: make wait-kafka + make topics-create; then run make bronze (T1) and make produce or make web (T2)"
	@echo ""
	@echo "Stop: Ctrl+C in each terminal running bronze, silver, or web. No local Kafka to stop."

install:
	@chmod +x scripts/setup.sh scripts/run_bronze.sh scripts/run_pipeline.sh scripts/cron_run.sh scripts/ssh_run_pipeline.sh scripts/ssh_login.sh run 2>/dev/null || true
	./scripts/setup.sh

check:
	@echo "=== Lesson 1 check (config + schema) ==="
	python3 -m streaming.lesson1_check
	@echo ""
	@echo "=== Lesson 2 check (config + Spark) ==="
	python3 -m streaming.lesson2_check

# Wait until Aiven Kafka is reachable. Requires .env with KAFKA_BOOTSTRAP_SERVERS and SSL certs.
wait-kafka:
	python3 scripts/wait_for_kafka.py

# Create topic 'orders' on Aiven. Run after wait-kafka.
topics-create:
	python3 scripts/create_topic.py

# Test Aiven Kafka connection (produce + consume one message). Requires .env.
test-kafka:
	python3 scripts/test_kafka_connection.py

# Run Bronze Spark job (reads from Aiven Kafka, writes Parquet). Requires .env and topic 'orders'.
bronze:
	@chmod +x scripts/run_bronze.sh 2>/dev/null || true
	./scripts/run_bronze.sh

# Run Silver job (reads Bronze Parquet, dedup, watermark; writes Silver). No Kafka.
silver:
	@chmod +x scripts/run_silver.sh 2>/dev/null || true
	./scripts/run_silver.sh

# Run Gold batch (reads Silver Parquet; writes daily_sales, customer_360, restaurant_metrics). No Kafka.
gold:
	@chmod +x scripts/run_gold.sh 2>/dev/null || true
	./scripts/run_gold.sh

# Run full pipeline once: Bronze (micro-batch) → Silver (micro-batch) → Gold. Requires .env (Aiven Kafka).
pipeline:
	@chmod +x scripts/run_pipeline.sh 2>/dev/null || true
	./scripts/run_pipeline.sh

# From Mac: SSH to VM and run pipeline (one command). Set VM_HOST and SSH_KEY in .env.
vm-run:
	@chmod +x scripts/ssh_run_pipeline.sh 2>/dev/null || true
	./scripts/ssh_run_pipeline.sh

# SSH into VM and open a shell in the repo (hotel-order-realtime-medallion). Set VM_HOST and SSH_KEY in .env.
login-ssh:
	@chmod +x scripts/ssh_login.sh 2>/dev/null || true
	./scripts/ssh_login.sh

# Produce one test order to Aiven Kafka.
produce:
	python3 scripts/produce_test_order.py

# Produce N orders (default 10). Order IDs continue from last run.
produce-orders:
	python3 scripts/produce_orders.py $(or $(N),10)

# Produce N orders starting from 1 (ignore saved state).
produce-orders-reset:
	python3 scripts/produce_orders.py $(or $(N),10) --reset

# Trace a single order through Silver and Gold layers.
# Usage: make check-order ID=web-a054ff91a6e5
check-order:
	python3 scripts/check_order.py $(or $(ID),web-a054ff91a6e5)

# Create Postgres schema and tables (run once). Requires POSTGRES_JDBC_URL in .env. See docs/POSTGRES_SETUP.md.
postgres-schema:
	python3 scripts/run_postgres_schema.py

# Backfill Postgres from existing Parquet. Use when Bronze Postgres is empty but Parquet has data (e.g. data ingested before Postgres was set up). Default: Bronze only. ALL=1 → Bronze + Silver + Gold.
postgres-backfill:
	python3 scripts/backfill_postgres_from_parquet.py $(if $(ALL),--all,--bronze)

# Truncate all medallion tables (full reset). Run after make clean-data to start completely fresh. Requires YES=1 to skip confirmation.
postgres-truncate:
	python3 scripts/truncate_postgres_medallion.py $(if $(YES),--yes,)

# Run hotel ordering website. Orders go to Aiven Kafka; run Bronze in another terminal to process.
web:
	cd web && python3 app.py

# Prepare Aiven: wait + create topic. Then run make bronze (T1) and make produce or make web (T2).
run: wait-kafka
	@$(MAKE) topics-create
	@echo ""
	@echo "=== Aiven Kafka ready. Next: ==="
	@echo "  Terminal 1: make bronze   (leave running)"
	@echo "  Terminal 2: make produce  or  make web"
	@echo "  Then: make silver  →  make gold"
	@echo ""

# No local Kafka; just remind to stop Bronze/Silver/Web if running.
stop:
	@echo "No local Kafka. Stop Bronze, Silver, or Web with Ctrl+C in each terminal."

# Full restart: remove all layer data + checkpoints + producer state.
clean: clean-data
clean-data:
	python3 scripts/clean_medallion_data.py

# Clean only one layer.
clean-bronze:
	python3 scripts/clean_medallion_data.py --bronze-only
clean-silver:
	python3 scripts/clean_medallion_data.py --silver-only
clean-gold:
	python3 scripts/clean_medallion_data.py --gold-only
