"""
Quick single-order tracer: check if an order exists in Silver and Gold.
Usage: python3 scripts/check_order.py <order_id>
"""
import os, sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pyspark.sql import SparkSession
from streaming.config_loader import get_paths_config, load_config

ORDER_ID = sys.argv[1] if len(sys.argv) > 1 else "web-a054ff91a6e5"

config = load_config()
paths  = get_paths_config(config)

spark = (
    SparkSession.builder
    .appName("check_order")
    .master("local[*]")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

DIV = "─" * 64

def read_parquet(path):
    p = Path(path)
    if not p.exists() or not any(p.rglob("*.parquet")):
        return None
    return spark.read.option("mergeSchema", "true").parquet(path)


print(f"\n{DIV}")
print(f"  Order tracer: {ORDER_ID}")
print(DIV)

# ── Silver: fact_orders ──────────────────────────────────────────────────────
df_orders = read_parquet(paths["silver_orders"])
if df_orders is None:
    print("\n[Silver] fact_orders     → path not found / no data yet")
else:
    match = df_orders.filter(df_orders.order_id == ORDER_ID)
    n = match.count()
    print(f"\n[Silver] fact_orders     → {n} row(s) found")
    if n > 0:
        match.select(
            "order_id", "order_status", "total_amount",
            "payment_method", "order_type", "order_date"
        ).show(truncate=False)

# ── Silver: fact_order_items ─────────────────────────────────────────────────
df_items = read_parquet(paths.get("silver_order_items", ""))
if df_items is None:
    print("[Silver] fact_order_items → path not found / no data yet")
else:
    match_items = df_items.filter(df_items.order_id == ORDER_ID)
    n2 = match_items.count()
    print(f"[Silver] fact_order_items → {n2} item row(s) found")
    if n2 > 0:
        match_items.select(
            "order_id", "item_id", "item_name", "category",
            "quantity", "unit_price", "subtotal"
        ).show(truncate=False)

# ── Gold ─────────────────────────────────────────────────────────────────────
order_date = None
if df_orders is not None:
    rows = df_orders.filter(df_orders.order_id == ORDER_ID).collect()
    if rows:
        order_date   = rows[0]["order_date"]
        customer_id  = rows[0]["customer_id"]
        restaurant_id = rows[0]["restaurant_id"]

print(f"\n{DIV}")
if order_date is None:
    print("[Gold]  Cannot check — order not in Silver yet.")
else:
    print(f"  Order date : {order_date}  |  Customer : {customer_id}  |  Restaurant : {restaurant_id}")
    print(DIV)

    # daily_sales
    df_daily = read_parquet(paths.get("gold_daily_sales", ""))
    if df_daily is None:
        print("[Gold]  daily_sales      → not built yet")
    else:
        row_daily = df_daily.filter(df_daily.order_date == str(order_date))
        n3 = row_daily.count()
        print(f"[Gold]  daily_sales for {order_date} → {n3} row(s)")
        if n3 > 0:
            row_daily.show(truncate=False)

    # customer_360
    df_cust = read_parquet(paths.get("gold_customer_360", ""))
    if df_cust is None:
        print("[Gold]  customer_360     → not built yet")
    else:
        row_cust = df_cust.filter(df_cust.customer_id == customer_id)
        n4 = row_cust.count()
        print(f"[Gold]  customer_360 ({customer_id}) → {n4} row(s)")
        if n4 > 0:
            row_cust.show(truncate=False)

    # restaurant_metrics
    df_rest = read_parquet(paths.get("gold_restaurant_metrics", ""))
    if df_rest is None:
        print("[Gold]  restaurant_metrics → not built yet")
    else:
        row_rest = df_rest.filter(df_rest.restaurant_id == restaurant_id)
        n5 = row_rest.count()
        print(f"[Gold]  restaurant_metrics ({restaurant_id}) → {n5} row(s)")
        if n5 > 0:
            row_rest.show(truncate=False)

print(f"{DIV}\n")
spark.stop()
