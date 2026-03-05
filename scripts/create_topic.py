#!/usr/bin/env python3
"""
Create Kafka topic 'orders' (idempotent). Uses confluent_kafka AdminClient.
Run from project root. Respects KAFKA_BOOTSTRAP_SERVERS; supports SSL/client cert when using Aiven.
"""
import os
import sys
from pathlib import Path

# Load .env from project root so SSL/cert vars are set when using Aiven
_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _REPO_ROOT / ".env"
if _ENV_FILE.is_file():
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "orders")
PARTITIONS = int(os.environ.get("KAFKA_TOPIC_PARTITIONS", "1"))
REPLICATION = int(os.environ.get("KAFKA_TOPIC_REPLICATION", "1"))


def _admin_config():
    """Same security config as wait_for_kafka / test_kafka_connection for Aiven SSL."""
    cfg = {"bootstrap.servers": BOOTSTRAP}
    security = os.environ.get("KAFKA_SECURITY_PROTOCOL", "").strip().upper()
    if security in ("SSL", "SASL_SSL", "SASL_PLAINTEXT"):
        cfg["security.protocol"] = security
    if security in ("SSL", "SASL_SSL"):
        ca = os.environ.get("KAFKA_SSL_CA_LOCATION") or os.environ.get("KAFKA_SSL_CAFILE")
        if not ca and os.environ.get("KAFKA_SSL_CA_CERT"):
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(os.environ["KAFKA_SSL_CA_CERT"])
                ca = f.name
        if ca:
            cfg["ssl.ca.location"] = ca
        cert = os.environ.get("KAFKA_SSL_CERT_LOCATION") or os.environ.get("KAFKA_SSL_CERTFILE")
        key = os.environ.get("KAFKA_SSL_KEY_LOCATION") or os.environ.get("KAFKA_SSL_KEYFILE")
        if cert:
            cfg["ssl.certificate.location"] = cert
        if key:
            cfg["ssl.key.location"] = key
        if os.environ.get("KAFKA_SSL_KEY_PASSWORD"):
            cfg["ssl.key.password"] = os.environ["KAFKA_SSL_KEY_PASSWORD"]
    if security in ("SASL_SSL", "SASL_PLAINTEXT"):
        mechanism = os.environ.get("KAFKA_SASL_MECHANISM", "PLAIN").strip()
        cfg["sasl.mechanism"] = mechanism
        u = os.environ.get("KAFKA_SASL_USERNAME") or os.environ.get("KAFKA_SASL_USER")
        p = os.environ.get("KAFKA_SASL_PASSWORD")
        if u and p:
            cfg["sasl.username"] = u
            cfg["sasl.password"] = p
    return cfg


def main():
    try:
        from confluent_kafka.admin import AdminClient
    except ImportError:
        print("Install confluent_kafka: pip install confluent-kafka", file=sys.stderr)
        sys.exit(1)

    client = AdminClient(_admin_config())
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
