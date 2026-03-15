#!/usr/bin/env bash
# SSH into the VM and open a shell in the repo directory (hotel-order-realtime-medallion).
# Requires in .env: VM_HOST, SSH_KEY. Optional: VM_REPO_DIR, VM_SSH_USER.
# Usage: make login-ssh
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

VM_HOST="${VM_HOST:?Add VM_HOST=your-vm-ip to .env}"
VM_REPO_DIR="${VM_REPO_DIR:-/home/ubuntu/hotel-order-realtime-medallion}"
SSH_USER="${VM_SSH_USER:-ubuntu}"

SSH_OPTS=(-o ConnectTimeout=15 -t)
[ -n "${SSH_KEY}" ] && SSH_OPTS+=(-i "$SSH_KEY")

echo "Connecting to $SSH_USER@$VM_HOST (repo: $VM_REPO_DIR)..."
exec ssh "${SSH_OPTS[@]}" "$SSH_USER@$VM_HOST" "cd $VM_REPO_DIR && exec bash -l"
