#!/usr/bin/env python3
"""
Create Kafka topic 'orders' (idempotent). Uses confluent_kafka AdminClient.
Run from project root. Respects KAFKA_BOOTSTRAP_SERVERS (default localhost:9092).
"""
import os
import sys

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "orders")
PARTITIONS = int(os.environ.get("KAFKA_TOPIC_PARTITIONS", "1"))
REPLICATION = int(os.environ.get("KAFKA_TOPIC_REPLICATION", "1"))


def main():
    try:
        from confluent_kafka.admin import AdminClient
    except ImportError:
        print("Install confluent_kafka: pip install confluent-kafka", file=sys.stderr)
        sys.exit(1)

    client = AdminClient({"bootstrap.servers": BOOTSTRAP})
    from confluent_kafka.admin import NewTopic

    new_topic = NewTopic(TOPIC, num_partitions=PARTITIONS, replication_factor=REPLICATION)
    fs = client.create_topics([new_topic])
    for topic, f in fs.items():
        try:
            f.result()
            print(f"Topic '{topic}' created (or already exists).")
        except Exception as e:
            if "already exists" in str(e).lower() or "TopicExistsException" in str(type(e).__name__):
                print(f"Topic '{topic}' already exists.")
            else:
                print(f"Failed to create topic '{topic}': {e}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
