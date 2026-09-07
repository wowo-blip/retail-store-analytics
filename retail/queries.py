import re
import pandas as pd
from sqlalchemy import text, bindparam
from .config import ROOT

SQL = {}
for block in re.split(r'-- name: ', (ROOT/'sql/metrics.sql').read_text(encoding='utf-8'))[1:]:
    name, body = block.split('\n',1)
    SQL[name.strip()] = body.strip().rstrip(';')


def metadata(db):
    with db.connect() as conn:
        bounds = conn.execute(text('SELECT MIN(sale_date),MAX(sale_date),COUNT(*) FROM fact_sales')).one()
        options = {}
        for col in ('city','customer_type','product_line'):
            options[col] = conn.execute(text(f'SELECT DISTINCT {col} FROM fact_sales ORDER BY {col}')).scalars().all()
    return {'start':bounds[0], 'end':bounds[1], 'rows':bounds[2], **options}


def query(db, name, start, end, cities=None, customer_types=None, categories=None):
    if start > end:
        raise ValueError('开始日期不得晚于结束日期')
    clauses = ['sale_date BETWEEN :start AND :end']
    params = dict(start=start, end=end)
    expanding = []
    for col, values in [('city',cities), ('customer_type',customer_types), ('product_line',categories)]:
        if values is not None:
            if len(values) == 0:
                clauses.append('1=0')
            else:
                clauses.append(f'{col} IN :{col}')
                params[col] = list(values)
                expanding.append(bindparam(col, expanding=True))
    stmt = text(SQL[name].format(filters=' AND '.join(clauses))).bindparams(*expanding)
    with db.connect() as conn:
        result = pd.read_sql(stmt,conn,params=params)
    if 'sale_date' in result:
        result['sale_date'] = pd.to_datetime(result['sale_date'])
    return result
