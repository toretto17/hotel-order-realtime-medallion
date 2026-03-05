#!/usr/bin/env python3
"""
Wait until Kafka is reachable by listing topics (with retries).
Used by: make wait-kafka. Exit 0 when ready, non-zero on timeout.
Supports SSL/client cert when KAFKA_SECURITY_PROTOCOL and cert paths are set (e.g. Aiven).
"""
import os
import sys
import time
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
MAX_WAIT = int(os.environ.get("KAFKA_WAIT_SECONDS", "60"))
INTERVAL = 2


def _admin_config():
    """Same security config as test_kafka_connection / web app for Aiven SSL."""
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
