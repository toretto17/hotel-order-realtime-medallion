-- Gold: Customer 360 (video: customer_360)
-- AGGREGATION: GROUP BY customer_id — one row per customer. 100 orders from 20 customers → 20 rows, not 100.
-- One row per customer: order count, spend, first/last order, preferred payment (mode), favorite restaurant (most orders)
-- Expects view: silver_fact_orders with order_date column

WITH base AS (
  SELECT
    customer_id,
    order_id,
    order_date,
    restaurant_id,
    total_amount,
    payment_method,
    discount_code,
    festival
  FROM silver_fact_orders
  WHERE customer_id IS NOT NULL AND TRIM(customer_id) != ''
),
agg AS (
  SELECT
    customer_id,
    COUNT(DISTINCT order_id) AS order_count,
    ROUND(SUM(total_amount), 2) AS total_spend,
    ROUND(AVG(total_amount), 2) AS avg_order_value,
    MIN(order_date) AS first_order_date,
    MAX(order_date) AS last_order_date,
    SUM(CASE WHEN discount_code IS NOT NULL AND TRIM(discount_code) != '' THEN 1 ELSE 0 END) AS orders_with_discount,
    SUM(CASE WHEN festival IS NOT NULL AND TRIM(festival) != '' THEN 1 ELSE 0 END) AS orders_during_festival
  FROM base
  GROUP BY customer_id
),
payment_mode AS (
  SELECT customer_id, payment_method AS preferred_payment_method,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY cnt DESC) AS rn
  FROM (
    SELECT customer_id, payment_method, COUNT(*) AS cnt
    FROM base
    WHERE payment_method IS NOT NULL AND TRIM(payment_method) != ''
    GROUP BY customer_id, payment_method
  )
),
restaurant_mode AS (
  SELECT customer_id, restaurant_id AS favorite_restaurant_id,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY cnt DESC) AS rn
  FROM (
    SELECT customer_id, restaurant_id, COUNT(*) AS cnt
    FROM base
    WHERE restaurant_id IS NOT NULL AND TRIM(restaurant_id) != ''
    GROUP BY customer_id, restaurant_id
  )
)
SELECT
  a.customer_id,
  a.order_count,
  a.total_spend,
  a.avg_order_value,
  a.first_order_date,
  a.last_order_date,
  p.preferred_payment_method,
  r.favorite_restaurant_id,
  a.orders_with_discount,
  a.orders_during_festival
FROM agg a
LEFT JOIN (SELECT customer_id, preferred_payment_method FROM payment_mode WHERE rn = 1) p ON a.customer_id = p.customer_id
LEFT JOIN (SELECT customer_id, favorite_restaurant_id FROM restaurant_mode WHERE rn = 1) r ON a.customer_id = r.customer_id
ORDER BY a.customer_id
