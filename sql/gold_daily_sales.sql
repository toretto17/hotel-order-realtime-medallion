-- Gold: Daily sales summary (video: daily_sales_summary)
-- AGGREGATION: GROUP BY order_date, restaurant_id — many orders collapse to ONE row per (date, restaurant).
-- So 100 orders in Silver → e.g. 5–20 rows here (depending on distinct dates/restaurants), not 100.
-- Real-world metrics: revenue, order count, AOV, payment/order-type breakdown, discount/festival usage
-- Expects view: silver_fact_orders (order_id, order_timestamp, restaurant_id, customer_id, order_type,
--   total_amount, payment_method, order_status, discount_code, festival, seasonal_food, ...)
-- order_date is derived in the batch runner and added to the view

SELECT
  order_date,
  restaurant_id,
  COUNT(DISTINCT order_id) AS order_count,
  ROUND(SUM(total_amount), 2) AS total_revenue,
  ROUND(AVG(total_amount), 2) AS avg_order_value,
  COUNT(DISTINCT customer_id) AS unique_customers,
  -- Payment method breakdown (real-world ops)
  SUM(CASE WHEN LOWER(COALESCE(payment_method, '')) IN ('card', 'credit', 'debit') THEN 1 ELSE 0 END) AS payment_card_count,
  SUM(CASE WHEN LOWER(COALESCE(payment_method, '')) = 'cash' THEN 1 ELSE 0 END) AS payment_cash_count,
  SUM(CASE WHEN LOWER(COALESCE(payment_method, '')) NOT IN ('card', 'credit', 'debit', 'cash') OR payment_method IS NULL OR payment_method = '' THEN 1 ELSE 0 END) AS payment_other_count,
  -- Order type breakdown
  SUM(CASE WHEN LOWER(COALESCE(order_type, '')) = 'delivery' THEN 1 ELSE 0 END) AS order_type_delivery_count,
  SUM(CASE WHEN LOWER(COALESCE(order_type, '')) = 'pickup' THEN 1 ELSE 0 END) AS order_type_pickup_count,
  SUM(CASE WHEN LOWER(COALESCE(order_type, '')) NOT IN ('delivery', 'pickup') OR order_type IS NULL OR order_type = '' THEN 1 ELSE 0 END) AS order_type_other_count,
  -- Discount & promotion (real-world marketing metrics)
  SUM(CASE WHEN discount_code IS NOT NULL AND TRIM(discount_code) != '' THEN 1 ELSE 0 END) AS orders_with_discount,
  SUM(CASE WHEN festival IS NOT NULL AND TRIM(festival) != '' THEN 1 ELSE 0 END) AS orders_during_festival,
  SUM(CASE WHEN COALESCE(seasonal_food, FALSE) = TRUE THEN 1 ELSE 0 END) AS orders_with_seasonal_item,
  -- Status (ops)
  SUM(CASE WHEN LOWER(COALESCE(order_status, '')) = 'completed' THEN 1 ELSE 0 END) AS completed_count,
  SUM(CASE WHEN LOWER(COALESCE(order_status, '')) != 'completed' AND order_status IS NOT NULL AND order_status != '' THEN 1 ELSE 0 END) AS other_status_count
FROM silver_fact_orders
WHERE order_date IS NOT NULL
GROUP BY order_date, restaurant_id
ORDER BY order_date DESC, restaurant_id
