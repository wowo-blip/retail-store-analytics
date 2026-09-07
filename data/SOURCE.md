# 数据来源与保留范围

- 来源仓库：https://github.com/Sven-Bo/streamlit-sales-dashboard
- 来源文件：`supermarkt_sales.xlsx`
- 参考版本：`d436bc8c4fbc6424828adccad792b4f46c2e8a84`
- 本地副本：`data/raw/supermarket_sales.xlsx`
- SHA-256：`345f5ebec9f6a8f681507ed9e6b3ca8655b8c4e0f36a79e5f8603447c495c342`
- 读取区域：Sales 工作表，B:R 列，第 4 行表头、第 5 行起数据；读取所有数据行，当前为 1000 行。

没有更改 Excel 原始值。本文件的日期实际为 2021-01-01 至 2021-03-30，不套用其他同名超市数据集的年份。
把每个唯一 Invoice ID 对应的行视为一笔样例交易；每行只含一个商品类别。无法据此还原多商品购物篮。
样本采集方式、实际币种、成本定义与真实性没有独立确认，项目定位为样例分析，不代表企业实际经营结果。

## 数据字典

| 源字段 | 数据库字段 | 类型 / 口径 |
|---|---|---|
| Invoice ID | invoice_id | 交易编号，主键；不是客户 ID |
| Branch / City | branch / city | 样例门店及城市，A–Yangon、B–Mandalay、C–Naypyitaw |
| Customer_type / Gender | customer_type / gender | 客户类型及样例性别类别 |
| Product line | product_line | 商品类别，共 6 类 |
| Unit price | unit_price | 单价，DECIMAL(12,2) |
| Quantity | quantity | 商品件数，正整数 |
| Tax 5% | tax_amount | 税额，DECIMAL(14,4) |
| Total | total | 交易金额，DECIMAL(14,4)，含源表税额 |
| Date / Time | sale_date / sale_time | DATE / TIME，按样例记录时间处理，无时区换算 |
| Payment | payment | 支付方式 |
| cogs | cogs | 保留源表字段，数值上为单价×数量；不据此认定真实进货成本 |
| gross margin percentage | gross_margin_percentage | 保留源值，本版不用它推导利润 |
| gross income | gross_income | 保留源值，本版不用它推导利润 |
| Rating | rating | 评分，当前观察范围4—10；校验采用0—10规则 |
| 补充元数据 | source_sha256 | 文件版本，用于追溯与防止混合导入 |

基于开源样例进行再开发，README 保留来源。发布或分发前应遵守原项目和数据来源的许可条件；本项目没有擅自给上游数据重新授予许可证。
