#!/usr/bin/env python3
"""
Produce one test order event to the Kafka 'orders' topic.
Run from host (not inside a container) so Kafka broker addresses work.
Usage:
  python3 scripts/produce_test_order.py
  KAFKA_BOOTSTRAP_SERVERS=localhost:39092 python3 scripts/produce_test_order.py
"""
import json
import os
import sys

# Bootstrap servers: from env or default (match config/pipeline.yaml; use 29092 for Confluent)
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "orders")

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

    p = Producer({"bootstrap.servers": BOOTSTRAP})
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
