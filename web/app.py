"""
Hotel ordering website — submit orders to Kafka for Bronze → Silver → Gold pipeline.
No sign-in/sign-up; guest orders. Same Kafka topic 'orders' and payload schema as pipeline.
Run: from project root, python web/app.py  or  make web
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Repo root for config
REPO_ROOT = Path(__file__).resolve().parent.parent

# Menu: all vegetarian. Each item has a unique image URL; images chosen to match the dish where possible.
# Pipeline uses item_id, name, category, unit_price. Image URLs: Unsplash (w=500&h=350&fit=crop).
# Categories: breakfast, south_indian, north_indian, gujarati, beverage, dessert.
MENU = [
    # Breakfast — idli, dosa, vada, upma, poha (each unique image)
    {"item_id": "I1", "name": "Idli (3 pcs)", "category": "breakfast", "unit_price": 6.0, "image": "https://images.unsplash.com/photo-1589301760014-d929f3989dfb?w=500&h=350&fit=crop"},
    {"item_id": "I2", "name": "Dosa (plain)", "category": "breakfast", "unit_price": 8.0, "image": "https://images.unsplash.com/photo-1630380068630-8a35d42b1e0e?w=500&h=350&fit=crop"},
    {"item_id": "I3", "name": "Medu Vada (3 pcs)", "category": "breakfast", "unit_price": 7.0, "image": "https://images.unsplash.com/photo-1604329760661-e71dc83f2b26?w=500&h=350&fit=crop"},
    {"item_id": "I4", "name": "Upma", "category": "breakfast", "unit_price": 5.0, "image": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500&h=350&fit=crop"},
    {"item_id": "I5", "name": "Poha", "category": "breakfast", "unit_price": 5.0, "image": "https://images.unsplash.com/photo-1546069901-d5bfd2c0b7a6?w=500&h=350&fit=crop"},
    # South Indian — sambar, curd rice, masala dosa, uttapam (each unique)
    {"item_id": "I6", "name": "Sambar", "category": "south_indian", "unit_price": 4.0, "image": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=500&h=350&fit=crop"},
    {"item_id": "I7", "name": "Curd Rice", "category": "south_indian", "unit_price": 7.0, "image": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500&h=350&fit=crop"},
    {"item_id": "I8", "name": "Masala Dosa", "category": "south_indian", "unit_price": 10.0, "image": "https://images.unsplash.com/photo-1630380068630-8a35d42b1e0e?w=500&h=350&fit=crop"},
    {"item_id": "I9", "name": "Uttapam", "category": "south_indian", "unit_price": 9.0, "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=500&h=350&fit=crop"},
    # North Indian — paneer, dal, biryani, naan, paratha (each unique)
    {"item_id": "I10", "name": "Paneer Tikka", "category": "north_indian", "unit_price": 14.0, "image": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=500&h=350&fit=crop"},
    {"item_id": "I11", "name": "Dal Makhani", "category": "north_indian", "unit_price": 10.0, "image": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=500&h=350&fit=crop"},
    {"item_id": "I12", "name": "Veg Biryani", "category": "north_indian", "unit_price": 12.0, "image": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=500&h=350&fit=crop"},
    {"item_id": "I13", "name": "Butter Naan", "category": "north_indian", "unit_price": 5.0, "image": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=500&h=350&fit=crop"},
    {"item_id": "I14", "name": "Aloo Paratha", "category": "north_indian", "unit_price": 8.0, "image": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=500&h=350&fit=crop"},
    # Gujarati — dhokla, thepla, fafda, khandvi (each unique; distinct from breakfast/south)
    {"item_id": "I15", "name": "Dhokla (4 pcs)", "category": "gujarati", "unit_price": 7.0, "image": "https://images.unsplash.com/photo-1599020793233-4301366c6754?w=500&h=350&fit=crop"},
    {"item_id": "I16", "name": "Thepla (3 pcs)", "category": "gujarati", "unit_price": 6.0, "image": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=500&h=350&fit=crop"},
    {"item_id": "I17", "name": "Fafda", "category": "gujarati", "unit_price": 6.0, "image": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=500&h=350&fit=crop"},
    {"item_id": "I18", "name": "Khandvi", "category": "gujarati", "unit_price": 8.0, "image": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=500&h=350&fit=crop"},
    # Beverage — chai, lassi, buttermilk, juice (each unique)
    {"item_id": "I19", "name": "Chai", "category": "beverage", "unit_price": 3.0, "image": "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=500&h=350&fit=crop"},
    {"item_id": "I20", "name": "Lassi", "category": "beverage", "unit_price": 5.0, "image": "https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=500&h=350&fit=crop"},
    {"item_id": "I21", "name": "Buttermilk", "category": "beverage", "unit_price": 4.0, "image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500&h=350&fit=crop"},
    {"item_id": "I22", "name": "Fresh Juice", "category": "beverage", "unit_price": 6.0, "image": "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=500&h=350&fit=crop"},
    # Dessert — gulab jamun, gajar halwa, kheer (each unique)
    {"item_id": "I23", "name": "Gulab Jamun (2 pcs)", "category": "dessert", "unit_price": 7.0, "image": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=500&h=350&fit=crop"},
    {"item_id": "I24", "name": "Gajar Halwa", "category": "dessert", "unit_price": 8.0, "image": "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=500&h=350&fit=crop"},
    {"item_id": "I25", "name": "Kheer", "category": "dessert", "unit_price": 6.0, "image": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=500&h=350&fit=crop"},
]

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "orders")
# Website orders always use this restaurant (the hotel's restaurant). Not random. Set HOTEL_RESTAURANT_ID to override.
RESTAURANT_ID = os.environ.get("HOTEL_RESTAURANT_ID", "R1")


def build_order_payload(order_id: str, items_with_qty: list[dict]) -> dict:
    """Build order JSON matching pipeline schema (Silver ORDER_JSON_SCHEMA)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    line_items = []
    total = 0.0
    for row in items_with_qty:
        item_id = row["item_id"]
        name = row["name"]
        category = row["category"]
        quantity = int(row["quantity"])
        unit_price = float(row["unit_price"])
        subtotal = round(unit_price * quantity, 2)
        total += subtotal
        line_items.append({
            "item_id": item_id,
            "name": name,
            "category": category,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })
    return {
        "order_id": order_id,
        "order_timestamp": now,
        "restaurant_id": RESTAURANT_ID,
        "customer_id": "guest-web",
        "order_type": "dine_in",
        "items": line_items,
        "total_amount": round(total, 2),
        "payment_method": "card",
        "order_status": "pending",
    }


def _kafka_producer_config() -> dict:
    """Build producer config from env; supports plain and SSL/SASL (e.g. Aiven, Confluent Cloud)."""
    cfg = {"bootstrap.servers": KAFKA_BOOTSTRAP}
    security = os.environ.get("KAFKA_SECURITY_PROTOCOL", "").strip().upper()
    if security in ("SSL", "SASL_SSL", "SASL_PLAINTEXT"):
        cfg["security.protocol"] = security
    if security in ("SSL", "SASL_SSL"):
        ca = os.environ.get("KAFKA_SSL_CA_LOCATION") or os.environ.get("KAFKA_SSL_CAFILE")
        if not ca and os.environ.get("KAFKA_SSL_CA_CERT"):
            # For PaaS (e.g. Render): cert in env var; write to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(os.environ["KAFKA_SSL_CA_CERT"])
                ca = f.name
        if ca:
            cfg["ssl.ca.location"] = ca
        # Client certificate (e.g. Aiven service.cert + service.key). On Render use KAFKA_SSL_CERT_CERT / KAFKA_SSL_KEY_CERT (content).
        cert = os.environ.get("KAFKA_SSL_CERT_LOCATION") or os.environ.get("KAFKA_SSL_CERTFILE")
        key = os.environ.get("KAFKA_SSL_KEY_LOCATION") or os.environ.get("KAFKA_SSL_KEYFILE")
        if not cert and os.environ.get("KAFKA_SSL_CERT_CERT"):
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(os.environ["KAFKA_SSL_CERT_CERT"])
                cert = f.name
        if not key and os.environ.get("KAFKA_SSL_KEY_CERT"):
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(os.environ["KAFKA_SSL_KEY_CERT"])
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


def produce_order(payload: dict) -> tuple[bool, str]:
    """Send order to Kafka; return (success, error_message)."""
    try:
        from confluent_kafka import Producer
    except ImportError:
        return False, "Kafka client not installed (pip install confluent-kafka)"
    producer = Producer(_kafka_producer_config())
    value = json.dumps(payload).encode("utf-8")
    err_holder = [None]

    def on_delivery(err, msg):
        err_holder[0] = err

    producer.produce(KAFKA_TOPIC, value=value, callback=on_delivery)
    producer.flush(timeout=10)
    if err_holder[0]:
        return False, str(err_holder[0])
    return True, ""


def create_app():
    from flask import Flask, jsonify, render_template, request
    app = Flask(__name__, static_folder="static", template_folder="templates")

    @app.route("/")
    def index():
        # Group menu by category: breakfast, south_indian, north_indian, gujarati, beverage, dessert (all veg)
        categories_order = ["breakfast", "south_indian", "north_indian", "gujarati", "beverage", "dessert"]
        by_cat = {c: [m for m in MENU if m["category"] == c] for c in categories_order}
        return render_template("index.html", menu=MENU, by_cat=by_cat, categories_order=categories_order)

    @app.route("/api/menu")
    def api_menu():
        return jsonify(MENU)

    @app.route("/api/order", methods=["POST"])
    def api_order():
        data = request.get_json(force=True, silent=True) or {}
        items = data.get("items") or []
        if not items:
            return jsonify({"success": False, "error": "No items in order"}), 400
        # Validate and resolve menu
        menu_by_id = {m["item_id"]: m for m in MENU}
        resolved = []
        for row in items:
            iid = row.get("item_id")
            qty = max(1, int(row.get("quantity", 1)))
            if iid not in menu_by_id:
                return jsonify({"success": False, "error": f"Unknown item: {iid}"}), 400
            resolved.append({**menu_by_id[iid], "quantity": qty})
        order_id = "web-" + uuid.uuid4().hex[:12]
        payload = build_order_payload(order_id, resolved)
        ok, err = produce_order(payload)
        if not ok:
            return jsonify({"success": False, "error": err}), 502
        return jsonify({
            "success": True,
            "order_id": order_id,
            "message": "Thank you! Your order has been received.",
            "total": payload["total_amount"],
        })
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    print(f"Hotel ordering: http://127.0.0.1:{port}")
    print("Ensure Kafka is running (make kafka-up) and Bronze (make bronze) to process orders.")
    app.run(host="0.0.0.0", port=port, debug=False)
