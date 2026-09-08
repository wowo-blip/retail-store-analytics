"""UCI Excel → 质量画像 → Parquet → 事务写入 MySQL。"""
import hashlib
import json
from datetime import datetime,timezone

import numpy as np
import pandas as pd
from sqlalchemy import text

from .config import ROOT,SOURCE,PROCESSED,REPORTS,engine

SHEETS=('Year 2009-2010','Year 2010-2011')
FIELDS={
    'Invoice':'invoice_id','StockCode':'stock_code','Description':'description',
    'Quantity':'quantity','InvoiceDate':'invoice_at','Price':'unit_price',
    'Customer ID':'customer_id','Country':'country',
}
REQUIRED=('invoice_id','stock_code','quantity','invoice_at','unit_price','country')
EXPECTED_START=pd.Timestamp('2009-12-01 00:00:00')
EXPECTED_END=pd.Timestamp('2011-12-09 23:59:59')
SERVICE_CODES={
    'ADJUST','ADJUST2','AMAZONFEE','B','BANK CHARGES','C2','CRUK','D','DOT',
    'M','PADS','POST','S','TEST001','TEST002',
}
PARQUET_COLUMNS=[
    'line_id','source_sheet','source_row','invoice_id','stock_code','description',
    'quantity','invoice_at','unit_price','customer_id','country','line_amount',
    'is_duplicate','is_cancellation','is_service_line','transaction_type',
]


def source_sha256(path=SOURCE):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def read_source(path=SOURCE):
    frames=[]
    for sheet in SHEETS:
        frame=pd.read_excel(path,sheet_name=sheet,engine='openpyxl')
        missing=set(FIELDS)-set(frame.columns)
        if missing:
            raise ValueError(f'{sheet} 缺少字段：{sorted(missing)}')
        frame=frame.rename(columns=FIELDS)[list(FIELDS.values())]
        frame.insert(0,'source_row',np.arange(2,len(frame)+2,dtype=np.int32))
        frame.insert(0,'source_sheet',sheet)
        frames.append(frame)
    df=pd.concat(frames,ignore_index=True)
    df.insert(0,'line_id',np.arange(1,len(df)+1,dtype=np.int64))
    for column in ('invoice_id','stock_code','description','country'):
        df[column]=df[column].astype('string').str.strip().replace('',pd.NA)
    df['invoice_id']=df.invoice_id.str.upper()
    df['stock_code']=df.stock_code.str.upper()
    df['quantity']=pd.to_numeric(df.quantity,errors='coerce')
    df['invoice_at']=pd.to_datetime(df.invoice_at,errors='coerce')
    df['unit_price']=pd.to_numeric(df.unit_price,errors='coerce')
    df['customer_id']=pd.to_numeric(df.customer_id,errors='coerce').astype('Int64')
    return df


def transform(df):
    result=df.copy()
    business_columns=list(FIELDS.values())
    result['is_duplicate']=result.duplicated(subset=business_columns,keep='first')
    result['is_cancellation']=result.invoice_id.str.upper().str.startswith('C',na=False)
    result['is_service_line']=result.stock_code.str.upper().isin(SERVICE_CODES)
    result['line_amount']=(result.quantity*result.unit_price).round(4)
    structurally_valid=(
        result[list(REQUIRED)].notna().all(axis=1)
        & np.isfinite(result[['quantity','unit_price']]).all(axis=1)
        & (result.quantity!=0)
        & result.invoice_at.between(EXPECTED_START,EXPECTED_END)
    )
    analysis_eligible=(
        structurally_valid & ~result.is_duplicate & result.description.notna()
        & (result.unit_price>0)
    )
    is_return=(analysis_eligible & ((result.quantity<0)|result.is_cancellation)).fillna(False).to_numpy(dtype=bool)
    is_sale=(analysis_eligible & (result.quantity>0) & ~result.is_cancellation).fillna(False).to_numpy(dtype=bool)
    result['transaction_type']=np.select(
        [is_sale,is_return],['sale','return'],default='excluded'
    )
    return result


def validate(df):
    checks={}
    bad=pd.Series(False,index=df.index)

    def fatal(name,mask):
        nonlocal bad
        mask=mask.fillna(True).astype(bool)
        checks[name]=int(mask.sum())
        bad|=mask

    fatal('missing_required',df[list(REQUIRED)].isna().any(axis=1))
    fatal('nonfinite_numeric',~np.isfinite(df[['quantity','unit_price']]).all(axis=1))
    fatal('zero_quantity',df.quantity==0)
    fatal('date_out_of_range',~df.invoice_at.between(EXPECTED_START,EXPECTED_END))
    observations={
        'missing_description':int(df.description.isna().sum()),
        'missing_customer_id':int(df.customer_id.isna().sum()),
        'exact_duplicate':int(df.is_duplicate.sum()),
        'cancellation_line':int(df.is_cancellation.sum()),
        'negative_quantity':int((df.quantity<0).sum()),
        'nonpositive_price':int((df.unit_price<=0).sum()),
        'excluded_line':int((df.transaction_type=='excluded').sum()),
        'sale_line':int((df.transaction_type=='sale').sum()),
        'return_line':int((df.transaction_type=='return').sum()),
        'cancellation_quantity_mismatch':int((df.is_cancellation!=(df.quantity<0)).sum()),
    }
    report={
        'rows':len(df),'fatal_checks':checks,'observations':observations,
        'fatal_rows':int(bad.sum()),'passed':bool(len(df)>0 and not bad.any()),
        'date_min':str(df.invoice_at.min()),'date_max':str(df.invoice_at.max()),
        'countries':int(df.country.nunique()),'invoices':int(df.invoice_id.nunique()),
        'known_customers':int(df.customer_id.nunique()),
        'generated_at':datetime.now(timezone.utc).isoformat(),
    }
    return report,bad


def prepare(path=SOURCE,processed=PROCESSED):
    REPORTS.mkdir(exist_ok=True)
    processed.parent.mkdir(parents=True,exist_ok=True)
    df=transform(read_source(path))
    quality,bad=validate(df)
    quality.update(source_sha256=source_sha256(path),source_file=path.name)
    (REPORTS/'quality.json').write_text(
        json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8'
    )
    if not quality['passed']:
        df.loc[bad].head(1000).to_csv(
            REPORTS/'rejected_rows.csv',index=False,encoding='utf-8-sig'
        )
        raise ValueError('源数据存在结构性错误；请查看 reports/quality.json。')
    df[PARQUET_COLUMNS].to_parquet(
        processed,index=False,compression='zstd',engine='pyarrow'
    )
    return df[PARQUET_COLUMNS],quality


def load(path=SOURCE,processed=PROCESSED):
    df,quality=prepare(path,processed)
    sha=quality['source_sha256']
    db=engine('etl')
    with db.connect() as conn:
        for statement in (ROOT/'sql/schema.sql').read_text(encoding='utf-8').split(';'):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()
    with db.begin() as conn:
        existing=conn.execute(text('SELECT COUNT(*) FROM fact_retail_lines')).scalar()
        sources=conn.execute(text('SELECT DISTINCT source_sha256 FROM fact_retail_lines')).scalars().all()
        if existing and sources!=[sha]:
            raise ValueError('数据库已包含另一版本 Online Retail II 数据，请使用新数据库卷。')
        status='already_loaded' if existing else 'inserted'
        if not existing:
            imported=conn.execute(
                text('SELECT COUNT(*) FROM dataset_imports WHERE source_sha256=:sha'),{'sha':sha}
            ).scalar()
            if not imported:
                conn.execute(text('''
                    INSERT INTO dataset_imports
                        (source_sha256,file_name,row_count,total_sales,quality_report)
                    VALUES (:sha,:file,:rows,:total,:quality)
                '''),{
                    'sha':sha,'file':path.name,'rows':len(df),
                    'total':float(df.loc[df.transaction_type!='excluded','line_amount'].sum()),
                    'quality':json.dumps(quality,ensure_ascii=False),
                })
            columns=PARQUET_COLUMNS+['source_sha256']
            statement=text(
                'INSERT INTO fact_retail_lines ('+','.join(columns)+') VALUES ('+
                ','.join(':'+column for column in columns)+')'
            )
            for start in range(0,len(df),5000):
                chunk=df.iloc[start:start+5000].copy()
                chunk['source_sha256']=sha
                chunk['customer_id']=chunk.customer_id.astype(object).where(chunk.customer_id.notna(),None)
                chunk['description']=chunk.description.astype(object).where(chunk.description.notna(),None)
                conn.execute(statement,chunk.to_dict('records'))
        counts=conn.execute(text('''
            SELECT COUNT(*) AS row_count,
                   SUM(transaction_type='sale') AS sale_lines,
                   SUM(transaction_type='return') AS return_lines
            FROM fact_retail_lines
        ''')).mappings().one()
        if counts['row_count']!=len(df):
            raise ValueError('MySQL 行数与 Parquet 不一致；事务已回滚。')
    outcome={'status':status,'rows':len(df),'source_sha256':sha,**dict(counts)}
    (REPORTS/'import-result.json').write_text(
        json.dumps(outcome,ensure_ascii=False,indent=2,default=str),encoding='utf-8'
    )
    print(json.dumps(outcome,ensure_ascii=False,indent=2,default=str))
    return outcome


if __name__=='__main__':
    load()
