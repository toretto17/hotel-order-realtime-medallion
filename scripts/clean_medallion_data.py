#!/usr/bin/env python3
"""
Remove Bronze, Silver, and/or Gold data (and their checkpoints) under BASE_PATH.
Use layer-specific clean when e.g. Gold is wrong — clean only Gold and re-run Gold job.

Usage:
  python3 scripts/clean_medallion_data.py                    # clean all layers + checkpoints
  python3 scripts/clean_medallion_data.py --gold-only       # only Gold (re-run make gold)
  python3 scripts/clean_medallion_data.py --silver-only      # only Silver + silver checkpoints
  python3 scripts/clean_medallion_data.py --bronze-only     # only Bronze + bronze checkpoint
  python3 scripts/clean_medallion_data.py --no-checkpoints  # all layer data, keep checkpoints
"""
import argparse
import os
import shutil
import sys

BASE_PATH = os.environ.get("BASE_PATH", "/tmp/medallion")

# Per-layer dirs (match config/pipeline.yaml)
BRONZE_DIRS = ["bronze/orders"]
BRONZE_CHECKPOINTS = ["checkpoints/bronze_orders"]

SILVER_DIRS = ["silver/orders", "silver/order_items"]
SILVER_CHECKPOINTS = ["checkpoints/silver_orders", "checkpoints/silver_orders_order_items"]

GOLD_DIRS = ["gold/daily_sales", "gold/customer_360", "gold/restaurant_metrics"]
# Gold has no streaming checkpoints (batch job)

# When doing full clean, also remove this so next produce_orders starts from order_id 1
ORDER_INDEX_STATE_FILE = ".produce_orders_last_id"


def main():
    parser = argparse.ArgumentParser(description="Clean Medallion data (all or one layer)")
    parser.add_argument("--no-checkpoints", action="store_true", help="When cleaning all: do not delete checkpoints")
    parser.add_argument("--bronze-only", action="store_true", help="Clean only Bronze data + bronze checkpoint")
    parser.add_argument("--silver-only", action="store_true", help="Clean only Silver data + silver checkpoints")
    parser.add_argument("--gold-only", action="store_true", help="Clean only Gold data (no checkpoint)")
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be removed")
    args = parser.parse_args()

    base = os.path.abspath(BASE_PATH)
    if not os.path.isdir(base):
        print(f"BASE_PATH {base} does not exist; nothing to clean.")
        return 0

    to_remove = []
    if args.bronze_only:
        to_remove = BRONZE_DIRS + BRONZE_CHECKPOINTS
    elif args.silver_only:
        to_remove = SILVER_DIRS + SILVER_CHECKPOINTS
    elif args.gold_only:
        to_remove = GOLD_DIRS
    else:
        to_remove = BRONZE_DIRS + SILVER_DIRS + GOLD_DIRS
        if not args.no_checkpoints:
            to_remove += BRONZE_CHECKPOINTS + SILVER_CHECKPOINTS

    removed = []
    for sub in to_remove:
        path = os.path.join(base, sub)
        if os.path.exists(path):
            if args.dry_run:
                print(f"Would remove: {path}")
                removed.append(path)
            else:
                shutil.rmtree(path, ignore_errors=True)
                print(f"Removed: {path}")
                removed.append(path)

    # Full clean only: remove order-index state file so next produce_orders starts from 1
    if not (args.bronze_only or args.silver_only or args.gold_only):
        state_path = os.path.join(base, ORDER_INDEX_STATE_FILE)
        if os.path.isfile(state_path):
            if args.dry_run:
                print(f"Would remove: {state_path}")
                removed.append(state_path)
            else:
                os.remove(state_path)
                print(f"Removed: {state_path} (next produce_orders will start from order_id 1)")
                removed.append(state_path)

    if not removed:
        print("No matching data or checkpoint dirs found under", base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
