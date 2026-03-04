#!/usr/bin/env bash
# Run Bronze job with Kafka connector from config. Use from project root.
#   ./scripts/run_bronze.sh
#   TRIGGER_AVAILABLE_NOW=1 ./scripts/run_bronze.sh  # one micro-batch then exit

set -e
cd "$(dirname "$0")/.."

# PySpark/Spark require Java; fail fast with a clear message
if ! command -v java >/dev/null 2>&1; then
  echo "Error: Java not found. PySpark needs a JVM (Java 11 or 17)."
  echo "  macOS (Homebrew): brew install openjdk@17"
  echo "  Then add to ~/.zshrc: export PATH=\"/opt/homebrew/opt/openjdk@17/bin:\$PATH\""
  echo "  And: export JAVA_HOME=\"/opt/homebrew/opt/openjdk@17\""
  echo "  Then: source ~/.zshrc  and run 'make bronze' again."
  echo "  See docs/SETUP_AND_RUN.md §4 for full instructions."
  exit 1
fi

# Spark Kafka package from single source of truth (config/pipeline.yaml)
PACKAGES=$(python3 -c "
import yaml
with open('config/pipeline.yaml') as f:
    c = yaml.safe_load(f)
print(c.get('spark_packages', ''))
")
if [ -z "$PACKAGES" ]; then
  echo "Error: spark_packages not set in config/pipeline.yaml"
  exit 1
fi

export BASE_PATH="${BASE_PATH:-/tmp/medallion}"
export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"

echo "BASE_PATH=$BASE_PATH KAFKA_BOOTSTRAP_SERVERS=$KAFKA_BOOTSTRAP_SERVERS"
echo "Spark packages: $PACKAGES"
exec spark-submit --packages "$PACKAGES" streaming/bronze_orders.py
