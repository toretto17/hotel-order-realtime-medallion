#!/usr/bin/env python3
"""
Wait until Kafka is reachable by listing topics (with retries).
Used by: make wait-kafka. Exit 0 when ready, non-zero on timeout.
"""
import os
import sys
import time

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
MAX_WAIT = int(os.environ.get("KAFKA_WAIT_SECONDS", "60"))
INTERVAL = 2


def main():
    try:
        from confluent_kafka.admin import AdminClient
    except ImportError:
        print("Install confluent_kafka: pip install confluent-kafka", file=sys.stderr)
        sys.exit(1)

    client = AdminClient({"bootstrap.servers": BOOTSTRAP})
    deadline = time.monotonic() + MAX_WAIT
    while time.monotonic() < deadline:
        try:
            metadata = client.list_topics(timeout=10)
            print(f"Kafka ready at {BOOTSTRAP}.")
            sys.exit(0)
        except Exception as e:
            print(f"Waiting for Kafka at {BOOTSTRAP}... ({e})")
            time.sleep(INTERVAL)
    print(f"Timeout: Kafka not reachable at {BOOTSTRAP} after {MAX_WAIT}s.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
