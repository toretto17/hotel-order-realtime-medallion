"""
Shared Kafka producer config from env. Aiven Kafka only.
Load .env from repo root then call build_producer_config() for confluent_kafka.Producer.
Requires KAFKA_BOOTSTRAP_SERVERS and SSL cert paths (see .env.example).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv() -> None:
    """Load .env from repo root into os.environ (no overwrite of existing vars)."""
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v


def build_producer_config() -> dict:
    """Build producer config dict from os.environ. Requires .env with Aiven Kafka (bootstrap + SSL)."""
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
    if not bootstrap:
        print(
            "Error: KAFKA_BOOTSTRAP_SERVERS not set. Copy .env.example to .env and add Aiven Kafka credentials.",
            file=sys.stderr,
        )
        print("  See docs/AIVEN_SETUP_STEP_BY_STEP.md", file=sys.stderr)
        sys.exit(1)
    cfg = {"bootstrap.servers": bootstrap}
    security = os.environ.get("KAFKA_SECURITY_PROTOCOL", "").strip().upper()
    if security in ("SSL", "SASL_SSL", "SASL_PLAINTEXT"):
        cfg["security.protocol"] = security
    if security in ("SSL", "SASL_SSL"):
        ca = os.environ.get("KAFKA_SSL_CA_LOCATION") or os.environ.get("KAFKA_SSL_CAFILE")
        if not ca and os.environ.get("KAFKA_SSL_CA_CERT"):
            content = os.environ["KAFKA_SSL_CA_CERT"].replace("\\n", "\n")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(content)
                ca = f.name
        if ca:
            cfg["ssl.ca.location"] = ca
        cert = os.environ.get("KAFKA_SSL_CERT_LOCATION") or os.environ.get("KAFKA_SSL_CERTFILE")
        key = os.environ.get("KAFKA_SSL_KEY_LOCATION") or os.environ.get("KAFKA_SSL_KEYFILE")
        if not cert and os.environ.get("KAFKA_SSL_CERT_CERT"):
            content = os.environ["KAFKA_SSL_CERT_CERT"].replace("\\n", "\n")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(content)
                cert = f.name
        if not key and os.environ.get("KAFKA_SSL_KEY_CERT"):
            content = os.environ["KAFKA_SSL_KEY_CERT"].replace("\\n", "\n")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(content)
                key = f.name
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
