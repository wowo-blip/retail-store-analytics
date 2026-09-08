"""MySQL 指标查询：统一绑定日期和国家筛选参数。"""
import re
from datetime import timedelta

import pandas as pd
from sqlalchemy import bindparam,text

from .config import ROOT

SQL={}
for block in re.split(r'-- name: ',(ROOT/'sql/metrics.sql').read_text(encoding='utf-8'))[1:]:
    name,body=block.split('\n',1)
    SQL[name.strip()]=body.strip().rstrip(';')


def metadata(db):
    with db.connect() as conn:
        bounds=conn.execute(text('''
            SELECT MIN(invoice_at),MAX(invoice_at),COUNT(*),
                   COUNT(DISTINCT invoice_id),COUNT(DISTINCT country)
            FROM fact_retail_lines
        ''')).one()
        countries=conn.execute(text('''
            SELECT DISTINCT country FROM fact_retail_lines
            WHERE transaction_type!='excluded' ORDER BY country
        ''')).scalars().all()
    return {
        'start':bounds[0].date(),'end':bounds[1].date(),'rows':bounds[2],
        'invoices':bounds[3],'country_count':bounds[4],
        'countries':sorted(countries,key=str.casefold),
    }


def query(db,name,start,end,countries=None):
    if start>end:
        raise ValueError('开始日期不得晚于结束日期')
    clauses=['invoice_at >= :start','invoice_at < :end_exclusive']
    params={'start':start,'end_exclusive':end+timedelta(days=1)}
    expanding=[]
    if countries is not None:
        if not countries:
            clauses.append('1=0')
        else:
            clauses.append('country IN :countries')
            params['countries']=list(countries)
            expanding.append(bindparam('countries',expanding=True))
    statement=text(SQL[name].format(filters=' AND '.join(clauses))).bindparams(*expanding)
    with db.connect() as conn:
        result=pd.read_sql(statement,conn,params=params)
    for column in ('first_purchase_at','last_purchase_at','invoice_at','cohort_month','activity_month'):
        if column in result:
            result[column]=pd.to_datetime(result[column])
    return result
