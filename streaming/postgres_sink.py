"""
Postgres sink for Medallion layers. Used by Bronze, Silver, and Gold to sync to Postgres
after successful Parquet writes. Same pattern as Kafka: one URL in .env (POSTGRES_JDBC_URL).
"""
from __future__ import annotations

import re
from typing import Any

from streaming.config_loader import get_postgres_config, load_config


def is_enabled(config: dict[str, Any] | None = None) -> bool:
    """True if Postgres sync is configured (POSTGRES_JDBC_URL set)."""
    cfg = get_postgres_config(config or load_config())
    url = (cfg.get("jdbc_url") or "").strip()
    return bool(url)


def get_jdbc_url(config: dict[str, Any] | None = None) -> str:
    """JDBC URL for Spark DataFrame.write.jdbc()."""
    cfg = get_postgres_config(config or load_config())
    url = (cfg.get("jdbc_url") or "").strip()
    if not url:
        raise ValueError("POSTGRES_JDBC_URL not set in .env")
    return url


def jdbc_to_conn_params(jdbc_url: str) -> dict[str, Any]:
    """Parse JDBC URL into psycopg2 connection params."""
    m = re.match(r"jdbc:postgresql://([^/]+)/([^?]+)(?:\?(.*))?", jdbc_url.strip())
    if not m:
        raise ValueError("Invalid POSTGRES_JDBC_URL; expected jdbc:postgresql://host:port/db?user=...&password=...")
    host_port, dbname, query = m.group(1), m.group(2), (m.group(3) or "")
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    params: dict[str, Any] = {"host": host, "port": port, "dbname": dbname}
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


def get_full_table_name(schema: str, table: str) -> str:
    """e.g. medallion.bronze_orders."""
    return f'"{schema}"."{table}"' if schema else f'"{table}"'


def write_bronze_batch(batch_df: Any, config: dict[str, Any] | None = None) -> None:
    """
    Insert a Bronze micro-batch into Postgres with ON CONFLICT DO NOTHING (idempotent).
    Call from driver (e.g. inside foreachBatch). batch_df is the Spark DataFrame for this batch.
    """
    cfg = get_postgres_config(config or load_config())
    jdbc_url = (cfg.get("jdbc_url") or "").strip()
    if not jdbc_url:
        return
    schema = (cfg.get("schema") or "medallion").strip()
    tables = cfg.get("tables") or {}
    table = (tables.get("bronze_orders") or "bronze_orders").strip()
    full_table = get_full_table_name(schema, table)

    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        raise RuntimeError("Postgres sync requires psycopg2: pip install psycopg2-binary") from None

    conn_params = jdbc_to_conn_params(jdbc_url)
    rows = batch_df.collect()
    if not rows:
        return

    # Bronze columns: value, _ingestion_ts, _source, _partition, _offset, _topic, _ingestion_date
    cols = ["value", "_ingestion_ts", "_source", "_partition", "_offset", "_topic", "_ingestion_date"]
    data = []
    for row in rows:
        data.append(tuple(row[c] for c in cols))

    sql = (
        f'INSERT INTO {full_table} (value, _ingestion_ts, _source, _partition, _offset, _topic, _ingestion_date) '
        "VALUES %s ON CONFLICT (_topic, _partition, _offset) DO NOTHING"
    )
    conn = psycopg2.connect(**conn_params)
    try:
        cur = conn.cursor()
        execute_values(cur, sql, data, page_size=500)
        conn.commit()
    finally:
        conn.close()


def write_silver_orders_batch(batch_df: Any, config: dict[str, Any] | None = None) -> None:
    """
    Upsert a Silver orders micro-batch into Postgres (ON CONFLICT order_id DO UPDATE).
    Call from driver inside Silver foreachBatch. batch_df must include order_date.
    """
    cfg = get_postgres_config(config or load_config())
    jdbc_url = (cfg.get("jdbc_url") or "").strip()
    if not jdbc_url:
        return
    schema = (cfg.get("schema") or "medallion").strip()
    tables = cfg.get("tables") or {}
    table = (tables.get("silver_orders") or "silver_orders").strip()
    full_table = get_full_table_name(schema, table)

    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        raise RuntimeError("Postgres sync requires psycopg2: pip install psycopg2-binary") from None

    conn_params = jdbc_to_conn_params(jdbc_url)
    rows = batch_df.collect()
    if not rows:
        return

    cols = [
        "order_id", "order_timestamp", "restaurant_id", "customer_id", "order_type",
        "total_amount", "payment_method", "order_status", "discount_code", "festival",
        "seasonal_food", "order_date", "_ingestion_ts", "_partition", "_offset",
    ]
    # Postgres ON CONFLICT DO UPDATE cannot affect the same row twice in one INSERT.
    # Dedupe by order_id (keep last row per order_id).
    seen: dict[str, tuple] = {}
    for row in rows:
        key = str(row["order_id"])
        seen[key] = tuple(row[c] for c in cols)
    data = list(seen.values())
    cols_str = ", ".join(cols)
    updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "order_id")
    sql = (
        f'INSERT INTO {full_table} ({cols_str}) VALUES %s '
        f"ON CONFLICT (order_id) DO UPDATE SET {updates}"
    )
    conn = psycopg2.connect(**conn_params)
    try:
        cur = conn.cursor()
        execute_values(cur, sql, data, page_size=500)
        conn.commit()
    finally:
        conn.close()


def write_silver_items_batch(batch_df: Any, config: dict[str, Any] | None = None) -> None:
    """
    Upsert a Silver order_items micro-batch into Postgres (ON CONFLICT (order_id, item_id) DO UPDATE).
    batch_df must include order_date.
    """
    cfg = get_postgres_config(config or load_config())
    jdbc_url = (cfg.get("jdbc_url") or "").strip()
    if not jdbc_url:
        return
    schema = (cfg.get("schema") or "medallion").strip()
    tables = cfg.get("tables") or {}
    table = (tables.get("silver_order_items") or "silver_order_items").strip()
    full_table = get_full_table_name(schema, table)

    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        raise RuntimeError("Postgres sync requires psycopg2: pip install psycopg2-binary") from None

    conn_params = jdbc_to_conn_params(jdbc_url)
    rows = batch_df.collect()
    if not rows:
        return

    cols = ["order_id", "item_id", "order_timestamp", "item_name", "category", "quantity", "unit_price", "subtotal", "order_date"]
    # Dedupe by (order_id, item_id) so one INSERT has no duplicate conflict keys.
    seen: dict[tuple[str, str], tuple] = {}
    for row in rows:
        key = (str(row["order_id"]), str(row["item_id"]))
        seen[key] = tuple(row[c] for c in cols)
    data = list(seen.values())
    cols_str = ", ".join(cols)
    updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in ("order_id", "item_id"))
    sql = (
        f'INSERT INTO {full_table} ({cols_str}) VALUES %s '
        f"ON CONFLICT (order_id, item_id) DO UPDATE SET {updates}"
    )
    conn = psycopg2.connect(**conn_params)
    try:
        cur = conn.cursor()
        execute_values(cur, sql, data, page_size=500)
        conn.commit()
    finally:
        conn.close()


def _write_gold_upsert(
    table_key: str,
    batch_df: Any,
    config: dict[str, Any],
    cols: list[str],
    conflict_keys: list[str],
) -> None:
    """Generic Gold table upsert. batch_df is Spark DataFrame; conflict_keys list for ON CONFLICT."""
    cfg = get_postgres_config(config or load_config())
    jdbc_url = (cfg.get("jdbc_url") or "").strip()
    if not jdbc_url:
        return
    schema = (cfg.get("schema") or "medallion").strip()
    tables = cfg.get("tables") or {}
    table = (tables.get(table_key) or table_key).strip()
    full_table = get_full_table_name(schema, table)

    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        raise RuntimeError("Postgres sync requires psycopg2: pip install psycopg2-binary") from None

    conn_params = jdbc_to_conn_params(jdbc_url)
    rows = batch_df.collect()
    if not rows:
        return

    data = [tuple(row[c] for c in cols) for row in rows]
    cols_str = ", ".join(f'"{c}"' for c in cols)
    updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in conflict_keys)
    sql = (
        f'INSERT INTO {full_table} ({cols_str}) VALUES %s '
        f"ON CONFLICT ({', '.join(conflict_keys)}) DO UPDATE SET {updates}"
    )
    conn = psycopg2.connect(**conn_params)
    try:
        cur = conn.cursor()
        execute_values(cur, sql, data, page_size=500)
        conn.commit()
    finally:
        conn.close()


def write_gold_daily_sales(batch_df: Any, config: dict[str, Any] | None = None) -> None:
    """Upsert Gold daily_sales to Postgres. Fails the job if Postgres write fails (keep Parquet + PG in sync)."""
    cols = [
        "order_date", "restaurant_id", "order_count", "total_revenue", "avg_order_value",
        "unique_customers", "payment_card_count", "payment_cash_count", "payment_other_count",
        "order_type_delivery_count", "order_type_pickup_count", "order_type_other_count",
        "orders_with_discount", "orders_during_festival", "orders_with_seasonal_item",
        "completed_count", "other_status_count",
    ]
    _write_gold_upsert("gold_daily_sales", batch_df, config or load_config(), cols, ["order_date", "restaurant_id"])


def write_gold_customer_360(batch_df: Any, config: dict[str, Any] | None = None) -> None:
    """Upsert Gold customer_360 to Postgres."""
    cols = [
        "customer_id", "order_count", "total_spend", "avg_order_value", "first_order_date",
        "last_order_date", "preferred_payment_method", "favorite_restaurant_id",
        "orders_with_discount", "orders_during_festival",
    ]
    _write_gold_upsert("gold_customer_360", batch_df, config or load_config(), cols, ["customer_id"])


def write_gold_restaurant_metrics(batch_df: Any, config: dict[str, Any] | None = None) -> None:
    """Upsert Gold restaurant_metrics to Postgres."""
    cols = [
        "restaurant_id", "order_count", "total_revenue", "avg_order_value", "unique_customers",
        "total_items_sold", "unique_items_ordered", "top_selling_category",
    ]
    _write_gold_upsert("gold_restaurant_metrics", batch_df, config or load_config(), cols, ["restaurant_id"])
