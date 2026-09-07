"""探索性统计：共同日期簇重抽样，比较交易金额均值之差。"""
from itertools import combinations
import numpy as np
import pandas as pd


def cluster_bootstrap(df, repetitions=5000, seed=20260907, block_days=1):
    columns = ['city_a','city_b','difference','ci_low','ci_high','n_a','n_b','days','valid_repetitions','status']
    if df.empty:
        return pd.DataFrame(columns=columns)
    daily = df.groupby(['sale_date','city']).total.agg(['sum','count'])
    days = pd.date_range(df.sale_date.min(),df.sale_date.max(),freq='D')
    cities = sorted(df.city.unique())
    amounts = daily['sum'].unstack().reindex(index=days,columns=cities).fillna(0).to_numpy()
    counts = daily['count'].unstack().reindex(index=days,columns=cities).fillna(0).to_numpy()
    rng = np.random.default_rng(seed)
    if block_days == 1:
        weights = rng.multinomial(len(days), np.full(len(days),1/len(days)), size=repetitions)
    else:
        if block_days < 1:
            raise ValueError('block_days must be positive')
        # 循环移动块，保留块内日期相邻性；每次仍抽取同样多的日历日。
        starts = rng.integers(0,len(days),size=(repetitions,int(np.ceil(len(days)/block_days))))
        indices = ((starts[:,:,None]+np.arange(block_days)) % len(days)).reshape(repetitions,-1)[:,:len(days)]
        weights = np.zeros((repetitions,len(days)),dtype=int)
        for i, indices_i in enumerate(indices):
            weights[i] = np.bincount(indices_i,minlength=len(days))
    numerators, denominators = weights @ amounts, weights @ counts
    means = np.divide(numerators,denominators,out=np.full_like(numerators,np.nan),where=denominators>0)
    original = amounts.sum(axis=0)/counts.sum(axis=0)
    results=[]
    for i,j in combinations(range(len(cities)),2):
        sample = means[:,i]-means[:,j]
        sample = sample[np.isfinite(sample)]
        eligible = (counts[:,i]>0).sum()>=14 and (counts[:,j]>0).sum()>=14 and min(counts[:,i].sum(),counts[:,j].sum())>=30 and len(sample)>=0.99*repetitions
        low,high = np.quantile(sample,[.025,.975]) if eligible else [np.nan,np.nan]
        results.append(dict(city_a=cities[i],city_b=cities[j],difference=original[i]-original[j],
                            ci_low=low,ci_high=high,n_a=int(counts[:,i].sum()),n_b=int(counts[:,j].sum()),
                            days=len(days),valid_repetitions=len(sample),status='ok' if eligible else 'insufficient_data'))
    return pd.DataFrame(results,columns=columns)


def decompose(stores, city_a, city_b):
    """A-B 的销售额差异 = 交易笔数项 + 平均交易金额项，使用对称分解。"""
    a=stores.set_index('city').loc[city_a]
    b=stores.set_index('city').loc[city_b]
    count_effect=(a.transactions-b.transactions)*(a.average_transaction+b.average_transaction)/2
    value_effect=(a.average_transaction-b.average_transaction)*(a.transactions+b.transactions)/2
    return dict(difference=float(a.revenue-b.revenue), transactions_effect=float(count_effect),
                average_transaction_effect=float(value_effect))


def standardized_means(df):
    """按合并样本各类别交易占比统一加权；缺失类别时不伪造均值。"""
    weights=df.product_line.value_counts(normalize=True).sort_index()
    table=df.groupby(['city','product_line']).total.mean().unstack().reindex(columns=weights.index)
    weighted=table.mul(weights,axis=1).sum(axis=1,min_count=len(weights))
    result=df.groupby('city').total.agg(raw_mean='mean',median='median',transactions='size')
    result['standardized_mean']=weighted
    threshold=df.total.quantile(.99)
    result['mean_without_top_1pct']=df[df.total<=threshold].groupby('city').total.mean()
    return result.reset_index(),float(threshold)
