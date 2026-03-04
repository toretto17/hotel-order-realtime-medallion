"""
Order event schema — single source of truth for what flows through the pipeline.

Why this file matters (interview-ready):
- Idempotency: order_id is the idempotency key. Same order_id replayed (e.g. after
  failure) must not create duplicate rows in Silver; we merge/upsert by order_id.
- Event time vs processing time: order_timestamp is event time (when the order happened);
  we use it for watermarking and late-data policy. Processing time is when we ingested.
- Schema evolution: New fields can appear in the source (e.g. "discount_code"). We store
  raw in Bronze (schema-on-read); in Silver we only expose columns we need. New fields
  get added in Silver when we're ready — no breaking change to the pipeline.

Production validations (this module):
- order_id: non-empty; optional format pattern (e.g. ^ord-\\d{8}$) is configurable per source.
- order_timestamp: parsed and validated as ISO8601; we treat as UTC for watermarking.
- restaurant_id / customer_id: non-empty (FK vs dim_restaurant/dim_customer is Silver-layer).
- order_type / payment_method / order_status: enum-only (no freeform).
- items: at least one item; total_amount >= 0.
- State machine (e.g. pending -> completed only): enforce in Silver or application layer, not here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# -----------------------------------------------------------------------------
# Enums — no freeform text; production DQ at parse time
# -----------------------------------------------------------------------------


class OrderType(str, Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    WALLET = "wallet"


class OrderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    READY = "ready"


# Optional: if your source guarantees a format, set e.g. re.compile(r"^ord-\d{8}$"); None = any non-empty.
ORDER_ID_PATTERN: re.Pattern | None = None

# -----------------------------------------------------------------------------
# Helpers for validation
# -----------------------------------------------------------------------------


def _require_non_empty(s: str, field_name: str) -> str:
    out = str(s).strip()
    if not out:
        raise ValueError(f"{field_name} must be non-empty")
    return out


def _parse_utc_timestamp(ts: str) -> str:
    """Parse ISO8601 timestamp; normalize to UTC; return ISO8601 string for storage."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except (ValueError, TypeError) as e:
        raise ValueError(f"order_timestamp must be ISO8601 (UTC): {e}") from e


def _validate_order_id(order_id: str) -> str:
    out = _require_non_empty(order_id, "order_id")
    if ORDER_ID_PATTERN is not None and not ORDER_ID_PATTERN.match(out):
        raise ValueError(f"order_id must match pattern {ORDER_ID_PATTERN.pattern!r}")
    return out


# -----------------------------------------------------------------------------
# Canonical order event (what we expect from Kafka topic "orders")
# -----------------------------------------------------------------------------


@dataclass
class OrderItem:
    """One line item in an order. Idempotency for items: (order_id, item_id)."""
    item_id: str
    name: str
    category: str
    quantity: int
    unit_price: float
    subtotal: float

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OrderItem":
        return cls(
            item_id=_require_non_empty(str(d["item_id"]), "item_id"),
            name=str(d["name"]),
            category=str(d["category"]),
            quantity=int(d["quantity"]),
            unit_price=float(d["unit_price"]),
            subtotal=float(d["subtotal"]),
        )


@dataclass
class OrderEvent:
    """
    Root order event. Must have order_id and order_timestamp for pipeline to use.
    - order_id: Idempotency key. Silver dedup/merge by this.
    - order_timestamp: Event time; used for watermark and partitioning.
    """
    order_id: str
    order_timestamp: str  # ISO8601 UTC
    restaurant_id: str
    customer_id: str
    order_type: OrderType
    items: list[OrderItem]
    total_amount: float
    payment_method: PaymentMethod
    order_status: OrderStatus

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OrderEvent":
        raw_order_type = str(d["order_type"]).strip().lower()
        raw_payment = str(d["payment_method"]).strip().lower()
        raw_status = str(d["order_status"]).strip().lower()

        try:
            order_type = OrderType(raw_order_type)
        except ValueError:
            raise ValueError(f"order_type must be one of {[e.value for e in OrderType]}, got {raw_order_type!r}")

        try:
            payment_method = PaymentMethod(raw_payment)
        except ValueError:
            raise ValueError(f"payment_method must be one of {[e.value for e in PaymentMethod]}, got {raw_payment!r}")

        try:
            order_status = OrderStatus(raw_status)
        except ValueError:
            raise ValueError(f"order_status must be one of {[e.value for e in OrderStatus]}, got {raw_status!r}")

        items_raw = d["items"]
        if not items_raw or len(items_raw) < 1:
            raise ValueError("items must contain at least one item")

        total_amount = float(d["total_amount"])
        if total_amount < 0:
            raise ValueError("total_amount must be >= 0")

        return cls(
            order_id=_validate_order_id(str(d["order_id"])),
            order_timestamp=_parse_utc_timestamp(str(d["order_timestamp"])),
            restaurant_id=_require_non_empty(str(d["restaurant_id"]), "restaurant_id"),
            customer_id=_require_non_empty(str(d["customer_id"]), "customer_id"),
            order_type=order_type,
            items=[OrderItem.from_dict(i) for i in items_raw],
            total_amount=total_amount,
            payment_method=payment_method,
            order_status=order_status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "order_timestamp": self.order_timestamp,
            "restaurant_id": self.restaurant_id,
            "customer_id": self.customer_id,
            "order_type": self.order_type.value,
            "items": [
                {
                    "item_id": i.item_id,
                    "name": i.name,
                    "category": i.category,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "subtotal": i.subtotal,
                }
                for i in self.items
            ],
            "total_amount": self.total_amount,
            "payment_method": self.payment_method.value,
            "order_status": self.order_status.value,
        }


# JSON schema (for validation or docs). Optional: use in Spark schema-on-read.
ORDER_EVENT_JSON_SCHEMA = {
    "type": "object",
    "required": [
        "order_id",
        "order_timestamp",
        "restaurant_id",
        "customer_id",
        "order_type",
        "items",
        "total_amount",
        "payment_method",
        "order_status",
    ],
    "properties": {
        "order_id": {"type": "string"},
        "order_timestamp": {"type": "string"},
        "restaurant_id": {"type": "string"},
        "customer_id": {"type": "string"},
        "order_type": {"type": "string", "enum": ["dine_in", "takeaway", "delivery"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["item_id", "name", "category", "quantity", "unit_price", "subtotal"],
                "properties": {
                    "item_id": {"type": "string"},
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "unit_price": {"type": "number"},
                    "subtotal": {"type": "number"},
                },
            },
        },
        "total_amount": {"type": "number"},
        "payment_method": {"type": "string", "enum": ["cash", "card", "wallet"]},
        "order_status": {"type": "string", "enum": ["pending", "completed", "ready"]},
    },
}
