-- Medallion Postgres schema — run once after creating the database.
-- Use with Aiven Postgres (or Neon/Supabase). See docs/POSTGRES_SETUP.md.
-- Schema: medallion. Tables only (no views). Column order: business/key cols first, audit/technical last.

CREATE SCHEMA IF NOT EXISTS medallion;

-- Bronze: raw Kafka payloads. Idempotent on (topic, partition, offset).
CREATE TABLE IF NOT EXISTS medallion.bronze_orders (
    _topic     TEXT NOT NULL,
    _partition INT  NOT NULL,
    _offset    BIGINT NOT NULL,
    value      TEXT,
    _ingestion_ts TIMESTAMPTZ,
    _source    TEXT,
    _ingestion_date DATE,
    PRIMARY KEY (_topic, _partition, _offset)
);

-- Silver: one row per order (latest wins). Upsert on order_id. Cols: order_id + business first, _ingestion_ts/_partition/_offset last.
CREATE TABLE IF NOT EXISTS medallion.silver_orders (
    order_id       TEXT NOT NULL PRIMARY KEY,
    order_timestamp TIMESTAMPTZ,
    restaurant_id   TEXT,
    customer_id     TEXT,
    order_type      TEXT,
    total_amount    DOUBLE PRECISION,
    payment_method  TEXT,
    order_status    TEXT,
    discount_code   TEXT,
    festival        TEXT,
    seasonal_food   BOOLEAN,
    order_date      DATE,
    _ingestion_ts   TIMESTAMPTZ,
    _partition      INT,
    _offset         BIGINT
);

-- Silver: one row per order line. Upsert on (order_id, item_id).
CREATE TABLE IF NOT EXISTS medallion.silver_order_items (
    order_id        TEXT NOT NULL,
    item_id         TEXT NOT NULL,
    order_timestamp TIMESTAMPTZ,
    item_name       TEXT,
    category        TEXT,
    quantity        INT,
    unit_price      DOUBLE PRECISION,
    subtotal        DOUBLE PRECISION,
    order_date      DATE,
    PRIMARY KEY (order_id, item_id)
);

-- Gold: daily sales by (order_date, restaurant_id). Key cols first, then metrics.
CREATE TABLE IF NOT EXISTS medallion.gold_daily_sales (
    order_date                DATE NOT NULL,
    restaurant_id             TEXT NOT NULL,
    order_count               BIGINT,
    total_revenue             DOUBLE PRECISION,
    avg_order_value           DOUBLE PRECISION,
    unique_customers          BIGINT,
    payment_card_count        BIGINT,
    payment_cash_count        BIGINT,
    payment_other_count       BIGINT,
    order_type_delivery_count BIGINT,
    order_type_pickup_count   BIGINT,
    order_type_other_count    BIGINT,
    orders_with_discount      BIGINT,
    orders_during_festival    BIGINT,
    orders_with_seasonal_item BIGINT,
    completed_count           BIGINT,
    other_status_count        BIGINT,
    PRIMARY KEY (order_date, restaurant_id)
);

-- Gold: one row per customer. customer_id first, then metrics.
CREATE TABLE IF NOT EXISTS medallion.gold_customer_360 (
    customer_id             TEXT NOT NULL PRIMARY KEY,
    order_count             BIGINT,
    total_spend             DOUBLE PRECISION,
    avg_order_value         DOUBLE PRECISION,
    first_order_date        DATE,
    last_order_date         DATE,
    preferred_payment_method TEXT,
    favorite_restaurant_id  TEXT,
    orders_with_discount    BIGINT,
    orders_during_festival  BIGINT
);

-- Gold: one row per restaurant. restaurant_id first, then metrics.
CREATE TABLE IF NOT EXISTS medallion.gold_restaurant_metrics (
    restaurant_id          TEXT NOT NULL PRIMARY KEY,
    order_count            BIGINT,
    total_revenue          DOUBLE PRECISION,
    avg_order_value        DOUBLE PRECISION,
    unique_customers       BIGINT,
    total_items_sold       BIGINT,
    unique_items_ordered   BIGINT,
    top_selling_category   TEXT
);

-- Optional: indexes for common queries (BI, Grafana).
CREATE INDEX IF NOT EXISTS idx_bronze_ingestion_date ON medallion.bronze_orders (_ingestion_date);
CREATE INDEX IF NOT EXISTS idx_silver_orders_order_date ON medallion.silver_orders (order_date);
CREATE INDEX IF NOT EXISTS idx_silver_orders_customer_id ON medallion.silver_orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_silver_items_order_date ON medallion.silver_order_items (order_date);
