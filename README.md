# 零售门店经营分析与交互式看板｜个人项目

围绕“门店销售差异来自哪里、差异有多不确定”构建完整分析流程：**Excel → 数据质量检查 → MySQL → SQL 指标 → 统计分析 → 交互看板 → 报告**。

以 [Sven-Bo 的销售看板](https://github.com/Sven-Bo/streamlit-sales-dashboard)为学习起点，沿用其附带的销售样例数据。本项目重新实现数据库管道、指标 SQL、差异分解、Bootstrap 统计分析、中文看板和验证代码。项目在 AI 编程助手协助下完成，应根据自己理解和实际负责内容介绍。

![经营总览](reports/dashboard-overview.png)

## 已实现

- 自动校验 1000 条交易的缺失、重复编号、数值范围、税额及金额关系；失败时不写业务表。
- MySQL 8.4 专用实例、DECIMAL 金额、数据库事务、来源哈希、重复导入对账；只读看板账户与导入账户分离。
- SQL 聚合、窗口函数排名和品类占比；统一日期/门店/客户类型/品类筛选。
- 6 项 KPI、每日趋势与 7 日均线、城市×品类热力图、交易金额分布和月份比较。
- 销售额对称分解、统一品类权重均值、最高 1% 交易敏感性分析。
- 5000 次共同日期簇 Bootstrap，7 日循环移动块敏感性检查；固定随机种子，样本不足时不输出区间。
- 筛选后 CSV 下载、全样本分析报告、数据字典及自动验证。

技术栈：Python 3.11、Pandas、NumPy、MySQL 8.4、SQLAlchemy、PyMySQL、Plotly、Streamlit、pytest。

## 当前电脑启动

双击 `start-project.cmd`，或运行：

```powershell
.\.venv\Scripts\python.exe scripts\start_local.py
```

打开 http://127.0.0.1:8502 。项目 MySQL 在 127.0.0.1:3307；数据目录为 `.runtime/mysql-data`。双击 `stop-project.cmd` 可停止本项目进程。

完整重算：

```powershell
.\.venv\Scripts\python.exe -m retail.etl
.\.venv\Scripts\python.exe -m retail.report
.\.venv\Scripts\python.exe -m pytest -q
```

## 在另一台 Windows 电脑首次配置

1. 安装 Python 3.11 和 MySQL 8.4，将 `mysqld.exe` 所在 bin 目录加入 PATH。
2. 在本项目目录创建环境并安装已锁定依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts\setup_local.py
.\.venv\Scripts\python.exe scripts\start_local.py
```

脚本要求 3307、8502 可用。首次初始化只针对本项目的新数据目录，并生成本地随机数据库密码。不要提交 `.env`、`.runtime` 或 `.venv`；Git 忽略规则已配置。环境应在目标电脑重建。

## 目录

```text
app.py                    中文交互看板
retail/etl.py              读取、校验、事务导入与对账
retail/queries.py          安全参数绑定与统一查询
retail/statistics.py       差异分解、Bootstrap、敏感性分析
retail/report.py           从数据库生成报告
sql/schema.sql            数据表、约束、索引
sql/metrics.sql           KPI、窗口函数、趋势及明细查询
data/SOURCE.md            数据来源、哈希及数据字典
reports/                  真实运行结果、CSV、报告和截图
scripts/                  数据库配置、启动和停止工具
tests/test_pipeline.py    核心逻辑与只读数据库集成测试
改造操作记录.md           每一步执行内容与命令
docs/                     指标口径、统计方法、简历与面试材料
```

## 分析发现

全样本销售额 322966.7490，1000 笔交易、5510 件商品。Naypyitaw 销售额最高，但其交易笔数少于 Yangon；算术分解显示较高平均交易金额抵消了交易笔数较少的差额。
三组门店均值差的 95% 日期簇 Bootstrap 区间均包含 0，不能凭排名认定门店能力差异。详见 [经营分析报告](reports/经营分析报告.md)。

日均销售额以筛选期日历天数为分母，不是实际营业天数。样本无客户唯一 ID，且仅有约三个月数据，不计算复购、留存、年度季节性或营销 ROI。
来源和成本口径未独立核实，不声称真实业务落地、利润改善或销售增长。统计区间用于探索，未做多重比较校正，也不作因果解释。
