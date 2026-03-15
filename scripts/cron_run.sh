#!/usr/bin/env bash
# Production: cron wrapper — sets JAVA_HOME, Spark on PATH, BASE_PATH, sources .env, runs pipeline.
# Use from crontab (every 10–15 min): */15 * * * * /home/ubuntu/hotel-order-realtime-medallion/scripts/cron_run.sh >> /home/ubuntu/pipeline.log 2>&1
# Replace path with your repo path on the VM.
set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# Cron has no login env; set Java (java-17-openjdk-amd64 or -arm64)
if [ -z "$JAVA_HOME" ]; then
  for d in /usr/lib/jvm/java-17-openjdk-amd64 /usr/lib/jvm/java-17-openjdk-arm64; do
    if [ -d "$d" ]; then JAVA_HOME="$d"; break; fi
  done
  [ -z "$JAVA_HOME" ] && { echo "JAVA_HOME not set and no java-17 found"; exit 1; }
fi
export PATH="$JAVA_HOME/bin:$PATH"

# Add Spark to PATH (cron does not source .bashrc)
for s in "$HOME/spark-3.5.0-bin-hadoop3" "$HOME/spark" "$HOME"/spark-*; do
  [ -x "$s/bin/spark-submit" ] 2>/dev/null && export PATH="$s/bin:$PATH" && break
done

export BASE_PATH="${BASE_PATH:-/home/ubuntu/medallion_data}"
[ -f .env ] && set -a && source .env 2>/dev/null && set +a
./scripts/run_pipeline.sh
