"""Online Retail II：MySQL 主链路与 DuckDB/Parquet 演示共用的交互看板。"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from retail.config import REPORTS,engine
from retail.demo import metadata as demo_metadata,query as demo_query
from retail.queries import metadata as mysql_metadata,query as mysql_query
from retail.statistics import add_return_intervals,cohort_retention,customer_concentration,rfm_segments

st.set_page_config(page_title='Online Retail II 客户与退货分析',page_icon='🛍️',layout='wide')
st.markdown('''<style>
.block-container {padding-top:2.2rem;padding-bottom:3rem;max-width:1550px;}
h1 {font-size:2.05rem !important;font-weight:760 !important;letter-spacing:-.03em;}
h2,h3 {letter-spacing:-.02em;}
[data-testid="metric-container"] {background:white;border:1px solid #dce4eb;border-radius:12px;padding:16px 12px;min-height:108px;}
[data-testid="stMetricValue"] {font-size:1.65rem;}
[data-testid="stMetricLabel"] {color:#597084;}
.eyebrow {font-size:12px;font-weight:700;letter-spacing:.14em;color:#177B70;margin-bottom:6px;}
button[data-baseweb="tab"] {font-size:16px;font-weight:600;}
</style>''',unsafe_allow_html=True)

COLORS=['#177B70','#527BB2','#D29435','#C77356','#7567A8','#769B68']
SEGMENT_COLORS={
    '高价值活跃':'#177B70','忠诚客户':'#527BB2','高价值流失风险':'#C77356',
    '新近客户':'#D29435','潜力客户':'#769B68','沉睡/低频':'#8B98A3',
}


def money(value):
    if pd.isna(value):return '—'
    value=float(value)
    if abs(value)>=1_000_000:return f'£{value/1_000_000:,.2f}M'
    if abs(value)>=1_000:return f'£{value/1_000:,.1f}K'
    return f'£{value:,.2f}'


def chart(figure,height=350):
    figure.update_layout(
        template='plotly_white',height=height,margin=dict(l=16,r=16,t=25,b=16),
        paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Microsoft YaHei, sans-serif',color='#31475B'),
        legend=dict(orientation='h',y=1.12,title=None),
    )
    st.plotly_chart(figure,use_container_width=True,config={'displaylogo':False})


def csv_bytes(frame):
    return frame.to_csv(index=False).encode('utf-8-sig')


@st.cache_resource
def get_db():
    return engine()


@st.cache_data(ttl=60)
def get_mysql_metadata(_db):
    return mysql_metadata(_db)


@st.cache_data(ttl=60)
def get_mysql_query(_db,name,start,end,countries):
    return mysql_query(_db,name,start,end,countries)


@st.cache_data(ttl=60)
def get_demo_metadata():
    return demo_metadata()


@st.cache_data(ttl=60)
def get_demo_query(name,start,end,countries):
    return demo_query(name,start,end,countries)


data_mode=os.getenv('RETAIL_DATA_MODE','auto').lower()
if data_mode not in {'auto','mysql','demo'}:
    st.error('RETAIL_DATA_MODE 只支持 auto、mysql 或 demo。')
    st.stop()

db=None;backend='demo'
if data_mode!='demo':
    try:
        db=get_db();meta=get_mysql_metadata(db);backend='mysql'
    except Exception:
        logging.exception('MySQL 后端初始化失败')
        if data_mode=='mysql':
            st.error('无法连接项目 MySQL；请检查数据库和 ETL 是否已完成。')
            st.stop()
if backend=='demo':
    try:
        meta=get_demo_metadata()
    except Exception:
        logging.exception('DuckDB/Parquet 演示后端初始化失败')
        st.error('无法读取 data/processed/retail_lines.parquet。')
        st.stop()

st.sidebar.title('分析范围')
st.sidebar.caption('统一筛选会同步更新市场、客户、商品和留存指标')
start=st.sidebar.date_input('开始日期',meta['start'],min_value=meta['start'],max_value=meta['end'])
end=st.sidebar.date_input('结束日期',meta['end'],min_value=meta['start'],max_value=meta['end'])
scope=st.sidebar.radio('市场范围',['全部市场','英国本土','国际市场','自定义国家'],horizontal=False)
if scope=='全部市场':
    countries=meta['countries']
elif scope=='英国本土':
    countries=['United Kingdom']
elif scope=='国际市场':
    countries=[country for country in meta['countries'] if country!='United Kingdom']
else:
    countries=st.sidebar.multiselect('选择国家',meta['countries'],default=['Germany','France','Netherlands','EIRE'])
st.sidebar.markdown('---')
st.sidebar.caption('UCI Online Retail II · 2009—2011\n\n金额单位：英镑（GBP）· 行级交易数据')
if start>end:
    st.warning('开始日期不能晚于结束日期。')
    st.stop()
if not countries:
    st.info('请至少选择一个国家。')
    st.stop()

names=['kpis','monthly','countries','products','customers','cohorts','sample']
try:
    if backend=='mysql':
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures={name:pool.submit(get_mysql_query,db,name,start,end,tuple(countries)) for name in names}
            frames={name:future.result() for name,future in futures.items()}
    else:
        frames={name:get_demo_query(name,start,end,tuple(countries)) for name in names}
except Exception:
    logging.exception('指标查询失败')
    st.error('指标查询失败，请检查后端日志。')
    st.stop()

kpi=frames['kpis'].iloc[0]
if not int(kpi.sales_orders or 0):
    st.info('当前筛选范围没有有效销售订单。')
    st.stop()

st.markdown('<div class="eyebrow">ONLINE RETAIL II / REVENUE QUALITY</div>',unsafe_allow_html=True)
st.title('在线零售收入质量、客户留存与退货分析')
st.caption(f'{start:%Y.%m.%d} — {end:%Y.%m.%d} · {len(countries)} 个市场 · 销售、退货与客户行为使用统一口径')
if backend=='demo':
    st.info('当前为 DuckDB + Parquet 免 MySQL 演示；同一批数据的 MySQL ETL、权限和指标对账由 CI 验证。')

cards=[
    ('净收入',money(kpi.net_revenue)),('销售额',money(kpi.gross_sales)),
    ('退货金额',money(kpi.returns_value)),('销售订单',f'{int(kpi.sales_orders):,}'),
    ('平均订单金额',money(kpi.average_order_value)),('已识别客户',f'{int(kpi.known_customers):,}'),
]
for column,(label,value) in zip(st.columns(6),cards):
    column.metric(label,value)
return_value_rate=float(kpi.returns_value/kpi.gross_sales)
st.caption(
    f'净收入 = 销售额 − 退货金额；当前退货金额占销售额 {return_value_rate:.1%}。'
    f'客户 ID 行覆盖率 {float(kpi.customer_id_line_coverage):.1%}，缺失客户不进入 RFM 与留存分析。'
)

overview,customers_tab,products_tab,quality_tab=st.tabs(['经营总览','客户与留存','商品与退货','数据质量'])

with overview:
    st.subheader('销售增长是否转化为可保留的净收入')
    monthly=frames['monthly'].copy()
    monthly['month']=pd.to_datetime(monthly.month)
    figure=go.Figure()
    figure.add_scatter(x=monthly.month,y=monthly.gross_sales,name='销售额',mode='lines+markers',line=dict(color='#85B8B1',width=2))
    figure.add_scatter(x=monthly.month,y=monthly.net_revenue,name='净收入',mode='lines+markers',line=dict(color='#177B70',width=3))
    figure.add_bar(x=monthly.month,y=-monthly.returns_value,name='退货金额（负向）',marker_color='#C77356',opacity=.65)
    figure.update_yaxes(title='GBP')
    chart(figure,390)
    st.caption('2011 年 12 月仅记录到 9 日，不把该月与完整月份直接比较。退货按原始负数量行归入发生月份。')

    country_metrics=add_return_intervals(frames['countries'])
    uk=country_metrics[country_metrics.country=='United Kingdom']
    if not uk.empty and len(country_metrics)>1:
        st.info(f'英国贡献当前筛选净收入的 {float(uk.iloc[0].net_revenue_share):.1%}；国际市场应单独观察，避免被英国体量掩盖。')
    left,right=st.columns([1.35,1])
    with left:
        st.subheader('主要市场净收入')
        display=country_metrics[country_metrics.country!='United Kingdom'].head(12) if len(country_metrics)>12 else country_metrics.head(12)
        figure=px.bar(display.sort_values('net_revenue'),x='net_revenue',y='country',orientation='h',
                      color_discrete_sequence=['#177B70'],labels={'net_revenue':'净收入（GBP）','country':'国家'})
        chart(figure)
    with right:
        st.subheader('市场集中度与退货')
        table=country_metrics.head(12)[['country','net_revenue','net_revenue_share','return_value_rate','sales_orders']].copy()
        table.columns=['国家','净收入','净收入占比','退货金额率','销售订单']
        st.dataframe(table,use_container_width=True,hide_index=True,column_config={
            '净收入':st.column_config.NumberColumn(format='£%.2f'),
            '净收入占比':st.column_config.NumberColumn(format='%.2%%'),
            '退货金额率':st.column_config.NumberColumn(format='%.2%%'),
        })
        st.download_button('下载国家指标 CSV',csv_bytes(country_metrics),'country-metrics.csv','text/csv')

with customers_tab:
    customers=rfm_segments(frames['customers'],end)
    concentration=customer_concentration(customers)
    c1,c2,c3,c4=st.columns(4)
    c1.metric('有购买记录客户',f'{len(customers):,}')
    c2.metric('复购客户占比',f'{concentration["repeat_customer_rate"]:.1%}')
    c3.metric('收入前 10% 客户贡献',f'{concentration["top_share"]:.1%}')
    c4.metric('客户净收入中位数',money(customers.net_revenue.median()))
    st.caption('复购定义为至少 2 个不同销售发票；集中度仅以净收入为正的已识别客户计算，不把缺失客户 ID 拼接成同一客户。')

    left,right=st.columns([1,1.6])
    with left:
        st.subheader('RFM 客户分层')
        segment_summary=(customers.groupby('segment',as_index=False)
                         .agg(customers=('customer_id','size'),net_revenue=('net_revenue','sum'))
                         .sort_values('customers'))
        figure=px.bar(segment_summary,x='customers',y='segment',orientation='h',color='segment',
                      color_discrete_map=SEGMENT_COLORS,labels={'customers':'客户数','segment':'分层'})
        chart(figure)
    with right:
        st.subheader('频次与客户净收入')
        scatter_data=customers.assign(frequency_log10=np.log10(customers.frequency))
        figure=px.scatter(scatter_data,x='frequency_log10',y='monetary',color='segment',opacity=.55,
                          color_discrete_map=SEGMENT_COLORS,hover_data=['customer_id','frequency','recency_days'],
                          labels={'frequency_log10':'销售订单数（对数轴）','monetary':'客户净收入（GBP）','segment':'分层'})
        figure.update_xaxes(tickmode='array',tickvals=[0,1,2],ticktext=['1','10','100'])
        chart(figure)
    st.caption('RFM 分数使用当前筛选范围内五分位；分层用于排序调查，不代表因果或自动营销决策。')

    st.subheader('首次购买月份 cohort：后续月仍有购买的客户占比')
    _,retention=cohort_retention(frames['cohorts'],end)
    if retention.empty:
        st.info('当前范围不足以计算 cohort 留存。')
    else:
        eligible=retention[retention[0]>=50].iloc[:,:13]
        eligible.index=pd.to_datetime(eligible.index).strftime('%Y-%m')
        figure=go.Figure(go.Heatmap(
            z=eligible.values,x=[f'M+{value}' for value in eligible.columns],y=eligible.index,
            zmin=0,zmax=.6,colorscale='Teal',texttemplate='%{z:.0%}',
            hovertemplate='Cohort %{y}<br>%{x}: %{z:.1%}<extra></extra>',
            colorbar=dict(title='留存'),
        ))
        chart(figure,max(400,26*len(eligible)))
        st.caption('仅显示首月客户数至少 50 的 cohort 和前 12 个后续月；“留存”指该月再次购买，不要求逐月连续活跃。')
    st.download_button('下载 RFM 客户分层 CSV',csv_bytes(customers),'customer-rfm.csv','text/csv')

with products_tab:
    products=frames['products'].copy()
    products['return_value_rate']=products.returns_value/products.gross_sales.replace(0,np.nan)
    left,right=st.columns(2)
    with left:
        st.subheader('净收入最高的商品')
        top=products.head(15).sort_values('net_revenue')
        figure=px.bar(top,x='net_revenue',y='description',orientation='h',color_discrete_sequence=['#177B70'],
                      labels={'net_revenue':'净收入（GBP）','description':'商品'})
        chart(figure,430)
    with right:
        st.subheader('高销售额商品中的退货金额率')
        threshold=products.gross_sales.quantile(.75)
        risk=products[(products.gross_sales>=threshold)&(products.returns_value>0)].nlargest(15,'return_value_rate').sort_values('return_value_rate')
        figure=px.bar(risk,x='return_value_rate',y='description',orientation='h',color_discrete_sequence=['#C77356'],
                      labels={'return_value_rate':'退货金额 / 销售额','description':'商品'})
        figure.update_xaxes(tickformat='.0%')
        chart(figure,430)
    st.caption('排行榜排除邮费、银行费用等特殊服务代码；退货金额率只做风险筛查，不能在缺少退货原因和履约数据时归因于商品质量。')

    st.subheader('各市场退货相关发票占比及 95% Wilson 区间')
    intervals=add_return_intervals(frames['countries'])
    intervals=intervals[intervals.commercial_invoices>=30].sort_values('return_invoice_share').tail(20)
    figure=go.Figure(go.Scatter(
        x=intervals.return_invoice_share,y=intervals.country,mode='markers',
        marker=dict(color='#177B70',size=9),
        error_x=dict(type='data',symmetric=False,
                     array=intervals.return_share_high-intervals.return_invoice_share,
                     arrayminus=intervals.return_invoice_share-intervals.return_share_low),
        hovertemplate='%{y}<br>退货相关发票占比 %{x:.1%}<extra></extra>',
    ))
    figure.update_xaxes(title='退货相关发票 / 商业发票',tickformat='.0%')
    chart(figure,max(380,24*len(intervals)))
    st.caption('只展示至少 30 个商业发票的市场。区间反映样本量不确定性；取消发票通常对应历史销售，但数据没有稳定的原销售—退货关联键，因此不称作订单退货概率。')

with quality_tab:
    quality=json.loads((REPORTS/'quality.json').read_text(encoding='utf-8'))
    st.success(f'官方源文件结构校验通过：{quality["rows"]:,} 行，{quality["fatal_rows"]} 行结构性错误。')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('原始行数',f'{quality["rows"]:,}')
    c2.metric('有效销售行',f'{quality["observations"]["sale_line"]:,}')
    c3.metric('有效退货行',f'{quality["observations"]["return_line"]:,}')
    c4.metric('排除行',f'{quality["observations"]["excluded_line"]:,}')
    observation_labels={
        'missing_description':'缺失商品描述','missing_customer_id':'缺失客户 ID',
        'exact_duplicate':'完全重复','cancellation_line':'取消标记行',
        'negative_quantity':'负数量行','nonpositive_price':'非正价格行',
        'excluded_line':'经营指标排除行','sale_line':'有效销售行','return_line':'有效退货行',
        'cancellation_quantity_mismatch':'取消标记与负数量不一致',
    }
    observations=pd.DataFrame([
        {'检查项':observation_labels.get(name,name),'行数':value,'占原始数据':value/quality['rows']}
        for name,value in quality['observations'].items()
    ])
    st.dataframe(observations,use_container_width=True,hide_index=True,column_config={
        '占原始数据':st.column_config.NumberColumn(format='%.2%%'),
    })
    st.markdown('数据由 UCI Machine Learning Repository 发布，许可证为 **CC BY 4.0**，数据集 DOI：`10.24432/C5CG6D`。原始 Excel 不提交到仓库，由下载脚本从官方地址获取并校验固定 SHA-256；仓库仅保留可审计的处理后 Parquet。')
    st.caption(f'源文件 SHA-256：{quality["source_sha256"]} · 数据期：{quality["date_min"]} 至 {quality["date_max"]}')
    st.subheader('最近 1000 条筛选记录（审计样本）')
    st.dataframe(frames['sample'],use_container_width=True,hide_index=True)
    st.download_button('下载审计样本 CSV',csv_bytes(frames['sample']),'retail-line-sample.csv','text/csv')
