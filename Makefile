# Realtime Order Medallion — single entry point for run flow
# Use from project root. First time: make install
# Then: make kafka-up → make topics-create → make bronze (terminal 1), make produce (terminal 2)

.PHONY: install check clean clean-data clean-bronze clean-silver clean-gold kafka-up kafka-down kafka-logs wait-kafka topics-create bronze silver gold produce produce-orders produce-orders-reset web run stop test-kafka help

# Default target
help:
	@echo "Realtime Order Medallion — targets"
	@echo ""
	@echo "First-time setup:"
	@echo "  make install       Install Python deps, check Java (run once)"
	@echo ""
	@echo "Clean (restart or fix one layer):"
	@echo "  make clean         Same as clean-data (full restart)"
	@echo "  make clean-data    Remove all Bronze, Silver, Gold + checkpoints + producer state (next produce-orders → web-bulk-00000001)"
	@echo "  make clean-bronze  Remove only Bronze (+ checkpoint)"
	@echo "  make clean-silver  Remove only Silver (+ checkpoints)"
	@echo "  make clean-gold    Remove only Gold (then re-run make gold for correct aggregation)"
	@echo ""
	@echo "Kafka (use project Docker Compose; port 9092):"
	@echo "  make kafka-up      Start Kafka broker (docker-compose up -d)"
	@echo "  make kafka-down    Stop Kafka"
	@echo "  make stop          Stop all (Kafka + reminder to Ctrl+C Bronze/Silver/Web terminals)"
	@echo "  make kafka-logs    Follow Kafka logs"
	@echo "  make wait-kafka    Wait until Kafka is reachable (after kafka-up)"
	@echo "  make topics-create Create topic 'orders' (run after wait-kafka or when using external Kafka)"
	@echo ""
	@echo "Pipeline:"
	@echo "  make bronze        Run Bronze streaming job (Spark; keep running in one terminal)"
	@echo "  make silver        Run Silver job (reads Bronze Parquet; dedup + watermark; writes Silver)"
	@echo "  make gold          Run Gold batch (reads Silver Parquet; writes daily_sales, customer_360, restaurant_metrics)"
	@echo "  make produce       Produce one test order to Kafka (run in another terminal)"
	@echo "  make produce-orders [N=100] Produce N orders; order_id continues from last run (101, 102...)"
	@echo "  make produce-orders-reset [N=100] Produce N orders starting from order_id 1"
	@echo "  make web               Run hotel ordering website (localhost:5000); orders → Kafka → Bronze"
	@echo ""
	@echo "Checks:"
	@echo "  make check         Run lesson1 + lesson2 checks (config, schema, Spark)"
	@echo "  make test-kafka    Test Kafka connection (loads .env; use after configuring Aiven/local Kafka)"
	@echo ""
	@echo "Full run flow (step by step):"
	@echo "  1. make install"
	@echo "  2. make kafka-up"
	@echo "  3. make wait-kafka    # optional; wait until broker is ready"
	@echo "  4. make topics-create"
	@echo "  5. make bronze       # terminal 1 — leave running"
	@echo "  6. make produce     # terminal 2 — send test event"
	@echo "  7. make silver      # terminal 3 (optional) — reads Bronze, writes Silver (after Bronze has data)"
	@echo "  8. make gold        # after Silver has data — batch aggregations to Gold"
	@echo ""
	@echo "After make clean (or make stop) — start again:"
	@echo "  Aiven Kafka:  Do NOT run make kafka-up. source .env then make topics-create make bronze (T1) make produce or make web (T2) make silver make gold"
	@echo "  Local Kafka:  make kafka-up  make wait-kafka  make topics-create  make bronze (T1)  make produce (T2)  make silver  make gold"
	@echo ""
	@echo "If you use Confluent Kafka (e.g. port 29092), set before make:"
	@echo "  export KAFKA_BOOTSTRAP_SERVERS=localhost:29092"
	@echo "  Then: make topics-create  make bronze  make produce"

install:
	@chmod +x scripts/setup.sh scripts/run_bronze.sh 2>/dev/null || true
	./scripts/setup.sh

check:
	@echo "=== Lesson 1 check (config + schema) ==="
	python3 -m streaming.lesson1_check
	@echo ""
	@echo "=== Lesson 2 check (config + Spark) ==="
	python3 -m streaming.lesson2_check

# Kafka via project docker-compose (port 9092). For Confluent, skip kafka-up and set KAFKA_BOOTSTRAP_SERVERS.
kafka-up:
	docker compose up -d
	@echo "Kafka starting. Run 'make wait-kafka' then 'make topics-create'."

kafka-down:
	docker compose down

# Stop all services before logging out. Stops Kafka; you must Ctrl+C in each terminal running bronze, silver, or web.
stop: kafka-down
	@echo "Kafka stopped. If you had Bronze, Silver, or Web running in other terminals, stop them with Ctrl+C there."

kafka-logs:
	docker compose logs -f

# Wait until Kafka is reachable (uses KAFKA_BOOTSTRAP_SERVERS; default localhost:9092)
wait-kafka:
	python3 scripts/wait_for_kafka.py

# Create topic 'orders'. Set KAFKA_BOOTSTRAP_SERVERS if not using project Kafka (e.g. localhost:29092).
topics-create:
	python3 scripts/create_topic.py

# Test Kafka connection using .env (produce + consume one message). Use for Aiven or local Kafka.
test-kafka:
	python3 scripts/test_kafka_connection.py

# Run Bronze Spark job (reads from Kafka, writes Parquet). Requires Kafka up + topic created.
bronze:
	@chmod +x scripts/run_bronze.sh 2>/dev/null || true
	./scripts/run_bronze.sh

# Run Silver job (reads Bronze Parquet, dedup by order_id, watermark, writes Silver fact_orders + fact_order_items).
# Run after Bronze has written data. No Kafka required.
silver:
	@chmod +x scripts/run_silver.sh 2>/dev/null || true
	./scripts/run_silver.sh

# Run Gold batch job (reads Silver Parquet, runs Gold SQL, writes daily_sales, customer_360, restaurant_metrics).
# Run after Silver has data. No Kafka required.
gold:
	@chmod +x scripts/run_gold.sh 2>/dev/null || true
	./scripts/run_gold.sh

# Produce one test order. Run in a second terminal while Bronze is running.
produce:
	python3 scripts/produce_test_order.py

# Produce multiple orders: random food items, qty 1-10. Order IDs continue from last run (e.g. 101-200).
# Usage: make produce-orders  (10)  or  make produce-orders N=100
# After make clean-data, next produce-orders starts from 1 again.
produce-orders:
	python3 scripts/produce_orders.py $(or $(N),10)

# Produce orders starting from 1 (ignore saved state). Use after cleaning only Silver/Gold.
produce-orders-reset:
	python3 scripts/produce_orders.py $(or $(N),10) --reset

# Run hotel ordering website (Flask). Orders go to Kafka; run Bronze in another terminal to process them.
web:
	cd web && python3 app.py

# Full restart: remove all layer data + checkpoints + producer state. Then follow "Start from clean" steps below.
clean: clean-data
clean-data:
	python3 scripts/clean_medallion_data.py

# Clean only one layer (e.g. fix Gold: make clean-gold then make gold)
clean-bronze:
	python3 scripts/clean_medallion_data.py --bronze-only
clean-silver:
	python3 scripts/clean_medallion_data.py --silver-only
clean-gold:
	python3 scripts/clean_medallion_data.py --gold-only

# Orchestrated run: start Kafka, wait, create topic, then print next steps (bronze + produce in two terminals)
run: kafka-up
	@echo "Waiting for Kafka to be ready..."
	@$(MAKE) wait-kafka
	@$(MAKE) topics-create
	@echo ""
	@echo "=== Kafka is up and topic 'orders' exists. Next: ==="
	@echo "  Terminal 1: make bronze   (leave running)"
	@echo "  Terminal 2: make produce (send test event)"
	@echo ""
