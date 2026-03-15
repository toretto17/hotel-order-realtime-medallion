#!/usr/bin/env bash
# Run this ON THE VM (e.g. after make login-ssh) to fix "Silver: no new Bronze data"
# when Bronze data exists under _ingestion_date=... (Spark file source ignores paths starting with _).
#
# Usage: cd ~/hotel-order-realtime-medallion && ./scripts/fix_silver_see_bronze_vm.sh

set -e
BASE="${BASE_PATH:-/home/ubuntu/medallion_data}"
BRONZE="$BASE/bronze/orders"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "=== 1. Pull latest code (Bronze partitions by ingestion_date, Silver sees it) ==="
git pull

echo ""
echo "=== 2. Rename existing Bronze partition so Silver can list it (_ → no underscore) ==="
if [ -d "$BRONZE/_ingestion_date=2026-03-15" ]; then
  mv "$BRONZE/_ingestion_date=2026-03-15" "$BRONZE/ingestion_date=2026-03-15"
  echo "  Renamed _ingestion_date=2026-03-15 → ingestion_date=2026-03-15"
else
  echo "  No _ingestion_date=2026-03-15 dir (already renamed or different date?). Listing Bronze:"
  ls -la "$BRONZE/" 2>/dev/null || true
fi

# Other possible dates
for d in "$BRONZE"/_ingestion_date=*; do
  [ -d "$d" ] || continue
  new="${d/_ingestion_date=/ingestion_date=}"
  if [ "$d" != "$new" ]; then
    mv "$d" "$new"
    echo "  Renamed $(basename "$d") → $(basename "$new")"
  fi
done

echo ""
echo "=== 3. Clear Silver checkpoint (it has stale _ingestion_date paths → 'file not found') ==="
for cp in "$BASE/checkpoints/silver_orders" "$BASE/checkpoints/silver_orders_order_items"; do
  if [ -d "$cp" ]; then
    rm -rf "$cp"
    echo "  Cleared $cp"
  fi
done

echo ""
echo "=== 4. Run pipeline (Silver will discover files at ingestion_date=... and process) ==="
export BASE_PATH="${BASE_PATH:-/home/ubuntu/medallion_data}"
[ -f .env ] && set -a && source .env 2>/dev/null && set +a
./scripts/run_pipeline.sh
