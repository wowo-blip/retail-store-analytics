-- 所有查询使用统一日期与国家筛选；销售和退货均保留，排除行不进入经营指标。
-- name: kpis
SELECT
    SUM(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) AS gross_sales,
    SUM(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) AS returns_value,
    SUM(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) AS net_revenue,
    COUNT(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) AS sales_orders,
    COUNT(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) AS return_orders,
    SUM(CASE WHEN transaction_type='sale' THEN quantity ELSE 0 END) AS units_sold,
    SUM(CASE WHEN transaction_type='return' THEN -quantity ELSE 0 END) AS units_returned,
    COUNT(DISTINCT CASE WHEN transaction_type!='excluded' AND customer_id IS NOT NULL THEN customer_id END) AS known_customers,
    COUNT(DISTINCT CASE WHEN transaction_type!='excluded' THEN country END) AS countries,
    SUM(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END)
      / NULLIF(COUNT(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END),0) AS average_order_value,
    SUM(CASE WHEN transaction_type!='excluded' AND customer_id IS NOT NULL THEN 1 ELSE 0 END)
      / NULLIF(SUM(transaction_type!='excluded'),0) AS customer_id_line_coverage
FROM fact_retail_lines WHERE {filters};

-- name: monthly
SELECT DATE_FORMAT(invoice_at,'%Y-%m-01') AS month,
       SUM(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) AS gross_sales,
       SUM(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) AS returns_value,
       SUM(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) AS net_revenue,
       COUNT(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) AS sales_orders,
       COUNT(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) AS return_orders
FROM fact_retail_lines WHERE {filters}
GROUP BY month ORDER BY month;

-- name: countries
SELECT country,
       SUM(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) AS gross_sales,
       SUM(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) AS returns_value,
       SUM(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) AS net_revenue,
       COUNT(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) AS sales_orders,
       COUNT(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) AS return_orders,
       COUNT(DISTINCT CASE WHEN transaction_type!='excluded' AND customer_id IS NOT NULL THEN customer_id END) AS known_customers,
       SUM(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END)
         / NULLIF(SUM(SUM(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END)) OVER (),0) AS net_revenue_share
FROM fact_retail_lines WHERE {filters}
GROUP BY country ORDER BY net_revenue DESC;

-- name: products
SELECT stock_code,MAX(description) AS description,
       SUM(CASE WHEN transaction_type='sale' THEN quantity ELSE 0 END) AS units_sold,
       SUM(CASE WHEN transaction_type='return' THEN -quantity ELSE 0 END) AS units_returned,
       SUM(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) AS gross_sales,
       SUM(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) AS returns_value,
       SUM(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) AS net_revenue
FROM fact_retail_lines IGNORE INDEX (idx_retail_product_date)
WHERE {filters} AND transaction_type!='excluded' AND NOT is_service_line
GROUP BY stock_code ORDER BY net_revenue DESC;

-- name: customers
SELECT customer_id,
       MIN(CASE WHEN transaction_type='sale' THEN invoice_at END) AS first_purchase_at,
       MAX(CASE WHEN transaction_type='sale' THEN invoice_at END) AS last_purchase_at,
       COUNT(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) AS sales_orders,
       COUNT(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) AS return_orders,
       SUM(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) AS gross_sales,
       SUM(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) AS returns_value,
       SUM(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) AS net_revenue
FROM fact_retail_lines
WHERE {filters} AND transaction_type!='excluded' AND customer_id IS NOT NULL
GROUP BY customer_id
HAVING sales_orders>0
ORDER BY net_revenue DESC;

-- name: cohorts
WITH activity AS (
    SELECT DISTINCT customer_id,
           CAST(DATE_FORMAT(invoice_at,'%Y-%m-01') AS DATE) AS activity_month
    FROM fact_retail_lines
    WHERE {filters} AND transaction_type='sale' AND customer_id IS NOT NULL
), firsts AS (
    SELECT customer_id,MIN(activity_month) AS cohort_month
    FROM activity GROUP BY customer_id
)
SELECT firsts.cohort_month,activity.activity_month,
       TIMESTAMPDIFF(MONTH,firsts.cohort_month,activity.activity_month) AS month_number,
       COUNT(*) AS active_customers
FROM activity JOIN firsts USING (customer_id)
GROUP BY firsts.cohort_month,activity.activity_month,month_number
ORDER BY firsts.cohort_month,activity.activity_month;

-- name: sample
SELECT line_id,invoice_id,stock_code,description,quantity,invoice_at,unit_price,
       customer_id,country,line_amount,transaction_type,is_service_line
FROM fact_retail_lines WHERE {filters}
ORDER BY invoice_at DESC,line_id DESC LIMIT 1000;
