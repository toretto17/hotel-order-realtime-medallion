#!/usr/bin/env bash
# Run full pipeline once: Bronze (micro-batch) → Silver (micro-batch) → Gold (batch).
# Use from project root. Requires .env with Aiven Kafka credentials (same as make bronze).
#   ./scripts/run_pipeline.sh
#   make pipeline

set -e
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Error: .env not found. Required for Bronze (Aiven Kafka)."
  echo "  Copy .env.example to .env and add Aiven credentials (see docs/AIVEN_SETUP_STEP_BY_STEP.md)"
  exit 1
fi
set -a
source .env
set +a

export BASE_PATH="${BASE_PATH:-/tmp/medallion}"
export TRIGGER_AVAILABLE_NOW=1

# Signal files written by Bronze and Silver after each run
BRONZE_SIGNAL="$BASE_PATH/checkpoints/bronze_orders/.last_run_rows"
SILVER_SIGNAL="$BASE_PATH/checkpoints/silver_orders/.last_run_rows"

_read_signal() {
  local f="$1"
  if [ -f "$f" ]; then
    val=$(cat "$f" | tr -d '[:space:]')
    echo "${val:-0}"
  else
    echo "0"
  fi
}

_banner_no_data() {
  local stage="$1"
  local reason="$2"
  echo ""
  echo "  ┌─────────────────────────────────────────────────────────────┐"
  printf "  │  %-61s│\n" "$stage: nothing to process."
  printf "  │  %-61s│\n" "$reason"
  echo "  │                                                             │"
  echo "  │  To add new orders:                                         │"
  echo "  │    From website : place an order at your hosted URL         │"
  echo "  │    Quick test   : make produce-orders N=10                  │"
  echo "  │                                                             │"
  echo "  │  Then re-run    : make pipeline                             │"
  echo "  └─────────────────────────────────────────────────────────────┘"
  echo ""
}

echo "=== Pipeline: Bronze → Silver → Gold (one run each) ==="
echo "BASE_PATH=$BASE_PATH"
echo ""

# ── 1/3 Bronze ───────────────────────────────────────────────────────────────
echo "--- 1/3 Bronze (consume available Kafka messages, then exit) ---"
./scripts/run_bronze.sh
echo ""

BRONZE_ROWS=$(_read_signal "$BRONZE_SIGNAL")
if [ "$BRONZE_ROWS" = "0" ]; then
  echo "  Bronze: no new Kafka messages. Silver will still run to retry any unfinished work."
  echo ""
fi

# ── 2/3 Silver ───────────────────────────────────────────────────────────────
# Silver ALWAYS runs — it owns its own checkpoint and knows what Bronze data
# it has already processed. If a previous Silver run failed mid-batch (e.g.
# fact_order_items crashed), Silver will automatically re-process that batch
# here. Skipping Silver based on Bronze = 0 would cause permanent data loss
# for any batch that Bronze wrote but Silver didn't fully commit.
echo "--- 2/3 Silver (process new Bronze data, then exit) ---"
./scripts/run_silver.sh
echo ""

SILVER_ROWS=$(_read_signal "$SILVER_SIGNAL")
if [ "$SILVER_ROWS" = "0" ]; then
  _banner_no_data "Silver" "All Bronze data already fully processed in a previous run."
  echo "=== Pipeline complete (Silver already up to date, Gold skipped). ==="
  exit 0
fi

# ── 3/3 Gold ─────────────────────────────────────────────────────────────────
echo "--- 3/3 Gold (batch: aggregate Silver → Gold tables) ---"
./scripts/run_gold.sh
echo ""

echo "=== Pipeline done. ==="
