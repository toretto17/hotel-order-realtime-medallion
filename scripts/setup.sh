#!/usr/bin/env bash
# One-time setup: install Python deps, check Java, print how to run Bronze.
# Run from project root:  ./scripts/setup.sh   or   bash scripts/setup.sh

set -e
cd "$(dirname "$0")/.."

echo "=== Realtime Order Medallion — setup ==="
echo ""

echo "1. Installing Python dependencies (requirements.txt)..."
pip3 install -r requirements.txt
echo "   Done."
echo ""

echo "2. Checking Java (required for Spark/Bronze)..."
if command -v java &>/dev/null; then
  java -version
  echo "   Java OK."
else
  echo "   Java not found. Install it:"
  echo "   macOS:  brew install openjdk@17"
  echo "   Then:  export JAVA_HOME=\$(/usr/libexec/java_home 2>/dev/null)"
  echo "   See docs/SETUP_AND_RUN.md"
fi
echo ""

echo "3. Kafka: run the following (from project root) to start Kafka and create topic:"
echo "   make kafka-up"
echo "   make wait-kafka"
echo "   make topics-create"
echo ""
echo "=== Next (first-time run, in order) ==="
echo "   Step 1–3 (this terminal):  make kafka-up   then   make wait-kafka   then   make topics-create"
echo "   Step 4 (Terminal 1):        make bronze     (leave running)"
echo "   Step 5 (Terminal 2):        make produce    (sends one test order)"
echo ""
echo "   See docs/SETUP_AND_RUN.md Section 8.0 for the full step-by-step."
echo ""
