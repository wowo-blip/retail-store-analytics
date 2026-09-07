"""自主扩展看板：业务指标由 MySQL 汇总，统计分析基于同一筛选后的明细。"""
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text
from retail.config import engine,REPORTS
from retail.queries import metadata,query
from retail.statistics import cluster_bootstrap,standardized_means,decompose

st.set_page_config(page_title='零售门店经营分析',page_icon='📊',layout='wide')
st.markdown('''<style>
.block-container {padding-top:2.5rem;padding-bottom:3rem;max-width:1600px;}
h1 {font-size:2.1rem !important;font-weight:750 !important;letter-spacing:-.03em;}
h2,h3 {letter-spacing:-.02em;}
[data-testid="metric-container"] {background:white;border:1px solid #dce4eb;border-radius:12px;padding:18px 12px;min-height:110px;}
[data-testid="stMetricValue"] {font-size:1.7rem;}
[data-testid="stMetricLabel"] {color:#597084;}
h3 {font-size:1.3rem !important;}
.eyebrow {font-size:12px;font-weight:700;letter-spacing:.14em;color:#177B70;margin-bottom:6px;}
button[data-baseweb="tab"] {font-size:16px;font-weight:600;}
</style>''',unsafe_allow_html=True)

COLORS=['#177B70','#D29435','#527BB2']
CITY_COLORS={'Naypyitaw':'#177B70','Yangon':'#D29435','Mandalay':'#527BB2'}
LABELS={'city':'门店所在城市','revenue':'销售额','transactions':'交易笔数','units':'商品件数',
        'average_transaction':'平均交易金额','average_rating':'平均评分','observed_days':'有交易日期数',
        'revenue_share':'销售额占比','revenue_rank':'销售额排名','branch':'门店',
        'product_line':'商品类别','sale_date':'日期','revenue_per_calendar_day':'日均销售额'}

@st.cache_resource
def get_db():
    return engine()

@st.cache_data(ttl=30)
def get_metadata(_db):
    return metadata(_db)

@st.cache_data(ttl=30)
def get_query(_db,name,start,end,cities,customer_types,categories):
    return query(_db,name,start,end,cities,customer_types,categories)

@st.cache_data
def statistics(df):
    return cluster_bootstrap(df),cluster_bootstrap(df,block_days=7),standardized_means(df)

def chart(fig,height=340):
    fig.update_layout(template='plotly_white',height=height,margin=dict(l=16,r=16,t=20,b=16),
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Microsoft YaHei, sans-serif',color='#31475B'),
                      legend=dict(orientation='h',y=1.12,title=None))
    st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False})

def csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8-sig')

try:
    db=get_db(); meta=get_metadata(db)
except Exception:
    st.error('无法连接项目数据库。请先运行 start-project.cmd；首次配置请参阅 README。')
    st.stop()
if not meta['rows']:
    st.info('数据库暂无交易，请先执行数据导入。')
    st.stop()

st.sidebar.title('分析范围')
st.sidebar.caption('统一筛选，同步更新全部指标与图表')
start=st.sidebar.date_input('开始日期',meta['start'],min_value=meta['start'],max_value=meta['end'])
end=st.sidebar.date_input('结束日期',meta['end'],min_value=meta['start'],max_value=meta['end'])
cities=st.sidebar.multiselect('门店城市',meta['city'],default=meta['city'])
customer_types=st.sidebar.multiselect('客户类型',meta['customer_type'],default=meta['customer_type'])
categories=st.sidebar.multiselect('商品类别',meta['product_line'],default=meta['product_line'])
st.sidebar.markdown('---')
st.sidebar.caption('样例数据 · 2021 年 1—3 月\n\nA / Yangon · B / Mandalay · C / Naypyitaw')
if start>end:
    st.warning('开始日期不能晚于结束日期，请调整分析范围。')
    st.stop()

st.markdown('<div class="eyebrow">RETAIL ANALYTICS / 门店经营观察</div>',unsafe_allow_html=True)
st.title('零售门店经营分析与交互式看板')
st.caption(f'{start:%Y.%m.%d} — {end:%Y.%m.%d}  ·  {len(cities)} 家门店  ·  销售表现、差异来源与统计不确定性')
try:
    frames={name:get_query(db,name,start,end,tuple(cities),tuple(customer_types),tuple(categories))
            for name in ['kpis','stores','daily','categories','store_categories','monthly','details']}
except Exception:
    st.error('数据库查询失败，请检查 MySQL 是否运行，然后重新加载页面。')
    st.stop()
kpi=frames['kpis'].iloc[0]
if int(kpi.transactions)==0:
    st.info('当前筛选没有交易记录，请扩大日期范围或重新选择门店、客户类型和商品类别。')
    st.stop()
calendar_days=(end-start).days+1
cards=[('销售额',f'{kpi.revenue:,.2f}'),('交易笔数',f'{kpi.transactions:,.0f}'),
       ('商品件数',f'{kpi.units:,.0f}'),('平均交易金额',f'{kpi.average_transaction:,.2f}'),
       ('日均销售额',f'{kpi.revenue/calendar_days:,.2f}'),('平均评分',f'{kpi.average_rating:.2f}')]
for col,(label,value) in zip(st.columns(6),cards):
    col.metric(label,value)
st.caption(f'金额沿用样例数值；日均销售额 ÷ {calendar_days} 个日历日。筛选范围有交易记录的日期共 {int(kpi.observed_days)} 天。')

overview,comparison,inference=st.tabs(['经营总览','门店差异','统计与数据'])
stores=frames['stores'].copy()
stores['revenue_per_calendar_day']=stores.revenue/calendar_days
details=frames['details']

with overview:
    leader=stores.iloc[0]
    st.info(f'样本观察：{leader.city} 销售额最高，为 {leader.revenue:,.2f}，占当前范围 {leader.revenue_share:.1%}。进一步在“门店差异”中拆解交易笔数和平均交易金额。')
    left,right=st.columns([1.7,1])
    with left:
        st.subheader('销售额随日期如何变化')
        daily=frames['daily'].groupby('sale_date').revenue.sum().reindex(pd.date_range(start,end),fill_value=0)
        fig=go.Figure()
        fig.add_scatter(x=daily.index,y=daily.values,name='每日销售额',mode='lines',line=dict(color='#85B8B1',width=1.5))
        fig.add_scatter(x=daily.index,y=daily.rolling(7,min_periods=7).mean(),name='7日移动平均',mode='lines',line=dict(color='#177B70',width=3))
        fig.update_yaxes(title='金额');chart(fig)
        st.caption('无样本交易日期补 0，仅表示该日未记录交易；不等于门店实际停业。')
    with right:
        st.subheader('哪些品类贡献销售额')
        fig=px.bar(frames['categories'].sort_values('revenue'),x='revenue',y='product_line',orientation='h',
                   color_discrete_sequence=['#177B70'],labels=LABELS,hover_data={'revenue_share':':.1%'})
        chart(fig)
    st.subheader('城市 × 商品类别：销售额分布')
    heat=frames['store_categories'].pivot(index='city',columns='product_line',values='revenue').fillna(0)
    fig=go.Figure(go.Heatmap(z=heat.values,x=heat.columns,y=heat.index,colorscale='Teal',
                             texttemplate='%{z:,.0f}',hovertemplate='%{y}<br>%{x}<br>销售额 %{z:,.2f}<extra></extra>',colorbar=dict(title='金额')))
    chart(fig,280)
    st.subheader('门店指标明细')
    st.dataframe(stores.rename(columns=LABELS),use_container_width=True,hide_index=True)
    st.download_button('下载当前门店指标 CSV',csv_bytes(stores),'store-metrics.csv','text/csv')

with comparison:
    st.subheader('销售额差异来自哪里')
    if len(stores)<2:
        st.info('至少选择两家有交易记录的门店，才能比较门店差异。')
    else:
        c1,c2=st.columns(2)
        a=c1.selectbox('比较门店 A',stores.city.tolist(),index=0)
        b=c2.selectbox('基准门店 B',[x for x in stores.city if x!=a])
        decomposition=decompose(stores,a,b)
        st.markdown(f'**{a} − {b}：销售额相差 {decomposition["difference"]:,.2f}**')
        fig=go.Figure(go.Waterfall(x=['交易笔数项','平均交易金额项','销售额差异'],measure=['relative','relative','total'],
                                  y=[decomposition['transactions_effect'],decomposition['average_transaction_effect'],0],
                                  text=[f"{decomposition[k]:+,.2f}" for k in ['transactions_effect','average_transaction_effect','difference']],
                                  textposition='outside',increasing=dict(marker=dict(color='#177B70')),
                                  decreasing=dict(marker=dict(color='#C77356')),totals=dict(marker=dict(color='#31475B'))))
        endpoints=[0,decomposition['transactions_effect'],decomposition['difference']]
        padding=max((max(endpoints)-min(endpoints))*.20,1)
        fig.update_yaxes(range=[min(endpoints)-padding,max(endpoints)+padding])
        chart(fig)
        st.caption('对称分解：笔数差 × 两店平均交易金额的均值 + 均价差 × 两店交易笔数的均值。这是算术分解，不是因果贡献。')
    st.subheader('交易金额的分布与月份稳定性')
    l,r=st.columns(2)
    with l:
        chart(px.box(details,x='city',y='total',color='city',points='outliers',color_discrete_map=CITY_COLORS,
                     labels={'city':'门店城市','total':'交易金额'}))
    with r:
        chart(px.line(frames['monthly'],x='month',y='average_transaction',color='city',markers=True,
                      color_discrete_map=CITY_COLORS,labels={**LABELS,'month':'月份'}))
    st.caption('3 月只到 30 日，因此不将总额比较解读为完整月份的环比增长。')
    st.subheader('统一品类构成后，差异是否仍在')
    standardized,threshold=standardized_means(details)
    st.dataframe(standardized.rename(columns={'city':'门店城市','raw_mean':'原始均值','median':'中位数','transactions':'交易笔数',
                      'standardized_mean':'统一品类权重均值','mean_without_top_1pct':'去除最高1%后的均值'}),use_container_width=True,hide_index=True)
    st.caption(f'统一权重来自当前范围内各品类交易占比；缺少某品类的门店显示为空。最高 1% 敏感性阈值为 {threshold:,.2f}，仅在此项分析中排除大额交易。')

with inference:
    st.subheader('平均交易金额差异：95% 置信区间')
    ci,block,_=statistics(details)
    eligible=ci[ci.status=='ok']
    if eligible.empty:
        st.info('当前范围不足以形成稳定比较：需要至少两家门店，每家至少 30 笔交易、14 个有交易日期。')
    else:
        fig=go.Figure()
        for row in eligible.itertuples():
            label=f'{row.city_a} − {row.city_b}'
            fig.add_scatter(x=[row.ci_low,row.ci_high],y=[label,label],mode='lines',showlegend=False,line=dict(color='#177B70',width=5))
            fig.add_scatter(x=[row.difference],y=[label],mode='markers',showlegend=False,marker=dict(color='#233D55',size=11),
                           hovertemplate=f'均值差 {row.difference:.2f}<br>95% 区间 [{row.ci_low:.2f}, {row.ci_high:.2f}]<extra></extra>')
        fig.add_vline(x=0,line_dash='dash',line_color='#9AA9B6')
        fig.update_xaxes(title='门店 A − 门店 B 的平均交易金额差异')
        chart(fig,300)
        for row in eligible.itertuples():
            message='区间包含 0，差异方向仍不确定' if row.ci_low<=0<=row.ci_high else '区间未包含 0，提示样本中的差异'
            st.write(f'{row.city_a} − {row.city_b}：**{row.difference:+.2f}**，95% 区间 [{row.ci_low:.2f}, {row.ci_high:.2f}]；{message}。')
    if not ci.empty and (ci.status!='ok').any():
        st.caption('部分门店样本量不足，未绘制其置信区间。')
    with st.expander('统计方法与敏感性结果'):
        st.write('以共同日期为簇联合重抽样，保留同日门店间关联；5000 次，固定种子 20260907，采用百分位区间。各日期簇近似独立是主分析假设。')
        st.write('下表使用 7 日循环移动块作为时间相关的敏感性检查。逐对区间未做多重比较校正；结果用于探索，不能推断门店经营措施的因果效果。')
        st.dataframe(block,use_container_width=True,hide_index=True)
    st.download_button('下载当前 Bootstrap 结果 CSV',csv_bytes(ci),'bootstrap-results.csv','text/csv')
    st.subheader('数据质量与下载')
    with db.connect() as conn:
        imported=conn.execute(text('SELECT row_count,source_sha256,imported_at,quality_report FROM dataset_imports')).mappings().one()
    quality=json.loads(imported['quality_report']) if isinstance(imported['quality_report'],str) else imported['quality_report']
    st.success(f'全量源数据检查通过：{imported["row_count"]} 条记录，{quality["invalid_rows"]} 条校验失败记录。导入时间：{imported["imported_at"]}。')
    with st.expander('查看全量质量检查规则'):
        st.dataframe(pd.DataFrame(list(quality['checks'].items()),columns=['检查项','问题记录数']),use_container_width=True,hide_index=True)
        st.caption('此处为全量导入质量检查，不随筛选改变；没有自动删除原始交易。')
    st.download_button('下载当前交易明细 CSV',csv_bytes(details),'filtered-transactions.csv','text/csv')
    report_path=REPORTS/'经营分析报告.md'
    if report_path.exists():
        st.download_button('下载完整样本分析报告',report_path.read_bytes(),'retail-analysis-report.md','text/markdown')
    st.caption('样本无稳定客户 ID，不计算复购、留存和 RFM；成本定义未核实，不推导经营利润。数据与灵感来源：Sven-Bo/streamlit-sales-dashboard；本项目自主实现数据库流程、统计分析与新看板。')
