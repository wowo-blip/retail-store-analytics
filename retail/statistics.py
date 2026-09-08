"""退货不确定性、RFM 分层、留存矩阵与客户集中度。"""
import numpy as np
import pandas as pd


def wilson_interval(successes,trials,z=1.959963984540054):
    successes=np.asarray(successes,dtype=float)
    trials=np.asarray(trials,dtype=float)
    proportion=np.divide(successes,trials,out=np.full_like(successes,np.nan),where=trials>0)
    denominator=1+z*z/trials
    center=(proportion+z*z/(2*trials))/denominator
    margin=z*np.sqrt((proportion*(1-proportion)+z*z/(4*trials))/trials)/denominator
    return center-margin,center+margin


def add_return_intervals(countries):
    result=countries.copy()
    result['commercial_invoices']=result.sales_orders+result.return_orders
    result['return_invoice_share']=result.return_orders/result.commercial_invoices.replace(0,np.nan)
    low,high=wilson_interval(result.return_orders,result.commercial_invoices)
    result['return_share_low']=low
    result['return_share_high']=high
    result['return_value_rate']=result.returns_value/result.gross_sales.replace(0,np.nan)
    return result


def rfm_segments(customers,analysis_end):
    result=customers.copy()
    result['recency_days']=(pd.Timestamp(analysis_end)-result.last_purchase_at.dt.normalize()).dt.days
    result['frequency']=result.sales_orders
    result['monetary']=result.net_revenue
    if len(result)<5:
        result[['r_score','f_score','m_score']]=np.nan
        result['segment']='样本不足'
        return result
    result['r_score']=pd.qcut(result.recency_days.rank(method='first'),5,labels=[5,4,3,2,1]).astype(int)
    result['f_score']=pd.qcut(result.frequency.rank(method='first'),5,labels=[1,2,3,4,5]).astype(int)
    result['m_score']=pd.qcut(result.monetary.rank(method='first'),5,labels=[1,2,3,4,5]).astype(int)
    conditions=[
        (result.r_score>=4)&(result.f_score>=4)&(result.m_score>=4),
        (result.f_score>=4)&(result.r_score>=3),
        (result.r_score<=2)&(result.f_score>=3),
        (result.r_score>=4)&(result.f_score<=2),
        result.r_score>=3,
    ]
    result['segment']=np.select(
        conditions,['高价值活跃','忠诚客户','高价值流失风险','新近客户','潜力客户'],
        default='沉睡/低频',
    )
    return result


def cohort_retention(cohorts,analysis_end):
    if cohorts.empty:
        return pd.DataFrame(),pd.DataFrame()
    counts=cohorts.pivot(index='cohort_month',columns='month_number',values='active_customers')
    counts=counts.reindex(columns=range(int(cohorts.month_number.max())+1))
    end_period=pd.Timestamp(analysis_end).to_period('M')
    for cohort in counts.index:
        observable=end_period-pd.Timestamp(cohort).to_period('M')
        observable=observable.n
        counts.loc[cohort,counts.columns<=observable]=counts.loc[cohort,counts.columns<=observable].fillna(0)
    sizes=counts[0].replace(0,np.nan)
    retention=counts.div(sizes,axis=0)
    return counts,retention


def customer_concentration(customers,top_fraction=.10):
    positive=customers[customers.net_revenue>0].sort_values('net_revenue',ascending=False)
    if positive.empty:
        return {'customers':0,'top_customers':0,'top_share':np.nan,'repeat_customer_rate':np.nan}
    top=max(1,int(np.ceil(len(positive)*top_fraction)))
    return {
        'customers':len(positive),'top_customers':top,
        'top_share':float(positive.head(top).net_revenue.sum()/positive.net_revenue.sum()),
        'repeat_customer_rate':float((positive.sales_orders>=2).mean()),
    }
