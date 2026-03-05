#!/usr/bin/env python3
"""
Test Aiven Kafka connection (produce + consume one message). Requires .env with Aiven credentials.
Run from project root:  make test-kafka
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Project root = parent of scripts/
_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)


def _load_dotenv(path: Path) -> None:
    """Load .env into os.environ (key=value, skip comments and empty lines)."""
    if not path.is_file():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v


_load_dotenv(_REPO_ROOT / ".env")

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
TOPIC = os.environ.get("KAFKA_TOPIC", "orders")
if not BOOTSTRAP:
    print("Error: KAFKA_BOOTSTRAP_SERVERS not set in .env. See docs/AIVEN_SETUP_STEP_BY_STEP.md", file=sys.stderr)
    sys.exit(1)


def _build_producer_config() -> dict:
    """Same logic as web/app.py _kafka_producer_config()."""
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
        key_pass = os.environ.get("KAFKA_SSL_KEY_PASSWORD")
        if key_pass:
            cfg["ssl.key.password"] = key_pass
    if security in ("SASL_SSL", "SASL_PLAINTEXT"):
        mechanism = os.environ.get("KAFKA_SASL_MECHANISM", "PLAIN").strip()
        cfg["sasl.mechanism"] = mechanism
        username = os.environ.get("KAFKA_SASL_USERNAME") or os.environ.get("KAFKA_SASL_USER")
        password = os.environ.get("KAFKA_SASL_PASSWORD")
        if username and password:
            cfg["sasl.username"] = username
            cfg["sasl.password"] = password
    return cfg


def _build_consumer_config() -> dict:
    """Consumer needs same security config as producer."""
    cfg = _build_producer_config().copy()
    cfg["group.id"] = "test-kafka-connection"
    cfg["auto.offset.reset"] = "earliest"
    return cfg


def main() -> int:
    print("Aiven Kafka connection test (using .env)")
    print(f"  KAFKA_BOOTSTRAP_SERVERS = {BOOTSTRAP}")
    print(f"  KAFKA_TOPIC = {TOPIC}")
    security = os.environ.get("KAFKA_SECURITY_PROTOCOL", "").strip() or "(none)"
    print(f"  KAFKA_SECURITY_PROTOCOL = {security}")
    if security == "SASL_SSL" and not os.environ.get("KAFKA_SASL_PASSWORD"):
        print("  (Hint: If Aiven SASL tab is disabled, use client cert only: set KAFKA_SECURITY_PROTOCOL=SSL and cert paths.)")

    try:
        from confluent_kafka import Producer, Consumer
    except ImportError:
        print("ERROR: confluent_kafka not installed. Run: pip install confluent-kafka")
        return 1

    producer_cfg = _build_producer_config()
    test_payload = {"order_id": "test-connection-1", "test": True, "items": []}
    value = json.dumps(test_payload).encode("utf-8")

    # 1) Produce
    print("\n1. Producing one test message...")
    producer = Producer(producer_cfg)
    err_holder = [None]

    def on_delivery(err, msg):
        err_holder[0] = err

    producer.produce(TOPIC, value=value, callback=on_delivery)
    try:
        producer.flush(timeout=15)
        # Poll so delivery callback runs (failures like "bad certificate" are reported there)
        for _ in range(20):
            producer.poll(0.5)
            if err_holder[0] is not None:
                break
    except Exception as e:
        err_str = str(e).lower()
        if "bad certificate" in err_str or "ssl" in err_str:
            print("   FAILED (SSL/cert). If SASL tab is disabled in Aiven, use client cert only:")
            print("   In .env set: KAFKA_SECURITY_PROTOCOL=SSL and the 3 cert paths; leave SASL vars empty.")
        else:
            print(f"   FAILED: {e}")
        return 1
    if err_holder[0]:
        err_str = str(err_holder[0]).lower()
        if "bad certificate" in err_str or "ssl" in err_str:
            print("   FAILED (SSL/cert). If SASL tab is disabled in Aiven, use client cert only:")
            print("   In .env set: KAFKA_SECURITY_PROTOCOL=SSL and the 3 cert paths; leave SASL vars empty.")
        else:
            print(f"   FAILED: {err_holder[0]}")
        return 1
    print("   OK — message produced.")

    # 2) Consume (read back one message)
    print("2. Consuming one message (to verify read path)...")
    consumer_cfg = _build_consumer_config()
    consumer = Consumer(consumer_cfg)
    consumer.subscribe([TOPIC])
    msg = None
    for _ in range(30):  # poll up to ~15s
        msg = consumer.poll(timeout=0.5)
        if msg is not None and not msg.error():
            break
        if msg is not None and msg.error():
            consumer.close()
            print(f"   FAILED: {msg.error()}")
            return 1
    consumer.close()
    if msg is None:
        print("   WARNING: No message received in 15s (produce succeeded; broker/connection OK).")
        return 0
    print(f"   OK — read back {len(msg.value())} bytes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
