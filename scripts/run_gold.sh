#!/usr/bin/env bash
# Run Gold batch job: reads Silver Parquet, runs Gold SQL aggregations, writes Gold Parquet.
# Use from project root. Silver must have data first (run Bronze + Silver, or at least have Silver paths).
#   ./scripts/run_gold.sh

set -e
cd "$(dirname "$0")/.."

export BASE_PATH="${BASE_PATH:-/tmp/medallion}"

echo "BASE_PATH=$BASE_PATH"
echo "Gold reads from \$BASE_PATH/silver/orders and silver/order_items, writes to \$BASE_PATH/gold/*"
exec spark-submit streaming/gold_batch.py
