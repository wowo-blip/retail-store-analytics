# 数据来源、许可与处理口径

## 官方来源

- 数据集：Online Retail II
- 发布方：UCI Machine Learning Repository
- 创建者：Daqing Chen
- 数据集页面：https://archive.ics.uci.edu/dataset/502/online+retail+ii
- DOI：https://doi.org/10.24432/C5CG6D
- 许可证：Creative Commons Attribution 4.0 International（CC BY 4.0）
- 官方下载：https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip
- 固定 ZIP SHA-256：`572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`
- 解压后 Excel SHA-256：`bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`

建议引用：Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D

CC BY 4.0 允许共享和改编，但必须给出适当署名。仓库代码采用 MIT 许可证；UCI 原始数据和处理后 Parquet 仍按 CC BY 4.0 归属原数据创建者，不由本项目重新授权。

## 文件保留策略

- `scripts/download_data.py` 从 UCI 官方地址下载 ZIP 并验证固定哈希。
- `data/raw/online_retail_II.xlsx` 是本地构建输入，不提交 Git。
- `data/processed/retail_lines.parquet` 是可审计的处理后快照，使用 Zstandard 压缩并保留原始行定位、异常标记和交易分类。
- 原始 ZIP 保存在 `.runtime/`，不提交 Git。

## 原字段与处理字段

| UCI 字段 | 项目字段 | 含义 |
|---|---|---|
| Invoice | invoice_id | 发票号；以 C 开头通常表示取消 |
| StockCode | stock_code | 商品或费用代码，统一去空格并转大写 |
| Description | description | 商品描述，允许缺失 |
| Quantity | quantity | 行项目数量；负数作为退货信号 |
| InvoiceDate | invoice_at | 发票日期和时间，无时区信息 |
| Price | unit_price | 单价，单位为英镑 |
| Customer ID | customer_id | 匿名客户 ID，允许缺失 |
| Country | country | 客户所在国家或地区 |
| 衍生字段 | line_amount | `quantity × unit_price`，保留正负号 |
| 衍生字段 | transaction_type | `sale`、`return` 或 `excluded` |

## 经营指标分类

- `sale`：结构字段有效、非重复、描述存在、价格为正、数量为正，且发票号不是取消单。
- `return`：满足同样质量条件，但数量为负或发票号以 C 开头。
- `excluded`：完全重复、描述缺失、价格非正或结构字段无效。原行仍保留在 Parquet/MySQL，经营汇总时排除。
- 邮费、银行费用等服务代码保留在财务总额，但从商品排行榜剔除。
- 缺失客户 ID 的有效交易保留在收入指标中，但不进入 RFM、复购和 cohort 留存分析。

## 固定版本质量画像

- 原始行：1,067,371
- 工作表内及跨工作表完全重复：34,335
- 缺失商品描述：4,382
- 缺失客户 ID：243,007
- 非正价格：6,207
- 取消标记行：19,494
- 负数量行：22,950
- 最终销售行：1,007,913
- 最终退货行：19,104
- 最终排除行：40,354

这些不是被隐藏的“脏数据清洗成果”，而是公开的数据口径和可审计决策。数据期为 2009-12-01 至 2011-12-09，代表一家英国非门店零售商的历史样本，不代表当前行业水平。
