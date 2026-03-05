# Realtime Order Medallion — Aiven Kafka only (no local Docker Kafka)
# Use from project root. First time: make install. Configure .env with Aiven credentials (see docs/AIVEN_SETUP_STEP_BY_STEP.md).
# Then: make run (or make wait-kafka + make topics-create) → make bronze (T1), make produce or make web (T2) → make silver → make gold

.PHONY: install check clean clean-data clean-bronze clean-silver clean-gold wait-kafka topics-create bronze silver gold produce produce-orders produce-orders-reset web run stop test-kafka help

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
	@echo "  make produce          Produce one test order to Aiven Kafka"
	@echo "  make produce-orders [N=100]  Produce N orders; order_id continues from last run"
	@echo "  make produce-orders-reset [N=100]  Produce N orders starting from order_id 1"
	@echo "  make web              Run hotel ordering website (localhost:5000); orders → Aiven Kafka → Bronze"
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
	@echo "Quick start (after .env is set):"
	@echo "  make run              Same as: make wait-kafka + make topics-create; then run make bronze (T1) and make produce or make web (T2)"
	@echo ""
	@echo "Stop: Ctrl+C in each terminal running bronze, silver, or web. No local Kafka to stop."

install:
	@chmod +x scripts/setup.sh scripts/run_bronze.sh 2>/dev/null || true
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

# Produce one test order to Aiven Kafka.
produce:
	python3 scripts/produce_test_order.py

# Produce N orders (default 10). Order IDs continue from last run.
produce-orders:
	python3 scripts/produce_orders.py $(or $(N),10)

# Produce N orders starting from 1 (ignore saved state).
produce-orders-reset:
	python3 scripts/produce_orders.py $(or $(N),10) --reset

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
