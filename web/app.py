"""
Hotel ordering website — submit orders to Kafka for Bronze → Silver → Gold pipeline.
Guests get a session customer_id; "Your orders" shows only their orders. Super admin sees all and can mark orders done.
Run: from project root, python web/app.py  or  make web
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Repo root for config (and .env lives here when running from project root or web/)
REPO_ROOT = Path(__file__).resolve().parent.parent
# Load .env from project root so ADMIN_PASSWORD, Kafka vars, etc. are set when running "make web" or "cd web && python app.py"
def _load_env():
    loaded = False
    try:
        from dotenv import load_dotenv
        loaded = load_dotenv(REPO_ROOT / ".env")
        if not loaded:
            cwd = Path(os.getcwd()).resolve()
            if cwd.name == "web":
                loaded = load_dotenv(cwd.parent / ".env")
    except ImportError:
        pass
    # Fallback: if dotenv didn't load, parse .env manually (e.g. when package missing)
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        cwd = Path(os.getcwd()).resolve()
        if cwd.name == "web":
            env_file = cwd.parent / ".env"
    if env_file.exists() and not os.environ.get("ADMIN_PASSWORD"):
        try:
            with open(env_file, "r", encoding="utf-8-sig") as f:  # utf-8-sig strips BOM if present
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k = k.strip().lstrip("\ufeff")
                        v = v.strip().strip("'\"").replace("\\n", "\n")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass
_load_env()

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

# Aiven Kafka only: set in .env (local) or environment (e.g. Render)
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "orders")
# Website orders always use this restaurant (the hotel's restaurant). Not random. Set HOTEL_RESTAURANT_ID to override.
RESTAURANT_ID = os.environ.get("HOTEL_RESTAURANT_ID", "R1")
# Super admin: set ADMIN_PASSWORD in env to enable "Mark done" and view all orders.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
# SQLite path for orders (so we can show "Your orders" and admin "All orders")
DB_PATH = Path(__file__).resolve().parent / "instance" / "orders.db"


def init_db() -> None:
    """Create orders table if not exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    """Return a DB connection (caller must close or use as context)."""
    return sqlite3.connect(str(DB_PATH))


def get_orders_by_customer(customer_id: str) -> list[dict]:
    """Return list of orders for customer, newest first."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT order_id, customer_id, order_json, status, created_at, updated_at FROM orders WHERE customer_id = ? ORDER BY created_at DESC",
        (customer_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_orders() -> list[dict]:
    """Return all orders, newest first."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT order_id, customer_id, order_json, status, created_at, updated_at FROM orders ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_order(order_id: str) -> Optional[dict]:
    """Return one order by order_id or None."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT order_id, customer_id, order_json, status, created_at, updated_at FROM orders WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_order(order_id: str, customer_id: str, payload: dict) -> None:
    """Insert order into DB (status from payload)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    conn = get_db()
    conn.execute(
        "INSERT INTO orders (order_id, customer_id, order_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (order_id, customer_id, json.dumps(payload), payload.get("order_status", "pending"), now, now),
    )
    conn.commit()
    conn.close()


def update_order_status(order_id: str, new_status: str) -> Optional[dict]:
    """Update order status in DB; return updated order dict or None if not found."""
    order = get_order(order_id)
    if not order:
        return None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    conn = get_db()
    conn.execute("UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?", (new_status, now, order_id))
    conn.commit()
    conn.close()
    return get_order(order_id)


def build_order_payload(
    order_id: str,
    items_with_qty: list[dict],
    customer_id: str = "guest-web",
    order_status: str = "pending",
    order_timestamp: Optional[str] = None,
) -> dict:
    """Build order JSON matching pipeline schema (Silver ORDER_JSON_SCHEMA)."""
    now = order_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
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
        "customer_id": customer_id,
        "order_type": "dine_in",
        "items": line_items,
        "total_amount": round(total, 2),
        "payment_method": "card",
        "order_status": order_status,
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
            # For PaaS (e.g. Render): cert in env var; write to temp file. Normalize \n if pasted as literal.
            import tempfile
            ca_content = os.environ["KAFKA_SSL_CA_CERT"].replace("\\n", "\n")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(ca_content)
                ca = f.name
        if ca:
            cfg["ssl.ca.location"] = ca
        # Client certificate (e.g. Aiven service.cert + service.key). On Render use KAFKA_SSL_CERT_CERT / KAFKA_SSL_KEY_CERT (content).
        cert = os.environ.get("KAFKA_SSL_CERT_LOCATION") or os.environ.get("KAFKA_SSL_CERTFILE")
        key = os.environ.get("KAFKA_SSL_KEY_LOCATION") or os.environ.get("KAFKA_SSL_KEYFILE")
        if not cert and os.environ.get("KAFKA_SSL_CERT_CERT"):
            import tempfile
            cert_content = os.environ["KAFKA_SSL_CERT_CERT"].replace("\\n", "\n")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(cert_content)
                cert = f.name
        if not key and os.environ.get("KAFKA_SSL_KEY_CERT"):
            import tempfile
            key_content = os.environ["KAFKA_SSL_KEY_CERT"].replace("\\n", "\n")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(key_content)
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
    from flask import Flask, jsonify, render_template, request, session

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    init_db()

    @app.before_request
    def ensure_customer_id():
        if "customer_id" not in session:
            session["customer_id"] = "web-" + uuid.uuid4().hex[:12]
            session.permanent = True

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    @app.route("/")
    def index():
        categories_order = ["breakfast", "south_indian", "north_indian", "gujarati", "beverage", "dessert"]
        by_cat = {c: [m for m in MENU if m["category"] == c] for c in categories_order}
        return render_template("index.html", menu=MENU, by_cat=by_cat, categories_order=categories_order)

    @app.route("/orders")
    def orders_page():
        """Your orders — standalone page (better UX than same-page section)."""
        return render_template("orders.html")

    @app.route("/admin/orders")
    def admin_orders_page():
        """All orders — standalone page for staff (redirect to home if not logged in)."""
        if not session.get("admin") or not ADMIN_PASSWORD:
            from flask import redirect
            return redirect("/?admin=login", 302)
        return render_template("admin_orders.html")

    @app.route("/api/menu")
    def api_menu():
        return jsonify(MENU)

    @app.route("/api/orders")
    def api_orders():
        """Return orders for the current session customer (Your orders)."""
        customer_id = session.get("customer_id", "")
        orders = get_orders_by_customer(customer_id)
        out = []
        for o in orders:
            items = json.loads(o["order_json"]).get("items", [])
            meta = _items_meta(items)
            out.append({
                "order_id": o["order_id"],
                "status": o["status"],
                "created_at": o["created_at"],
                "updated_at": o["updated_at"],
                "total_amount": json.loads(o["order_json"]).get("total_amount"),
                "items_summary": _items_summary(items),
                "item_count": meta["item_count"],
                "total_quantity": meta["total_quantity"],
                "items_list": meta["items_list"],
            })
        return jsonify(out)

    def _items_summary(items: list) -> str:
        parts = [f"{x.get('name', '')} x{x.get('quantity', 0)}" for x in (items or [])[:5]]
        if len(items or []) > 5:
            parts.append("...")
        return ", ".join(parts) if parts else "—"

    def _items_meta(items: list) -> dict:
        items = items or []
        total_qty = sum(int(x.get("quantity", 0)) for x in items)
        return {"item_count": len(items), "total_quantity": total_qty, "items_list": [{"name": x.get("name", ""), "quantity": int(x.get("quantity", 0))} for x in items]}

    @app.route("/api/admin/login", methods=["POST"])
    def api_admin_login():
        """Super admin login: require ADMIN_PASSWORD. Sets session admin=1."""
        if not ADMIN_PASSWORD:
            return jsonify({
                "success": False,
                "error": "Admin login is not set up. Add ADMIN_PASSWORD=yourpassword to the .env file in the project root (not inside web/) and restart the app.",
            }), 503
        data = request.get_json(force=True, silent=True) or {}
        if data.get("password") != ADMIN_PASSWORD:
            return jsonify({"success": False, "error": "Invalid password"}), 401
        session["admin"] = True
        session.permanent = True
        return jsonify({"success": True})

    @app.route("/api/admin/logout", methods=["POST"])
    def api_admin_logout():
        session.pop("admin", None)
        return jsonify({"success": True})

    @app.route("/api/admin/orders")
    def api_admin_orders():
        """Return all orders (super admin only)."""
        if not session.get("admin") or not ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401
        orders = get_all_orders()
        out = []
        for o in orders:
            items = json.loads(o["order_json"]).get("items", [])
            meta = _items_meta(items)
            out.append({
                "order_id": o["order_id"],
                "customer_id": o["customer_id"],
                "status": o["status"],
                "created_at": o["created_at"],
                "updated_at": o["updated_at"],
                "total_amount": json.loads(o["order_json"]).get("total_amount"),
                "items_summary": _items_summary(items),
                "item_count": meta["item_count"],
                "total_quantity": meta["total_quantity"],
                "items_list": meta["items_list"],
            })
        return jsonify(out)

    @app.route("/api/admin/orders/<order_id>/status", methods=["POST"])
    def api_admin_order_status(order_id: str):
        """Update order status and send updated record to Kafka (Bronze). Super admin only."""
        if not session.get("admin") or not ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(force=True, silent=True) or {}
        new_status = (data.get("status") or "").strip().lower() or "done"
        if new_status not in ("pending", "preparing", "done", "completed", "cancelled", "canceled"):
            new_status = "done"
        order = update_order_status(order_id, new_status)
        if not order:
            return jsonify({"success": False, "error": "Order not found"}), 404
        payload = json.loads(order["order_json"])
        payload["order_status"] = new_status
        payload["order_timestamp"] = order["updated_at"]
        ok, err = produce_order(payload)
        if not ok:
            return jsonify({"success": False, "error": err or "Failed to send update to pipeline"}), 502
        return jsonify({"success": True, "order_id": order_id, "status": new_status})

    @app.route("/api/order", methods=["POST"])
    def api_order():
        try:
            data = request.get_json(force=True, silent=True) or {}
            items = data.get("items") or []
            if not items:
                return jsonify({"success": False, "error": "No items in order"}), 400
            menu_by_id = {m["item_id"]: m for m in MENU}
            resolved = []
            for row in items:
                iid = row.get("item_id")
                qty = max(1, int(row.get("quantity", 1)))
                if iid not in menu_by_id:
                    return jsonify({"success": False, "error": f"Unknown item: {iid}"}), 400
                resolved.append({**menu_by_id[iid], "quantity": qty})
            order_id = "web-" + uuid.uuid4().hex[:12]
            customer_id = session.get("customer_id", "guest-web")
            payload = build_order_payload(order_id, resolved, customer_id=customer_id, order_status="pending")
            save_order(order_id, customer_id, payload)
            ok, err = produce_order(payload)
            if not ok:
                return jsonify({"success": False, "error": err or "Failed to send order"}), 502
            return jsonify({
                "success": True,
                "order_id": order_id,
                "message": "Thank you! Your order has been received.",
                "total": payload["total_amount"],
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    return app


# Expose app for Gunicorn: gunicorn app:app
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Hotel ordering: http://127.0.0.1:{port}")
    if ADMIN_PASSWORD:
        print("Admin login: enabled (staff can log in via Login → Staff / Admin)")
    else:
        print("Admin login: disabled — add ADMIN_PASSWORD=yourpassword to .env in project root and restart")
    print("Ensure .env has Aiven Kafka credentials and run Bronze (make bronze) to process orders.")
    app.run(host="0.0.0.0", port=port, debug=False)
