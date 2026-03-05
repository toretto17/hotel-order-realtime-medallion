#!/usr/bin/env python3
"""
Produce one test order event to the Kafka 'orders' topic.
Run from host (not inside a container) so Kafka broker addresses work.
Loads .env from project root so Aiven is default when hosted.
Usage:
  python3 scripts/produce_test_order.py
  make produce
  (ensure .env has Aiven credentials)
"""
import json
import os
import sys

import kafka_producer_config

# Aiven Kafka only: .env required
kafka_producer_config.load_dotenv()

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
TOPIC = os.environ.get("KAFKA_TOPIC", "orders")
if not BOOTSTRAP:
    print("Error: KAFKA_BOOTSTRAP_SERVERS not set in .env. See docs/AIVEN_SETUP_STEP_BY_STEP.md", file=sys.stderr)
    sys.exit(1)

# Order ID matches website convention (web-*); bulk/single test use web-bulk-*
TEST_ORDER = {
    "order_id": "web-bulk-00000001",
    "order_timestamp": "2025-03-04T12:00:00Z",
    "restaurant_id": "R1",
    "customer_id": "C1",
    "order_type": "delivery",
    "items": [
        {
            "item_id": "I1",
            "name": "Burger",
            "category": "main",
            "quantity": 1,
            "unit_price": 10.0,
            "subtotal": 10.0,
        }
    ],
    "total_amount": 10.0,
    "payment_method": "card",
    "order_status": "completed",
}

def main():
    try:
        from confluent_kafka import Producer
    except ImportError:
        print("Install confluent_kafka: pip install confluent-kafka", file=sys.stderr)
        sys.exit(1)

    p = Producer(kafka_producer_config.build_producer_config())
    value = json.dumps(TEST_ORDER).encode("utf-8")

    def on_delivery(err, msg):
        if err:
            print(f"Delivery failed: {err}", file=sys.stderr)
        else:
            print(f"Produced to {msg.topic()} partition {msg.partition()} offset {msg.offset()}")

    p.produce(TOPIC, value=value, callback=on_delivery)
    p.flush(timeout=10)
    print("Done. Bronze job (if running) should pick up the message within ~1 trigger interval.")


if __name__ == "__main__":
    main()
