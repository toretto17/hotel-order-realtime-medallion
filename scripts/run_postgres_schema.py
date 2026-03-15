#!/usr/bin/env python3
"""
Run the Medallion Postgres schema (scripts/sql/postgres_schema.sql) once.
Uses POSTGRES_JDBC_URL from .env, or builds from POSTGRES_HOST/PORT/DB/USER/PASSWORD.
Usage: from repo root, python scripts/run_postgres_schema.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load .env
env_file = REPO_ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v


def _jdbc_to_conn_params(jdbc_url: str) -> dict:
    """Parse JDBC URL into psycopg2-style connection params."""
    # jdbc:postgresql://host:port/dbname?user=u&password=p&ssl=true&sslmode=require
    m = re.match(r"jdbc:postgresql://([^/]+)/([^?]+)(?:\?(.*))?", jdbc_url.strip())
    if not m:
        raise ValueError("Invalid POSTGRES_JDBC_URL; expected jdbc:postgresql://host:port/db?user=...&password=...")
    host_port, dbname, query = m.group(1), m.group(2), (m.group(3) or "")
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    params = {"host": host, "port": port, "dbname": dbname}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "user":
                params["user"] = v
            elif k == "password":
                params["password"] = v
            elif k == "sslmode":
                params["sslmode"] = v
    if "sslmode" not in params and "ssl=true" in query.lower():
        params["sslmode"] = "require"
    return params


def main() -> None:
    jdbc = os.environ.get("POSTGRES_JDBC_URL")
    if jdbc:
        conn_params = _jdbc_to_conn_params(jdbc)
    else:
        host = os.environ.get("POSTGRES_HOST")
        if not host:
            print("Set POSTGRES_JDBC_URL in .env (or POSTGRES_HOST, PORT, DB, USER, PASSWORD). See docs/POSTGRES_SETUP.md.")
            sys.exit(1)
        conn_params = {
            "host": host,
            "port": int(os.environ.get("POSTGRES_PORT", "5432")),
            "dbname": os.environ.get("POSTGRES_DB", "defaultdb"),
            "user": os.environ.get("POSTGRES_USER", "avnadmin"),
            "password": os.environ.get("POSTGRES_PASSWORD", ""),
            "sslmode": os.environ.get("POSTGRES_SSLMODE", "require"),
        }

    try:
        import psycopg2
    except ImportError:
        print("Install psycopg2: pip install psycopg2-binary")
        sys.exit(1)

    sql_file = REPO_ROOT / "scripts" / "sql" / "postgres_schema.sql"
    if not sql_file.is_file():
        print(f"Schema file not found: {sql_file}")
        sys.exit(1)
    sql = sql_file.read_text()

    print("Connecting to Postgres...")
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    # Run each statement (split on semicolon + newline so we don't break inside CREATE TABLE).
    # Strip leading comment/blank lines so the first segment ("-- ... CREATE SCHEMA") runs CREATE SCHEMA.
    for raw in re.split(r";\s*[\r\n]+", sql):
        segment = raw.strip()
        if not segment:
            continue
        lines = segment.split("\n")
        start = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s and not s.startswith("--"):
                start = i
                break
        stmt = "\n".join(lines[start:]).strip()
        if stmt:
            cur.execute(stmt)
    cur.close()
    conn.close()
    print("Schema created successfully. Tables: medallion.bronze_orders, silver_orders, silver_order_items, gold_daily_sales, gold_customer_360, gold_restaurant_metrics.")


if __name__ == "__main__":
    main()
