"""关键口径与边界测试；数据库测试只读，不修改业务表。"""
from decimal import Decimal
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from retail.etl import read_source,validate
from retail.config import engine
from retail.queries import metadata,query
from retail.statistics import cluster_bootstrap,decompose,standardized_means

@pytest.fixture(scope='module')
def source():return read_source()

@pytest.fixture(scope='module')
def db():return engine()

def test_source_quality(source):
    report,bad=validate(source)
    assert report['passed'] and len(source)==1000 and not bad.any()

@pytest.mark.parametrize('field,value,check',[
    ('quantity',0,'invalid_quantity'),('total',-1,'negative_amount'),
    ('rating',11,'invalid_rating'),('total',9999,'total_arithmetic'),
    ('city',pd.NA,'missing_required'),('unit_price',np.inf,'nonfinite_numeric'),
])
def test_reject_corrupt_data(source,field,value,check):
    df=source.copy();df.loc[0,field]=value
    report,bad=validate(df)
    assert not report['passed'] and report['checks'][check]>0 and bad.iloc[0]

def test_duplicate_key_is_rejected(source):
    df=pd.concat([source,source.iloc[:1]],ignore_index=True)
    assert validate(df)[0]['checks']['duplicate_invoice']==2

def test_sql_source_and_decimal_reconcile(source,db):
    m=metadata(db); k=query(db,'kpis',m['start'],m['end']).iloc[0]
    assert k.transactions==len(source)
    assert k.units==source.quantity.sum()
    with db.connect() as conn:
        sql_total=conn.execute(text('SELECT SUM(total) FROM fact_sales')).scalar()
    assert sql_total==sum(map(lambda x:Decimal(str(x)),source.total))
    for name in ['stores','daily','categories','store_categories','monthly']:
        assert query(db,name,m['start'],m['end']).revenue.sum()==pytest.approx(float(sql_total),abs=1e-6)

def test_sql_filters_and_calendar_boundary(source,db):
    start=pd.Timestamp('2021-02-01').date();end=pd.Timestamp('2021-02-28').date()
    filtered=source[(source.sale_date.dt.date>=start)&(source.sale_date.dt.date<=end)&(source.city=='Yangon')&(source.customer_type=='Member')]
    k=query(db,'kpis',start,end,['Yangon'],['Member']).iloc[0]
    assert k.transactions==len(filtered)
    assert k.revenue==pytest.approx(filtered.total.sum())
    assert query(db,'kpis',start,end,[]).iloc[0].transactions==0
    assert query(db,'kpis',start,end,["Yangon' OR 1=1 --"]).iloc[0].transactions==0
    with pytest.raises(ValueError):query(db,'kpis',end,start)

def test_reader_has_only_select(db):
    with db.connect() as conn:
        grants=conn.execute(text('SHOW GRANTS')).scalars().all()
    assert any('GRANT SELECT ON' in s for s in grants)
    assert not any('INSERT' in s or 'ALL PRIVILEGES' in s for s in grants)

def test_decomposition_identity(db):
    m=metadata(db);s=query(db,'stores',m['start'],m['end'])
    result=decompose(s,'Naypyitaw','Yangon')
    assert result['transactions_effect']<0 and result['average_transaction_effect']>0
    assert result['difference']==pytest.approx(result['transactions_effect']+result['average_transaction_effect'],abs=0.0001)

def paired_fixture():
    rows=[]
    for i,date in enumerate(pd.date_range('2021-01-01',periods=40)):
        for city,offset in [('A',0),('B',5)]:
            rows.append(dict(sale_date=date,city=city,total=float(i+10+offset),product_line='same'))
    return pd.DataFrame(rows)

@pytest.mark.parametrize('block',[1,7])
def test_paired_cluster_preserves_day_effect(block):
    result=cluster_bootstrap(paired_fixture(),repetitions=500,block_days=block).iloc[0]
    assert result.status=='ok'
    assert result.difference==pytest.approx(-5)
    assert result.ci_low==pytest.approx(-5) and result.ci_high==pytest.approx(-5)

def test_bootstrap_reproducible_and_insufficient():
    data=paired_fixture()
    pd.testing.assert_frame_equal(cluster_bootstrap(data,100),cluster_bootstrap(data,100))
    assert cluster_bootstrap(data.iloc[:10],100).iloc[0].status=='insufficient_data'
    assert cluster_bootstrap(data[data.city=='A'],100).empty

def test_standardization_does_not_impute_missing_category():
    d=pd.DataFrame({'city':['A','A','B'],'product_line':['X','Y','X'],'total':[10.,20.,30.]})
    result,_=standardized_means(d)
    assert pd.isna(result.set_index('city').loc['B','standardized_mean'])
    assert result.set_index('city').loc['A','standardized_mean']==pytest.approx(40/3)
