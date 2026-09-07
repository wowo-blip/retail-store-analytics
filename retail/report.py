"""从 MySQL 重算全部结果并输出可引用报告。"""
import json
from datetime import datetime,timezone
from .config import engine,REPORTS
from .queries import metadata,query
from .statistics import cluster_bootstrap,standardized_means,decompose


def md_table(df, digits=2):
    cols=list(df.columns)
    rows=['| '+' | '.join(cols)+' |','|'+'|'.join(['---']*len(cols))+'|']
    for row in df.itertuples(index=False,name=None):
        rows.append('| '+' | '.join(f'{x:,.{digits}f}' if isinstance(x,float) else str(x) for x in row)+' |')
    return '\n'.join(rows)


def main():
    db=engine(); m=metadata(db)
    frames={name:query(db,name,m['start'],m['end']) for name in ['kpis','stores','daily','categories','store_categories','monthly','details']}
    days=(m['end']-m['start']).days+1
    frames['stores']['revenue_per_calendar_day']=frames['stores'].revenue/days
    ci=cluster_bootstrap(frames['details'])
    block=cluster_bootstrap(frames['details'],block_days=7)
    standardized,threshold=standardized_means(frames['details'])
    frames.update(bootstrap=ci,bootstrap_block7=block,standardized=standardized)
    for name,frame in frames.items():
        frame.to_csv(REPORTS/f'{name}.csv',index=False,encoding='utf-8-sig')
    ranked=frames['stores']; first,second=ranked.city.iloc[:2]
    attribution=decompose(ranked,first,second)
    summary=dict(generated_at=datetime.now(timezone.utc).isoformat(),source='MySQL retail_analytics.fact_sales',
                 dates=[str(m['start']),str(m['end'])],calendar_days=days,
                 kpis=frames['kpis'].iloc[0].to_dict(),leader=first,comparison=second,
                 decomposition=attribution,bootstrap_repetitions=5000,bootstrap_seed=20260907,
                 top_1pct_threshold=threshold)
    (REPORTS/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    interval_text=[]
    for row in ci.itertuples():
        verdict='区间包含 0，尚不能清楚区分两店平均交易金额' if row.ci_low<=0<=row.ci_high else '区间未包含 0，提示样本期内存在均值差异'
        interval_text.append(f'- {row.city_a} − {row.city_b}：差异 {row.difference:.2f}，95% 区间 [{row.ci_low:.2f}, {row.ci_high:.2f}]；{verdict}。')
    report=f'''# 零售门店经营分析报告

## 分析问题与数据

比较门店销售额，判断差异来自交易笔数还是平均交易金额，并考察品类构成、月份和大额交易的影响。
数据来自原开源项目附带的 Excel 样例；本报告由 MySQL 查询结果生成。样本期 {m['start']} 至 {m['end']}，共 {days} 个日历日、{m['rows']} 笔交易，3 家门店、6 个商品类别。
原界面标注 US $；实际币种和样本采集机制未独立核实，以下统一称“金额”，不把结果解释为真实企业现状。

## 门店表现与差异来源

{md_table(ranked[['city','transactions','units','revenue','average_transaction','revenue_per_calendar_day']])}

销售额最高的 {first} 相比 {second} 高出 {attribution['difference']:.2f}。对称分解中，交易笔数项为 {attribution['transactions_effect']:.2f}，平均交易金额项为 {attribution['average_transaction_effect']:.2f}，两项相加等于销售额差异。这是恒等式分解，不是因果贡献。
日均销售额分母为筛选期日历天数，不是已确认营业天数。

## 平均交易金额差异与不确定性

{chr(10).join(interval_text)}

使用共同日期簇 Bootstrap：每次抽取同一组日期，同时保留这些日期内所有门店的交易，重新计算“总金额 / 交易笔数”并相减。5000 次，随机种子 20260907，百分位 95% 区间。
按日期重抽样保留同日依赖，主分析仍假设日期簇之间足够独立；另以 7 日循环移动块检查短期序列相关的敏感性：

{md_table(block[['city_a','city_b','difference','ci_low','ci_high']])}

这些是探索性的逐对区间，未做多重比较校正；区间包含 0 不等于证明门店完全相同。未知采样机制限制向总体推广，且门店只有 3 家，不估计门店总体的随机效应。

## 品类构成与大额交易敏感性

{md_table(standardized)}

standardized_mean 按全样本各品类交易占比统一加权，比较相同类别构成下的均值；不控制类别内商品和顾客的其他差异。
mean_without_top_1pct 仅用于敏感性分析：统一去除高于合并样本第 99 百分位（{threshold:.2f}）的交易后重新求均值。原数据库没有删掉这些交易。

## 按月份查看稳定性

{md_table(frames['monthly'])}

3 月只到 30 日，跨月总额不构成严格可比的完整月份增长率，因此不展示环比增长结论。

## 可行建议与限制

- 先区分交易量和交易金额，再决定是否进一步调查客流、商品组合或定价；现有数据不能确认改善措施的实际效果。
- 对比具体品类，优先调查品类结构差异；结合进店人数、营销和库存数据后才可评估转化、营销收益或缺货。
- 没有客户唯一 ID，不计算复购、留存或 RFM；没有经过核实的成本口径，不做利润提升承诺。
- 数据检查通过只说明本次检查范围内未发现问题，不保证样本代表性，也不把质量检查描述成大规模脏数据清洗。

可重现命令：`.venv/Scripts/python.exe -m retail.etl`，然后 `.venv/Scripts/python.exe -m retail.report`。
'''
    (REPORTS/'经营分析报告.md').write_text(report,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':
    main()
