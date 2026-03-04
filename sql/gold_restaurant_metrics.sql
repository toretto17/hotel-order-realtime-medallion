-- Gold: Restaurant metrics (video: restaurant_review_metrics; we do order/item metrics)
-- AGGREGATION: GROUP BY restaurant_id — one row per restaurant. 100 orders across 4 restaurants → 4 rows, not 100.
-- One row per restaurant: order count, revenue, unique customers, items sold (from order_items), top category
-- Expects views: silver_fact_orders (with order_date), silver_fact_order_items

WITH order_metrics AS (
  SELECT
    restaurant_id,
    COUNT(DISTINCT o.order_id) AS order_count,
    ROUND(SUM(o.total_amount), 2) AS total_revenue,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value,
    COUNT(DISTINCT o.customer_id) AS unique_customers
  FROM silver_fact_orders o
  WHERE o.restaurant_id IS NOT NULL AND TRIM(o.restaurant_id) != ''
  GROUP BY restaurant_id
),
item_metrics AS (
  SELECT
    o.restaurant_id,
    SUM(i.quantity) AS total_items_sold,
    COUNT(DISTINCT i.item_id) AS unique_items_ordered
  FROM silver_fact_orders o
  INNER JOIN silver_fact_order_items i ON o.order_id = i.order_id
  WHERE o.restaurant_id IS NOT NULL AND TRIM(o.restaurant_id) != ''
  GROUP BY o.restaurant_id
),
category_rank AS (
  SELECT
    restaurant_id,
    category AS top_category,
    ROW_NUMBER() OVER (PARTITION BY restaurant_id ORDER BY item_count DESC) AS rn
  FROM (
    SELECT o.restaurant_id, i.category, SUM(i.quantity) AS item_count
    FROM silver_fact_orders o
    INNER JOIN silver_fact_order_items i ON o.order_id = i.order_id
    WHERE o.restaurant_id IS NOT NULL AND i.category IS NOT NULL AND TRIM(i.category) != ''
    GROUP BY o.restaurant_id, i.category
  )
)
SELECT
  m.restaurant_id,
  m.order_count,
  m.total_revenue,
  m.avg_order_value,
  m.unique_customers,
  COALESCE(im.total_items_sold, 0) AS total_items_sold,
  COALESCE(im.unique_items_ordered, 0) AS unique_items_ordered,
  c.top_category AS top_selling_category
FROM order_metrics m
LEFT JOIN item_metrics im ON m.restaurant_id = im.restaurant_id
LEFT JOIN (SELECT restaurant_id, top_category FROM category_rank WHERE rn = 1) c ON m.restaurant_id = c.restaurant_id
ORDER BY m.restaurant_id
