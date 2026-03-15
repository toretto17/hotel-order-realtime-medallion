#!/usr/bin/env bash
# From your Mac (or local machine): SSH into the VM and run the pipeline in one command.
# Requires in .env: VM_HOST (e.g. 80.225.236.237), and SSH_KEY (path to private key).
# Usage: make vm-run   or   ./scripts/ssh_run_pipeline.sh
# Reads only VM_* and SSH_KEY from .env (no full source) so paths with ( ) or spaces work.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ -f .env ]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
    if [[ "$line" =~ ^(VM_HOST|VM_REPO_DIR|VM_SSH_USER|SSH_KEY)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      value="${value%\"}"; value="${value#\"}"
      value="${value%\'}"; value="${value#\'}"
      eval "export ${key}=\"\${value}\""
    fi
  done < .env
fi

VM_HOST="${VM_HOST:?Add VM_HOST=your-vm-ip to .env (e.g. 80.225.236.237)}"
VM_REPO_DIR="${VM_REPO_DIR:-/home/ubuntu/hotel-order-realtime-medallion}"
SSH_USER="${VM_SSH_USER:-ubuntu}"

SSH_OPTS=(-o ConnectTimeout=15)
[ -n "${SSH_KEY}" ] && SSH_OPTS+=(-i "$SSH_KEY")

echo "Connecting to $SSH_USER@$VM_HOST and running pipeline..."
# On VM: set JAVA_HOME + Spark on PATH (non-interactive SSH has no .bashrc), then run pipeline
exec ssh "${SSH_OPTS[@]}" "$SSH_USER@$VM_HOST" "cd $VM_REPO_DIR && for j in /usr/lib/jvm/java-17-openjdk-amd64 /usr/lib/jvm/java-17-openjdk-arm64; do [ -d \"\$j\" ] && export JAVA_HOME=\"\$j\" && break; done && export PATH=\"\$JAVA_HOME/bin:\$PATH\" && for s in \$HOME/spark-3.5.0-bin-hadoop3 \$HOME/spark \$HOME/spark-*; do [ -x \"\$s/bin/spark-submit\" ] 2>/dev/null && export PATH=\"\$s/bin:\$PATH\" && break; done && export BASE_PATH=\${BASE_PATH:-/home/ubuntu/medallion_data} && [ -f .env ] && set -a && . ./.env 2>/dev/null && set +a && ./scripts/run_pipeline.sh"
