"""Excel → 全量校验 → 事务写入 MySQL。任何校验失败都不写入业务表。"""
import hashlib
import json
from decimal import Decimal
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import text
from .config import ROOT, SOURCE, REPORTS, engine

FIELDS = {
    'Invoice ID':'invoice_id', 'Branch':'branch', 'City':'city',
    'Customer_type':'customer_type', 'Gender':'gender', 'Product line':'product_line',
    'Unit price':'unit_price', 'Quantity':'quantity', 'Tax 5%':'tax_amount',
    'Total':'total', 'Date':'sale_date', 'Time':'sale_time', 'Payment':'payment',
    'cogs':'cogs', 'gross margin percentage':'gross_margin_percentage',
    'gross income':'gross_income', 'Rating':'rating',
}
NUMERIC = ['unit_price','quantity','tax_amount','total','cogs','gross_margin_percentage','gross_income','rating']


def read_source(path=SOURCE):
    df = pd.read_excel(path, sheet_name='Sales', skiprows=3, usecols='B:R', engine='openpyxl')
    df.columns = df.columns.str.strip()
    missing = set(FIELDS) - set(df.columns)
    if missing:
        raise ValueError(f'缺少字段：{sorted(missing)}')
    df = df.rename(columns=FIELDS)
    for c in set(df.columns) - set(NUMERIC) - {'sale_date','sale_time'}:
        df[c] = df[c].astype('string').str.strip().replace('', pd.NA)
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['sale_date'] = pd.to_datetime(df['sale_date'], errors='coerce')
    df['sale_time'] = pd.to_datetime(df['sale_time'].astype(str), format='%H:%M:%S', errors='coerce').dt.time
    return df


def validate(df):
    checks = {}
    bad = pd.Series(False, index=df.index)
    def check(name, mask):
        nonlocal bad
        mask = mask.fillna(True).astype(bool)
        checks[name] = int(mask.sum())
        bad |= mask
    check('missing_required', df.isna().any(axis=1))
    check('duplicate_invoice', df['invoice_id'].duplicated(keep=False))
    check('nonfinite_numeric', ~np.isfinite(df[NUMERIC]).all(axis=1))
    check('invalid_quantity', (df.quantity <= 0) | (df.quantity % 1 != 0))
    check('negative_amount', (df[['unit_price','tax_amount','total','cogs','gross_income']] < 0).any(axis=1))
    check('invalid_rating', ~df.rating.between(0, 10))
    check('cost_arithmetic', (df.unit_price * df.quantity - df.cogs).abs() > 0.0001)
    check('tax_arithmetic', (df.cogs * 0.05 - df.tax_amount).abs() > 0.0001)
    check('total_arithmetic', (df.cogs + df.tax_amount - df.total).abs() > 0.0001)
    check('invalid_customer_type', ~df.customer_type.isin(['Member','Normal']))
    check('invalid_branch', ~df.branch.isin(['A','B','C']))
    # 一家门店只能对应一个城市，一个城市只对应一家样例门店。
    check('branch_city_mapping', (df.groupby('branch')['city'].transform('nunique') != 1)
          | (df.groupby('city')['branch'].transform('nunique') != 1))
    report = {'rows':len(df), 'checks':checks, 'invalid_rows':int(bad.sum()),
              'passed': bool(len(df) > 0 and not bad.any()),
              'generated_at':datetime.now(timezone.utc).isoformat()}
    return report, bad


def load(path=SOURCE):
    REPORTS.mkdir(exist_ok=True)
    df = read_source(path)
    quality, bad = validate(df)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    quality.update(source_sha256=sha, source_file=path.name)
    (REPORTS/'quality.json').write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')
    if not quality['passed']:
        rejected = df[bad].copy()
        rejected.insert(0, 'excel_row', rejected.index+5)
        rejected.to_csv(REPORTS/'rejected_rows.csv', index=False, encoding='utf-8-sig')
        raise ValueError('数据校验失败，未导入；请查看 reports/quality.json 和 rejected_rows.csv。')
    total = sum((Decimal(str(x)) for x in df.total), Decimal(0)).quantize(Decimal('0.0001'))
    db = engine('etl')
    with db.connect() as conn:
        for statement in (ROOT/'sql/schema.sql').read_text(encoding='utf-8').split(';'):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()
    with db.begin() as conn:
        prior = conn.execute(text('SELECT source_sha256 FROM dataset_imports')).scalars().all()
        if prior and prior != [sha]:
            raise ValueError('数据库已包含另一个版本的数据。请使用新项目数据库，避免覆盖已有分析。')
        status = 'already_loaded' if prior else 'inserted'
        if not prior:
            conn.execute(text('INSERT INTO dataset_imports (source_sha256,file_name,row_count,total_sales,quality_report) VALUES (:sha,:file,:n,:total,:quality)'),
                         dict(sha=sha,file=path.name,n=len(df),total=total,quality=json.dumps(quality)))
            records = []
            for row in df.to_dict('records'):
                row['sale_date'] = row['sale_date'].date()
                row['quantity'] = int(row['quantity'])
                for c in NUMERIC:
                    if c != 'quantity':
                        row[c] = Decimal(str(row[c]))
                row['source_sha256'] = sha
                records.append(row)
            cols = list(records[0])
            stmt = text('INSERT INTO fact_sales ('+','.join(cols)+') VALUES ('+','.join(':'+c for c in cols)+')')
            conn.execute(stmt, records)
        result = conn.execute(text('SELECT COUNT(*) AS n, SUM(total) AS total, COUNT(DISTINCT source_sha256) AS sources FROM fact_sales')).mappings().one()
        if result['n'] != len(df) or result['total'] != total or result['sources'] != 1:
            raise ValueError('数据库与源文件对账不一致；本次事务已回滚。')
    outcome = dict(status=status, rows=len(df), total=str(total), source_sha256=sha)
    (REPORTS/'import-result.json').write_text(json.dumps(outcome,indent=2),encoding='utf-8')
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return outcome


if __name__ == '__main__':
    load()
