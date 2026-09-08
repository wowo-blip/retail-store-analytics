"""DuckDB 直接查询 Parquet 的免 MySQL 演示后端。"""
from datetime import timedelta

import duckdb
import pandas as pd

from .config import PROCESSED

SQL={
'kpis':'''SELECT
 sum(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) gross_sales,
 sum(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) returns_value,
 sum(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) net_revenue,
 count(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) sales_orders,
 count(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) return_orders,
 sum(CASE WHEN transaction_type='sale' THEN quantity ELSE 0 END) units_sold,
 sum(CASE WHEN transaction_type='return' THEN -quantity ELSE 0 END) units_returned,
 count(DISTINCT CASE WHEN transaction_type!='excluded' AND customer_id IS NOT NULL THEN customer_id END) known_customers,
 count(DISTINCT CASE WHEN transaction_type!='excluded' THEN country END) countries,
 sum(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END)
  / nullif(count(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END),0) average_order_value,
 count(*) FILTER (WHERE transaction_type!='excluded' AND customer_id IS NOT NULL)
  / nullif(count(*) FILTER (WHERE transaction_type!='excluded'),0) customer_id_line_coverage
 FROM fact_retail_lines WHERE {filters}''',
'monthly':'''SELECT strftime(invoice_at,'%Y-%m-01') AS "month",
 sum(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) gross_sales,
 sum(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) returns_value,
 sum(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) net_revenue,
 count(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) sales_orders,
 count(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) return_orders
 FROM fact_retail_lines WHERE {filters} GROUP BY 1 ORDER BY 1''',
'countries':'''SELECT country,
 sum(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) gross_sales,
 sum(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) returns_value,
 sum(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) net_revenue,
 count(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) sales_orders,
 count(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) return_orders,
 count(DISTINCT CASE WHEN transaction_type!='excluded' AND customer_id IS NOT NULL THEN customer_id END) known_customers,
 sum(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END)
  / nullif(sum(sum(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END)) OVER (),0) net_revenue_share
 FROM fact_retail_lines WHERE {filters} GROUP BY country ORDER BY net_revenue DESC''',
'products':'''SELECT stock_code,max(description) description,
 sum(CASE WHEN transaction_type='sale' THEN quantity ELSE 0 END) units_sold,
 sum(CASE WHEN transaction_type='return' THEN -quantity ELSE 0 END) units_returned,
 sum(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) gross_sales,
 sum(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) returns_value,
 sum(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) net_revenue
 FROM fact_retail_lines WHERE {filters} AND transaction_type!='excluded' AND NOT is_service_line
 GROUP BY stock_code ORDER BY net_revenue DESC''',
'customers':'''SELECT customer_id,
 min(CASE WHEN transaction_type='sale' THEN invoice_at END) first_purchase_at,
 max(CASE WHEN transaction_type='sale' THEN invoice_at END) last_purchase_at,
 count(DISTINCT CASE WHEN transaction_type='sale' THEN invoice_id END) sales_orders,
 count(DISTINCT CASE WHEN transaction_type='return' THEN invoice_id END) return_orders,
 sum(CASE WHEN transaction_type='sale' THEN line_amount ELSE 0 END) gross_sales,
 sum(CASE WHEN transaction_type='return' THEN -line_amount ELSE 0 END) returns_value,
 sum(CASE WHEN transaction_type IN ('sale','return') THEN line_amount ELSE 0 END) net_revenue
 FROM fact_retail_lines WHERE {filters} AND transaction_type!='excluded' AND customer_id IS NOT NULL
 GROUP BY customer_id HAVING sales_orders>0 ORDER BY net_revenue DESC''',
'cohorts':'''WITH activity AS (
 SELECT DISTINCT customer_id,date_trunc('month',invoice_at)::DATE activity_month
 FROM fact_retail_lines WHERE {filters} AND transaction_type='sale' AND customer_id IS NOT NULL
), firsts AS (
 SELECT customer_id,min(activity_month) cohort_month FROM activity GROUP BY customer_id
)
SELECT firsts.cohort_month,activity.activity_month,
 date_diff('month',firsts.cohort_month,activity.activity_month) month_number,
 count(*) active_customers
FROM activity JOIN firsts USING (customer_id)
GROUP BY firsts.cohort_month,activity.activity_month,month_number
ORDER BY firsts.cohort_month,activity.activity_month''',
'sample':'''SELECT line_id,invoice_id,stock_code,description,quantity,invoice_at,unit_price,
 customer_id,country,line_amount,transaction_type,is_service_line
 FROM fact_retail_lines WHERE {filters} ORDER BY invoice_at DESC,line_id DESC LIMIT 1000''',
}


def _connect(path=PROCESSED):
    escaped=str(path.resolve()).replace('\\','/').replace("'","''")
    connection=duckdb.connect()
    connection.execute(f"CREATE VIEW fact_retail_lines AS SELECT * FROM read_parquet('{escaped}')")
    return connection


def metadata(path=PROCESSED):
    with _connect(path) as connection:
        bounds=connection.execute('''
            SELECT min(invoice_at),max(invoice_at),count(*),
                   count(DISTINCT invoice_id),count(DISTINCT country)
            FROM fact_retail_lines
        ''').fetchone()
        countries=[row[0] for row in connection.execute('''
            SELECT DISTINCT country FROM fact_retail_lines
            WHERE transaction_type!='excluded' ORDER BY country
        ''').fetchall()]
    return {
        'start':pd.Timestamp(bounds[0]).date(),'end':pd.Timestamp(bounds[1]).date(),
        'rows':bounds[2],'invoices':bounds[3],'country_count':bounds[4],
        'countries':sorted(countries,key=str.casefold),
    }


def query(name,start,end,countries=None,path=PROCESSED):
    if start>end:
        raise ValueError('开始日期不得晚于结束日期')
    clauses=['invoice_at >= ?','invoice_at < ?']
    params=[start,end+timedelta(days=1)]
    if countries is not None:
        if not countries:
            clauses.append('1=0')
        else:
            clauses.append('country IN ('+','.join('?' for _ in countries)+')')
            params.extend(countries)
    sql=SQL[name].format(filters=' AND '.join(clauses))
    with _connect(path) as connection:
        result=connection.execute(sql,params).df()
    for column in ('first_purchase_at','last_purchase_at','invoice_at','cohort_month','activity_month'):
        if column in result:
            result[column]=pd.to_datetime(result[column])
    return result
