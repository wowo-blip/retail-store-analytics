"""UCI 数据契约、双后端指标和统计边界测试。"""
import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from retail.config import PROCESSED,REPORTS,SOURCE,SOURCE_ZIP,SOURCE_ZIP_SHA256,engine
from retail.demo import metadata as demo_metadata,query as demo_query
from retail.etl import source_sha256,transform,validate
from retail.queries import metadata as mysql_metadata,query as mysql_query
from retail.statistics import add_return_intervals,cohort_retention,customer_concentration,rfm_segments,wilson_interval
from scripts.download_data import file_sha256


@pytest.fixture(scope='module')
def db():return engine()


@pytest.fixture(scope='module')
def bounds(db):return mysql_metadata(db)


def raw_fixture():
    return pd.DataFrame([
        [1,'Year 2010-2011',2,'500001','abc','Product A',2,pd.Timestamp('2011-01-01 10:00'),3.5,12345,'United Kingdom'],
        [2,'Year 2010-2011',3,'C500002','ABC','Product A',-1,pd.Timestamp('2011-01-02 10:00'),3.5,12345,'United Kingdom'],
        [3,'Year 2010-2011',4,'500001','abc','Product A',2,pd.Timestamp('2011-01-01 10:00'),3.5,12345,'United Kingdom'],
        [4,'Year 2010-2011',5,'500003','POST','Postage',1,pd.Timestamp('2011-01-03 10:00'),10.0,pd.NA,'France'],
        [5,'Year 2010-2011',6,'500004','XYZ','Unknown',1,pd.Timestamp('2011-01-04 10:00'),-1.0,pd.NA,'France'],
    ],columns=['line_id','source_sheet','source_row','invoice_id','stock_code','description','quantity','invoice_at','unit_price','customer_id','country'])


def test_official_download_hashes_match_fixed_version():
    assert file_sha256(SOURCE_ZIP)==SOURCE_ZIP_SHA256
    assert source_sha256(SOURCE)=='bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980'


def test_processed_snapshot_contract():
    frame=pd.read_parquet(PROCESSED,columns=['line_id','stock_code','transaction_type'])
    assert len(frame)==1_067_371
    assert frame.line_id.is_unique
    assert (frame.stock_code.dropna()==frame.stock_code.dropna().str.upper()).all()
    assert frame.transaction_type.value_counts().to_dict()=={
        'sale':1_007_913,'excluded':40_354,'return':19_104,
    }


def test_transform_classifies_sales_returns_duplicates_and_services():
    result=transform(raw_fixture())
    assert result.transaction_type.tolist()==['sale','return','excluded','sale','excluded']
    assert result.is_duplicate.tolist()==[False,False,True,False,False]
    assert result.is_service_line.tolist()==[False,False,False,True,False]
    assert result.line_amount.tolist()==[7.0,-3.5,7.0,10.0,-1.0]
    report,bad=validate(result)
    assert report['passed'] and not bad.any()
    assert report['observations']['missing_customer_id']==2


@pytest.mark.parametrize('field,value,check',[
    ('quantity',0,'zero_quantity'),
    ('unit_price',np.inf,'nonfinite_numeric'),
    ('invoice_at',pd.Timestamp('2012-01-01'),'date_out_of_range'),
    ('country',pd.NA,'missing_required'),
])
def test_validate_rejects_structural_errors(field,value,check):
    frame=transform(raw_fixture());frame.loc[0,field]=value
    report,bad=validate(frame)
    assert not report['passed'] and report['fatal_checks'][check]>0 and bad.iloc[0]


def test_quality_report_discloses_expected_anomalies():
    quality=json.loads((REPORTS/'quality.json').read_text(encoding='utf-8'))
    assert quality['passed'] and quality['fatal_rows']==0
    assert quality['observations']['exact_duplicate']==34_335
    assert quality['observations']['missing_customer_id']==243_007
    assert quality['observations']['nonpositive_price']==6_207


def test_mysql_row_counts_and_financial_identity(db,bounds):
    kpi=mysql_query(db,'kpis',bounds['start'],bounds['end']).iloc[0]
    assert bounds['rows']==1_067_371
    assert kpi.sales_orders==40_077 and kpi.return_orders==8_292
    assert kpi.gross_sales==pytest.approx(20_476_260.448,abs=.001)
    assert kpi.returns_value==pytest.approx(1_462_050.61,abs=.001)
    assert kpi.net_revenue==pytest.approx(kpi.gross_sales-kpi.returns_value,abs=.001)


def test_filters_are_bound_and_date_end_is_inclusive(db):
    start=pd.Timestamp('2011-01-01').date();end=pd.Timestamp('2011-01-31').date()
    mysql=mysql_query(db,'kpis',start,end,['Germany']).iloc[0]
    demo=demo_query('kpis',start,end,['Germany']).iloc[0]
    assert mysql.sales_orders==demo.sales_orders
    assert mysql.net_revenue==pytest.approx(demo.net_revenue,rel=1e-7)
    injected=mysql_query(db,'kpis',start,end,["Germany' OR 1=1 --"]).iloc[0]
    assert injected.sales_orders==0
    with pytest.raises(ValueError):mysql_query(db,'kpis',end,start)


def test_reader_is_select_only(db):
    with db.connect() as connection:
        grants=connection.execute(text('SHOW GRANTS')).scalars().all()
    assert any('GRANT SELECT ON' in grant for grant in grants)
    assert not any('INSERT' in grant or 'ALL PRIVILEGES' in grant for grant in grants)


@pytest.mark.parametrize('name,sort_by,ignore',[
    ('kpis',[],[]),('monthly',['month'],[]),('countries',['country'],[]),
    ('products',['stock_code'],['description']),('customers',['customer_id'],[]),
    ('cohorts',['cohort_month','activity_month'],[]),
])
def test_duckdb_matches_mysql(db,bounds,name,sort_by,ignore):
    actual=mysql_query(db,name,bounds['start'],bounds['end'])
    expected=demo_query(name,bounds['start'],bounds['end'])
    if sort_by:
        actual=actual.sort_values(sort_by).reset_index(drop=True)
        expected=expected.sort_values(sort_by).reset_index(drop=True)
    actual=actual.drop(columns=ignore)
    expected=expected.drop(columns=ignore)
    pd.testing.assert_frame_equal(actual,expected,check_dtype=False,rtol=1e-4,atol=1e-4)


def test_wilson_interval_and_country_enrichment():
    low,high=wilson_interval([5],[10])
    assert low[0]==pytest.approx(.2366,abs=.001)
    assert high[0]==pytest.approx(.7634,abs=.001)
    countries=pd.DataFrame({'sales_orders':[90],'return_orders':[10],'returns_value':[50.],'gross_sales':[1000.]})
    result=add_return_intervals(countries).iloc[0]
    assert result.return_invoice_share==pytest.approx(.1)
    assert result.return_value_rate==pytest.approx(.05)


def test_rfm_cohorts_and_concentration_boundaries():
    customers=pd.DataFrame({
        'customer_id':range(1,11),'last_purchase_at':pd.date_range('2011-01-01',periods=10),
        'sales_orders':range(1,11),'net_revenue':np.arange(10,110,10),
    })
    segmented=rfm_segments(customers,pd.Timestamp('2011-01-31'))
    assert segmented.segment.notna().all()
    concentration=customer_concentration(segmented)
    assert concentration['customers']==10 and 0<concentration['top_share']<=1
    cohorts=pd.DataFrame({
        'cohort_month':pd.to_datetime(['2011-01-01','2011-01-01']),
        'activity_month':pd.to_datetime(['2011-01-01','2011-02-01']),
        'month_number':[0,1],'active_customers':[100,30],
    })
    counts,retention=cohort_retention(cohorts,pd.Timestamp('2011-02-28'))
    assert counts.loc[pd.Timestamp('2011-01-01'),1]==30
    assert retention.loc[pd.Timestamp('2011-01-01'),1]==pytest.approx(.3)


def test_metadata_matches_between_backends(bounds):
    demo=demo_metadata()
    for key in ('start','end','rows','invoices','country_count','countries'):
        assert bounds[key]==demo[key]
