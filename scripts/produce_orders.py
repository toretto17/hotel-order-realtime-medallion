#!/usr/bin/env python3
"""
Produce multiple order events to Kafka with varied order_id, customer_id, restaurant_id,
items (from a food list), random quantity 1–10 and random amounts. Supports 100, 500, 1000+
orders in one run; each order uses random combinations so no duplication issues.

Per order: 1–5 line items (random). Each line: random food from list, qty 1–10, unit_price 2–30.
Festivals (Valentine, Christmas, New Year, Diwali, etc.) with matching discount codes applied.

Usage:
  python3 scripts/produce_orders.py              # default 10 orders
  python3 scripts/produce_orders.py 100          # 100 orders
  python3 scripts/produce_orders.py 500
  PRODUCE_ORDERS_COUNT=1000 python3 scripts/produce_orders.py
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python3 scripts/produce_orders.py 300
"""
import json
import os
import random
import sys
from datetime import datetime, timedelta

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "orders")
BASE_PATH = os.environ.get("BASE_PATH", "/tmp/medallion")

# State file: next run continues from last order index (e.g. web-bulk-00000001, web-bulk-00000100).
# Full clean (make clean-data) removes this file so next run starts from web-bulk-00000001 again.
ORDER_INDEX_STATE_FILE = os.path.join(BASE_PATH, ".produce_orders_last_id")

# Seed for reproducible runs (optional)
RANDOM_SEED = int(os.environ.get("PRODUCE_ORDERS_SEED", "42"))
random.seed(RANDOM_SEED)

RESTAURANT_IDS = ["R1", "R2", "R3", "R4", "R5"]
CUSTOMER_IDS = [f"C{i}" for i in range(1, 21)]  # C1..C20
ORDER_TYPES = ["delivery", "pickup", "dine_in"]
PAYMENT_METHODS = ["card", "cash", "card", "card"]
ORDER_STATUSES = ["completed", "completed", "completed", "pending"]

# Food items: list of dicts with id, name, category. unit_price and qty are chosen at random per order line.
# Random unit_price 2–30, random qty 1–10 so 100 or 1000 orders get different combinations.
FOOD_ITEMS = [
    {"item_id": "I1", "name": "Burger", "category": "main"},
    {"item_id": "I2", "name": "Pizza", "category": "main"},
    {"item_id": "I3", "name": "Pasta", "category": "main"},
    {"item_id": "I4", "name": "Grilled Chicken", "category": "main"},
    {"item_id": "I5", "name": "Fish & Chips", "category": "main"},
    {"item_id": "I6", "name": "Curry", "category": "main"},
    {"item_id": "I7", "name": "Tacos", "category": "main"},
    {"item_id": "I8", "name": "Sandwich", "category": "main"},
    {"item_id": "I9", "name": "Salad", "category": "starter"},
    {"item_id": "I10", "name": "Soup", "category": "starter"},
    {"item_id": "I11", "name": "Bruschetta", "category": "starter"},
    {"item_id": "I12", "name": "Spring Rolls", "category": "starter"},
    {"item_id": "I13", "name": "Fries", "category": "side"},
    {"item_id": "I14", "name": "Rice", "category": "side"},
    {"item_id": "I15", "name": "Mashed Potato", "category": "side"},
    {"item_id": "I16", "name": "Coleslaw", "category": "side"},
    {"item_id": "I17", "name": "Soda", "category": "beverage"},
    {"item_id": "I18", "name": "Juice", "category": "beverage"},
    {"item_id": "I19", "name": "Coffee", "category": "beverage"},
    {"item_id": "I20", "name": "Tea", "category": "beverage"},
    {"item_id": "I21", "name": "Water", "category": "beverage"},
    {"item_id": "I22", "name": "Ice Cream", "category": "dessert"},
    {"item_id": "I23", "name": "Cake", "category": "dessert"},
    {"item_id": "I24", "name": "Brownie", "category": "dessert"},
    {"item_id": "I25", "name": "Fruit Bowl", "category": "dessert"},
    {"item_id": "I26", "name": "Noodles", "category": "main"},
    {"item_id": "I27", "name": "Ramen", "category": "main"},
    {"item_id": "I28", "name": "Wrap", "category": "main"},
    {"item_id": "I29", "name": "Onion Rings", "category": "side"},
    {"item_id": "I30", "name": "Garlic Bread", "category": "side"},
]

# Festivals and discount codes — discount applies accordingly (matching festival → matching code)
FESTIVALS = [
    None, None, None,  # no festival often
    "Valentine", "Christmas", "NewYear", "Diwali", "Thanksgiving",
    "Easter", "Halloween", "IndependenceDay", "BlackFriday", "LabourDay",
]
# When order has a festival, use this discount code (discount applies accordingly)
FESTIVAL_TO_DISCOUNT = {
    "Valentine": "LOVE15",
    "Christmas": "XMAS20",
    "NewYear": "NEWYEAR25",
    "Diwali": "DIWALI15",
    "Thanksgiving": "TURKEY10",
    "Easter": "EASTER12",
    "Halloween": "SPOOKY10",
    "IndependenceDay": "FOURTH15",
    "BlackFriday": "BLACKFRIDAY30",
    "LabourDay": "LABOUR10",
}
# Generic discounts when no festival
DISCOUNT_CODES = [None, None, "SAVE10", "FESTIVAL20", "WELCOME5", "FIRST15"]
SEASONAL_FOOD = [False, False, True]

# Spread orders over this many days (so Gold daily_sales has multiple dates: e.g. 20 one day, 50 another)
DAYS_SPREAD = 14


def make_order(order_index: int, base_date: datetime) -> dict:
    """Build one order: random items from FOOD_ITEMS, qty 1–10, unit_price 2–30 per item.
    Order ID uses web-bulk-* so it matches website convention (all orders are web-*)."""
    order_id = f"web-bulk-{order_index:08d}"
    # Random day over last DAYS_SPREAD so we get variety (e.g. 20 orders one day, 50 another)
    days_offset = random.randint(0, DAYS_SPREAD - 1)
    ts = base_date + timedelta(
        days=days_offset,
        hours=random.randint(8, 22),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    order_timestamp = ts.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    restaurant_id = random.choice(RESTAURANT_IDS)
    customer_id = random.choice(CUSTOMER_IDS)
    order_type = random.choice(ORDER_TYPES)
    payment_method = random.choice(PAYMENT_METHODS)
    order_status = random.choice(ORDER_STATUSES)

    # Line items per order: random 1–5 (so each order has 1–5 line items at random)
    n_items = random.randint(1, 5)
    chosen = random.sample(FOOD_ITEMS, min(n_items, len(FOOD_ITEMS)))
    items = []
    total = 0.0
    for it in chosen:
        qty = random.randint(1, 10)
        unit_price = round(random.uniform(2.0, 30.0), 2)
        subtotal = round(unit_price * qty, 2)
        total += subtotal
        items.append({
            "item_id": it["item_id"],
            "name": it["name"],
            "category": it["category"],
            "quantity": qty,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })
    total_amount = round(total, 2)

    payload = {
        "order_id": order_id,
        "order_timestamp": order_timestamp,
        "restaurant_id": restaurant_id,
        "customer_id": customer_id,
        "order_type": order_type,
        "items": items,
        "total_amount": total_amount,
        "payment_method": payment_method,
        "order_status": order_status,
    }
    # Festival and discount: apply discount accordingly (matching code for festival)
    if random.random() < 0.35:
        festival = random.choice(FESTIVALS)
        payload["festival"] = festival
        if festival and festival in FESTIVAL_TO_DISCOUNT:
            payload["discount_code"] = FESTIVAL_TO_DISCOUNT[festival]
        else:
            payload["discount_code"] = random.choice(DISCOUNT_CODES)
    else:
        if random.random() < 0.25:
            payload["discount_code"] = random.choice(DISCOUNT_CODES)
    if random.random() < 0.2:
        payload["seasonal_food"] = random.choice(SEASONAL_FOOD)
    return payload


def _read_last_order_index() -> int:
    """Read last used order index from state file; return 0 if missing or invalid."""
    if not os.path.isfile(ORDER_INDEX_STATE_FILE):
        return 0
    try:
        with open(ORDER_INDEX_STATE_FILE) as f:
            return max(0, int(f.read().strip()))
    except (ValueError, OSError):
        return 0


def _write_last_order_index(index: int) -> None:
    """Persist last used order index so next run continues from index+1."""
    os.makedirs(os.path.dirname(ORDER_INDEX_STATE_FILE) or ".", exist_ok=True)
    with open(ORDER_INDEX_STATE_FILE, "w") as f:
        f.write(str(index))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("count", nargs="?", type=int, default=None, help="Number of orders to produce (default 10)")
    parser.add_argument("--reset", action="store_true", help="Start order_id from 1 (ignore saved state)")
    args = parser.parse_args()

    count = args.count if args.count is not None else int(os.environ.get("PRODUCE_ORDERS_COUNT", "10"))
    count = max(1, min(count, 50000))

    # Order ID continuity: next run starts from last_id+1 unless --reset or state was cleared by clean-data
    if args.reset:
        start_index = 1
    else:
        start_index = _read_last_order_index() + 1
    end_index = start_index + count - 1
    print(f"Order IDs: web-bulk-{start_index:08d} .. web-bulk-{end_index:08d} ({count} orders)")

    try:
        from confluent_kafka import Producer
    except ImportError:
        print("Install confluent_kafka: pip install confluent-kafka", file=sys.stderr)
        sys.exit(1)

    base_date = datetime.utcnow() - timedelta(days=DAYS_SPREAD)
    p = Producer({"bootstrap.servers": BOOTSTRAP})
    err_count = [0]

    def on_delivery(err, msg):
        if err:
            err_count[0] += 1
            print(f"Delivery failed: {err}", file=sys.stderr)

    for i in range(start_index, end_index + 1):
        order = make_order(i, base_date)
        value = json.dumps(order).encode("utf-8")
        p.produce(TOPIC, value=value, callback=on_delivery)
    p.flush(timeout=60)

    if err_count[0]:
        print(f"Produced {count - err_count[0]} orders; {err_count[0]} failed.", file=sys.stderr)
        sys.exit(1)
    _write_last_order_index(end_index)
    print(f"Produced {count} orders to topic '{TOPIC}'. Next run will start from order index {end_index + 1}.")


if __name__ == "__main__":
    main()
