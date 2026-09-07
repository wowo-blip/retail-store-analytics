-- 所有查询使用相同筛选条件，由 SQLAlchemy 绑定参数，用户输入不拼接到 SQL。
-- name: kpis
SELECT COUNT(*) AS transactions, COALESCE(SUM(quantity),0) AS units,
       COALESCE(SUM(total),0) AS revenue, AVG(total) AS average_transaction,
       AVG(rating) AS average_rating, COUNT(DISTINCT sale_date) AS observed_days
FROM fact_sales WHERE {filters};

-- name: stores
SELECT branch, city, COUNT(*) AS transactions, SUM(quantity) AS units,
       SUM(total) AS revenue, AVG(total) AS average_transaction,
       AVG(rating) AS average_rating, COUNT(DISTINCT sale_date) AS observed_days,
       SUM(total) / SUM(SUM(total)) OVER () AS revenue_share,
       DENSE_RANK() OVER (ORDER BY SUM(total) DESC) AS revenue_rank
FROM fact_sales WHERE {filters} GROUP BY branch, city ORDER BY revenue DESC;

-- name: daily
SELECT sale_date, city, COUNT(*) AS transactions, SUM(total) AS revenue,
       SUM(quantity) AS units FROM fact_sales WHERE {filters}
GROUP BY sale_date, city ORDER BY sale_date, city;

-- name: categories
SELECT product_line, COUNT(*) AS transactions, SUM(quantity) AS units,
       SUM(total) AS revenue, AVG(total) AS average_transaction,
       SUM(total) / SUM(SUM(total)) OVER () AS revenue_share
FROM fact_sales WHERE {filters} GROUP BY product_line ORDER BY revenue DESC;

-- name: store_categories
SELECT city, product_line, COUNT(*) AS transactions, SUM(total) AS revenue,
       AVG(total) AS average_transaction
FROM fact_sales WHERE {filters} GROUP BY city, product_line;

-- name: monthly
SELECT DATE_FORMAT(sale_date, '%Y-%m') AS month, city, COUNT(*) AS transactions,
       SUM(total) AS revenue, AVG(total) AS average_transaction
FROM fact_sales WHERE {filters} GROUP BY month, city ORDER BY month, city;

-- name: details
SELECT invoice_id, branch, city, customer_type, gender, product_line,
       unit_price, quantity, tax_amount, total, sale_date, sale_time, payment, rating
FROM fact_sales WHERE {filters} ORDER BY sale_date, invoice_id;
