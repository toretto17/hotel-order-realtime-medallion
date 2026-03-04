#!/usr/bin/env bash
# Run Silver job (reads Bronze Parquet, writes Silver fact_orders + fact_order_items).
# Use from project root. Bronze must have written data first.
#   ./scripts/run_silver.sh
#   TRIGGER_AVAILABLE_NOW=1 ./scripts/run_silver.sh  # one micro-batch then exit

set -e
cd "$(dirname "$0")/.."

export BASE_PATH="${BASE_PATH:-/tmp/medallion}"

echo "BASE_PATH=$BASE_PATH"
echo "Silver reads from \$BASE_PATH/bronze/orders, writes to \$BASE_PATH/silver/orders and silver/order_items"
exec spark-submit streaming/silver_fact_orders.py
