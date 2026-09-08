"""从 MySQL 重算结果并生成可引用的中文分析报告。"""
import json
from datetime import datetime,timezone

import pandas as pd

from .config import REPORTS,engine
from .queries import metadata,query
from .statistics import add_return_intervals,cohort_retention,customer_concentration,rfm_segments


def md_table(frame,digits=2):
    columns=list(frame.columns)
    lines=['| '+' | '.join(columns)+' |','|'+'|'.join(['---']*len(columns))+'|']
    for row in frame.itertuples(index=False,name=None):
        values=[]
        for value in row:
            if isinstance(value,float):values.append(f'{value:,.{digits}f}')
            else:values.append(str(value))
        lines.append('| '+' | '.join(values)+' |')
    return '\n'.join(lines)


def main():
    db=engine();meta=metadata(db)
    names=['kpis','monthly','countries','products','customers','cohorts','sample']
    frames={name:query(db,name,meta['start'],meta['end']) for name in names}
    kpi=frames['kpis'].iloc[0]
    countries=add_return_intervals(frames['countries'])
    customers=rfm_segments(frames['customers'],meta['end'])
    concentration=customer_concentration(customers)
    cohort_counts,retention=cohort_retention(frames['cohorts'],meta['end'])
    frames.update(countries=countries,customers=customers)
    for name,frame in frames.items():
        frame.to_csv(REPORTS/f'{name}.csv',index=False,encoding='utf-8-sig')

    uk=countries[countries.country=='United Kingdom'].iloc[0]
    international=countries[countries.country!='United Kingdom'].head(5)
    products=frames['products'].head(10)
    first_cohort=retention.iloc[0]
    summary={
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'source':'UCI Online Retail II / MySQL fact_retail_lines',
        'dates':[str(meta['start']),str(meta['end'])],
        'rows':meta['rows'],'kpis':kpi.to_dict(),
        'uk_net_revenue_share':float(uk.net_revenue_share),
        'positive_customer_top_10pct_share':concentration['top_share'],
        'repeat_customer_rate':concentration['repeat_customer_rate'],
        'first_cohort_m1_retention':float(first_cohort.get(1,float('nan'))),
    }
    (REPORTS/'summary.json').write_text(
        json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8'
    )

    international_table=international[['country','net_revenue','net_revenue_share','return_value_rate','sales_orders']].copy()
    international_table.columns=['country','net_revenue','share','return_value_rate','sales_orders']
    product_table=products[['stock_code','description','units_sold','returns_value','net_revenue']]
    report=f'''# Online Retail II 收入质量、客户留存与退货分析

## 数据与问题

分析 UCI Online Retail II 的 {meta['rows']:,} 条行级记录，时间为 {meta['start']} 至 {meta['end']}，覆盖 {meta['country_count']} 个国家或地区。金额单位为英镑。
项目关注三个问题：销售额有多少最终转化为净收入；收入是否集中在单一市场或少数客户；哪些商品和市场出现更高的退货信号。

销售行要求数量为正、价格为正、描述存在且不是完全重复；退货行使用负数量或取消发票标记识别。净收入 = 销售额 − 退货金额。缺失客户 ID 的记录保留在财务指标中，但不进入客户和 cohort 分析。

## 收入质量

- 销售额：£{kpi.gross_sales:,.2f}
- 退货金额：£{kpi.returns_value:,.2f}，占销售额 {kpi.returns_value/kpi.gross_sales:.2%}
- 净收入：£{kpi.net_revenue:,.2f}
- 销售订单：{int(kpi.sales_orders):,}；平均订单金额：£{kpi.average_order_value:,.2f}

2011 年 12 月仅记录到 9 日，因此不把该月与完整月份直接比较。退货按负数量行的记录时间归入月份；数据没有稳定的原销售—退货关联键。

## 市场集中

英国贡献 £{uk.net_revenue:,.2f} 净收入，占全样本 {uk.net_revenue_share:.2%}。国际市场规模明显更小，不能在同一纵轴上只看绝对值后直接下结论。

净收入最高的五个国际市场：

{md_table(international_table,4)}

`return_value_rate` 是退货金额 / 销售额，用于风险筛查，不解释为商品质量或履约因果。

## 客户结构与留存

有购买记录的已识别客户为 {len(customers):,}。在净收入为正的客户中：

- 至少有 2 个销售发票的复购客户占 {concentration['repeat_customer_rate']:.2%}；
- 收入前 10% 客户贡献 {concentration['top_share']:.2%}，存在明显客户集中；
- 最早 cohort 在次月仍有购买的客户占 {first_cohort.get(1,float('nan')):.2%}。

RFM 使用当前范围内 recency、frequency、monetary 五分位分层，目的是确定后续调查优先级，不把分层解释为营销措施的效果。

## 商品与退货信号

净收入最高的商品编码：

{md_table(product_table)}

商品排行排除邮费、银行费用等服务代码。高退货金额率只表示需要结合退货原因、履约和商品质量数据继续调查。

## 不确定性与限制

- 各市场“退货相关发票占比”使用 95% Wilson 区间；小样本市场不会因为一个退货发票被误判为稳定高风险。
- 取消发票通常对应历史销售，但缺少稳定配对键，不能计算严格的订单退货概率。
- 原始数据约 {1-float(kpi.customer_id_line_coverage):.1%} 的有效商业行缺少客户 ID，客户留存和 RFM 仅代表可识别客户。
- 数据为 2009—2011 年一家英国非门店零售商的历史记录，不外推为当前行业水平，也不作因果推断。
- 收入集中、复购和退货发现是描述性证据；落地策略需要营销触点、获客成本、退货原因和履约数据。

可重现流程：`python scripts/download_data.py` → `python -m retail.etl` → `python -m retail.report` → `python -m pytest -q`。
'''
    (REPORTS/'经营分析报告.md').write_text(report,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':
    main()
