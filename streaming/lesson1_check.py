"""
Lesson 1 check: run this to verify schema + config are wired correctly.
  From repo root: python -m streaming.lesson1_check
  Or: python streaming/lesson1_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repo root is on path when run as script
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from streaming.config_loader import load_config, get_kafka_config, get_paths_config
from streaming.schemas.order_events import OrderEvent, ORDER_EVENT_JSON_SCHEMA


def main() -> None:
    print("=== Lesson 1: Data contract & config ===\n")

    # 1. Config
    print("1. Loading config from config/pipeline.yaml ...")
    config = load_config()
    kafka = get_kafka_config(config)
    paths = get_paths_config(config)
    print(f"   Kafka bootstrap: {kafka.get('bootstrap_servers')}")
    print(f"   Topic (orders):  {kafka.get('topic_orders')}")
    print(f"   Base path:       {paths.get('base')}")
    print("   OK.\n")

    # 2. Schema — parse a sample event
    sample = {
        "order_id": "ord-001",
        "order_timestamp": "2025-03-04T12:00:00Z",
        "restaurant_id": "R1",
        "customer_id": "C1",
        "order_type": "delivery",
        "items": [
            {
                "item_id": "I1",
                "name": "Burger",
                "category": "main",
                "quantity": 2,
                "unit_price": 10.5,
                "subtotal": 21.0,
            }
        ],
        "total_amount": 21.0,
        "payment_method": "card",
        "order_status": "completed",
    }
    print("2. Parsing sample order event (idempotency key = order_id) ...")
    event = OrderEvent.from_dict(sample)
    print(f"   order_id: {event.order_id}, order_timestamp: {event.order_timestamp}")
    print(f"   items: {len(event.items)}, total_amount: {event.total_amount}")
    print("   OK.\n")

    # 3. Round-trip
    print("3. Round-trip: event -> dict -> JSON ...")
    back = event.to_dict()
    assert back["order_id"] == sample["order_id"]
    print("   OK.\n")

    print("Lesson 1 check passed. Next: Lesson 2 — Bronze ingestion from Kafka.")


if __name__ == "__main__":
    main()
