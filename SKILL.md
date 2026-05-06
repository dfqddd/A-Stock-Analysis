---
name: a-stock-analysis
version: "1.0.0"
description: "A股盘面综合分析工具。基于AKShare的中短线/趋势/波段分析，覆盖大盘环境、板块轮动、涨停情绪、市场情绪、个股技术面(均线/量价)、近3天趋势对比。适用于盘前策略制定、盘中快速扫描、盘后复盘总结。当用户提到：复盘、盘面分析、今天行情怎么样、板块轮动、涨停分析、市场情绪、个股分析、消息面等关键词时触发。注意：资金流向(北向/龙虎榜/主力)数据当前不更新，分析时跳过该维度。"
tags:
  - "股票分析"
  - "A股"
  - "盘面分析"
  - "技术分析"
  - "资金流向"
  - "市场情绪"
  - "龙虎榜"
  - "板块轮动"
  - "数据同步"
  - "定时任务"
author:
  name: "OpenClaw Contributor"
  email: "contributor@example.com"
metadata:
  openclaw:
    emoji: "📈"
    requires:
      bins: ["python3"]
    examples:
      - query: "帮我复盘今天的行情"
        response: "好的,我来帮你分析今天的市场情况..."
      - query: "分析下今天的大盘环境"
        response: "让我查看今天的大盘数据..."
      - query: "北向资金今天怎么样"
        response: "正在查询北向资金流向..."
      - query: "今天涨停板情况如何"
        response: "让我分析今天的涨停数据..."
      - query: "查看贵州茅台的技术面"
        response: "正在分析贵州茅台的技术指标..."
---

# A股盘面综合分析 - OpenClaw Skill

> 📈 **OpenClaw AI 助手的 A 股市场分析技能**

这是一个部署在 OpenClaw AI 助手框架中的专业 A 股盘面分析技能,提供完整的数据采集、分析和推送功能。

## 🎯 使用场景

### 场景一:盘后复盘

**用户**: "帮我复盘今天的行情"

**AI 助手**: 
```
好的,我来为你分析今天的市场情况。

[调用 python -m a_stock analyze daily-review]

📊 今日市场概览:
- 上证指数收于 3XXX.XX 点,涨幅 +X.XX%
- 两市成交额 X.XX 万亿,量能对比近3天...
- 涨跌家数: 上涨 XXXX 家,下跌 XXX 家

🔥 板块轮动:
- 领涨板块: 半导体(+X.XX%)、人工智能(+X.XX%)
- 资金流入: 半导体净流入 XX 亿

💰 资金面:
- 北向资金净流入 XX 亿
- 龙虎榜机构净买入...

🎯 市场情绪:
- 涨停 XX 只,最高连板 X 板
- 封板率 XX%,情绪处于...

📈 操作建议: ...
```

### 场景二:盘中快速扫描

**用户**: "北向资金今天怎么样"

**AI 助手**:
```
让我查询今天的北向资金流向。

[调用 python -m a_stock analyze capital-flow]

💰 今日北向资金:
- 净流入: XX.XX 亿
- 沪股通: XX.XX 亿
- 深股通: XX.XX 亿

📊 近3日趋势:
- 3月10日: +XX 亿
- 3月9日: -XX 亿  
- 3月8日: +XX 亿

💡 分析: 北向资金连续2日净流入,显示外资态度偏积极...
```

### 场景三:个股技术分析

**用户**: "分析下贵州茅台的技术面"

**AI 助手**:
```
让我分析贵州茅台(600519)的技术指标。

[调用 python -m a_stock analyze hot-stocks]

📈 贵州茅台技术分析:
- 当前价: XXXX.XX 元
- 5日均线: XXXX.XX 元 (多头排列)
- 10日均线: XXXX.XX 元
- 20日均线: XXXX.XX 元

📊 量价分析:
- 今日放量上涨,成交额 XX 亿
- 换手率 X.XX%
- 量价配合良好,资金流入 XX 亿

🎯 技术判断:
- 短期趋势: 向上
- 支撑位: XXXX 元
- 压力位: XXXX 元

💡 操作建议: ...
```

### 场景四:板块轮动分析

**用户**: "今天哪些板块表现好"

**AI 助手**:
```
让我查看今天的板块表现。

[调用 python -m a_stock analyze sector]

🔥 今日领涨板块:

行业板块 TOP10:
1. 半导体 (+X.XX%) - 领涨股: XXX
2. 人工智能 (+X.XX%) - 领涨股: XXX
3. 新能源汽车 (+X.XX%) - 领涨股: XXX

概念板块 TOP10:
1. ChatGPT (+X.XX%) - 领涨股: XXX
2. 芯片 (+X.XX%) - 领涨股: XXX

📊 板块资金流:
- 半导体净流入 XX 亿
- 人工智能净流入 XX 亿

💡 分析: 科技板块持续领涨,资金集中流入半导体和AI方向...
```

### 场景五:市场情绪判断

**用户**: "今天涨停板情况如何"

**AI 助手**:
```
让我分析今天的涨停数据。

[调用 python -m a_stock analyze sentiment]

🎯 今日涨停分析:

涨停统计:
- 涨停总数: XX 只
- 自然涨停: XX 只
- 一字板: XX 只
- 连板股: XX 只

🔥 连板梯队:
- X 板: XXX (XX行业)
- X 板: XXX (XX行业)

📊 情绪指标:
- 封板率: XX%
- 炸板率: XX%
- 最高连板: X 板

💡 市场情绪: 当前处于发酵期,封板率较高,赚钱效应良好...
```

## ✨ 核心功能

基于 AKShare 的 A 股中短线/趋势/波段盘面分析工具，覆盖 7 大分析维度，所有数据输出为结构化 JSON。

## 依赖安装

```bash
pip install akshare pandas
```

## 分析维度

所有分析模块位于 `a_stock/analysis/` 下,可通过 `python -m a_stock analyze <command>` 调用:

| 命令 | 模块 | 核心内容 |
|------|------|----------|
| `overview` | `market_overview.py` | 三大指数、量能、涨跌家数、涨停跌停、近3天对比 |
| `sector` | `sector_analysis.py` | 行业/概念板块排名、资金流向、连续性分析 |
| `capital-flow` | `capital_flow.py` | 北向资金、主力资金、融资融券、龙虎榜 |
| `sentiment` | `market_sentiment.py` | 连板高度/梯队、封板率、昨涨停表现、炸板率 |
| `hot` | `hot_stocks.py` | 热门股票分析 |
| `daily-review` | `daily_review.py` | 调用全部模块生成综合报告 |

## 数据同步

### 每日自动同步（`scripts/daily_sync.sh`，15:30 盘后）

每个交易日收盘后自动执行,通过 `python -m a_stock.scheduler.tasks daily` 调用,执行完整的 9 步同步流程:

1. 股票基础信息同步
2. 市场统计数据同步
3. 板块排名数据同步
4. 资金流向数据同步
5. 市场情绪数据同步
6. 个股资金流数据同步
7. 板块资金流数据同步
8. 涨停数据同步
9. 日K数据同步
10. 龙虎榜数据同步

生成的报告可选择性发送钉钉通知。

### 龙虎榜同步（`scripts/dragon_tiger_sync.sh`，18:00）

交易日 18:00 自动执行，同步当日龙虎榜数据：

- 交易所收盘后披露（约 17:00-17:30）
- 包含营业部买卖明细
- 机构席位资金流向分析

### 补偿同步（`scripts/catch_up_sync.sh`，22:00 执行）

每天晚上 22:00 自动执行，包含以下功能：

1. **数据完整性检查**：检查 13 个核心数据表的数据完整性
   - market_stats, sector_ranking, capital_flow, sentiment
   - stock_fund_flow, sector_fund_flow, limit_up_detail
   - stock_daily, dragon_tiger, abnormal_movement
   - stock_hot_ranking, stock_news, stock_events

2. **自动补偿**：发现缺失数据时自动触发补偿同步

3. **钉钉告警**：同步失败或数据缺失时发送告警通知

4. **开机自启备份**：macOS 开机时也会检查，如果距上次成功同步超过 20 小时，自动补执行

### 数据同步模块

所有同步模块位于 `a_stock/sync/` 下，可通过 `python -m a_stock sync <command>` 调用：

| 命令 | 模块 | 核心内容 |
|------|------|----------|
| `stock-info` | `stock_info.py` | 全量A股基本信息（行业/概念/市值/PE等） |
| `stock-daily` | `stock_daily.py` | 日K线数据（东财源，含换手率） |
| `stock-fund-flow` | `stock_fund_flow.py` | 个股资金流入/流出/净额（新浪），约5000只 |
| `sector-fund-flow` | `sector_fund_flow.py` | 行业板块净流入/涨跌家数/领涨股（同花顺） |
| `limit-up` | `limit_up.py` | 涨停池+炸板池合并采集（东财） |
| `dragon-tiger` | `dragon_tiger.py` | 龙虎榜数据（交易所 17:00 后披露） |
| `hot-ranking` | `stock_hot_ranking.py` | 热门股票榜单（东财热度榜前100） |
| `abnormal` | `stock_abnormal_movement.py` | 个股异动监测（价格/成交量/振幅异动） |
| `backfill` | `backfill.py` | 历史数据回填 |
| - | `stock_news.py` | 东财个股新闻 + 财联社电报 |
| - | `stock_events.py` | 业绩预告/快报、分红送转、限售解禁、股票回购 |

## 本地数据库

所有数据缓存在 SQLite 数据库 `data/market.db`，可直接用 `sqlite3` 查询，也可通过 `a_stock.db.cache` 的 Python API 读写。

### 表结构速查

| 表名 | 用途 | 主键/索引 | 核心字段 |
|------|------|-----------|----------|
| `index_daily` | 大盘指数日线 | `(date, code)` | code, name, close, change_pct, volume, amount |
| `market_stats` | 每日市场统计 | `date` | up_count, down_count, limit_up, limit_down, total_amount_yi |
| `sector_ranking` | 板块排名 | `(date, type, rank)` | type(industry/concept), name, change_pct, leading_stock, up_count |
| `capital_flow` | 资金流向 | `date` | north_net_yi, sh_connect_yi, sz_connect_yi, margin_balance_yi, main_flow_json | ⚠️ 数据停更（最新 2026-03-11），查询无意义 |
| `sentiment` | 市场情绪 | `date` | limit_up_total, first_board, continuous_board, max_height, seal_rate, broken_rate, bull_bear_index, fear_greed_index |
| `stock_daily` | 个股日K线 | `(date, code)` | name, open, close, high, low, volume, amount, change_pct, turnover_rate |
| `stock_info` | 个股基本信息 | `code` | name, market, board, industry, concepts(JSON), total_market_cap_yi, pe_ratio, pb_ratio |
| `stock_news` | 个股新闻 | `id` (自增), 唯一索引 `(code, date, title)` | type(news/telegraph), title, content, source, url |
| `stock_events` | 个股重大事件 | `id` (自增), 唯一索引 `(code, date, event_type)` | event_type(forecast/express/dividend/unlock/buyback), detail_json |
| `limit_up_detail` | 涨停股详情 | `(date, code)` | status(limit_up/broken), seal_amount_yi, continuous_board, limit_up_stat, industry |
| `stock_fund_flow` | 个股资金流向 | `(date, code)` | inflow_yi, outflow_yi, net_flow_yi, amount_yi, change_pct | ⚠️ 数据停更（最新 2026-03-11） |
| `sector_fund_flow` | 板块资金流向 | `(date, name)` | net_flow_yi, total_amount_yi, up_count, down_count, leading_stock | ⚠️ 数据停更（最新 2026-03-06） |
| `dragon_tiger` | 龙虎榜数据 | `id` (自增), UNIQUE `(date, code)` | date, code, name, close_price, change_pct, lhb_reason, buy_value, sell_value, net_buy_value | ⚠️ 数据停更（最新 2026-03-11） |
| `stock_hot_ranking` | 热门股票榜单 | `(date, code)` | total_rank, total_score, ths_rank, tgb_rank, dcb_rank, xq_rank, source_count | ⚠️ 偶发更新，不保证当日有数据 |
| `stock_abnormal_movement` | 个股异动 | `id` (自增), UNIQUE `(code, movement_type, enter_date)` | movement_type, stage, enter_date, exit_date, trigger_price, trigger_change, risk_level |

### 常用查询示例

```bash
# 直接 SQL 查询
sqlite3 data/market.db

# 查某只股票最近10天K线（含换手率）
sqlite3 data/market.db "SELECT date, close, change_pct, volume, turnover_rate FROM stock_daily WHERE code='600519' ORDER BY date DESC LIMIT 10"

# 查某只股票基本信息
sqlite3 {baseDir}/data/market.db "SELECT code, name, industry, total_market_cap_yi, pe_ratio FROM stock_info WHERE code='600519'"

# 查某只股票最近新闻
sqlite3 {baseDir}/data/market.db "SELECT date, type, title FROM stock_news WHERE code='600519' ORDER BY date DESC LIMIT 10"

# 查某天所有限售解禁事件
sqlite3 {baseDir}/data/market.db "SELECT code, date, detail_json FROM stock_events WHERE event_type='unlock' AND date='2025-03-10'"

# 按行业查股票
sqlite3 {baseDir}/data/market.db "SELECT code, name, total_market_cap_yi FROM stock_info WHERE industry='半导体' ORDER BY total_market_cap_yi DESC LIMIT 20"

# 按概念查股票（模糊匹配 JSON 数组）
sqlite3 {baseDir}/data/market.db "SELECT code, name FROM stock_info WHERE concepts LIKE '%人工智能%'"

# 查近20天大盘成交额（用于动态分位数计算）
sqlite3 {baseDir}/data/market.db "SELECT date, total_amount_yi FROM market_stats ORDER BY date DESC LIMIT 20"

# 查近20天北向资金净流入
sqlite3 {baseDir}/data/market.db "SELECT date, north_net_yi FROM capital_flow ORDER BY date DESC LIMIT 20"

# 查近20天连板高度和封板率
sqlite3 {baseDir}/data/market.db "SELECT date, max_height, seal_rate FROM sentiment ORDER BY date DESC LIMIT 20"
```

### Python API（db_cache 模块）

数据库 API 位于 `a_stock/db/cache.py`，主要函数：

```python
from a_stock.db import get_connection, init_db
from a_stock.db.cache import (
    get_cached_stock_daily,
    get_stock_info,
    search_stocks_by_industry,
    get_cached_market_stats,
    get_cached_capital_flow,
    get_cached_sentiment,
    # ... 更多函数
)
```

| 函数 | 用途 |
|------|------|
| `get_cached_stock_daily(code, start_date, end_date)` | 查个股日K线 |
| `get_stock_info(code)` | 查个股基本信息 |
| `search_stocks_by_industry(industry)` | 按行业查股票列表 |
| `get_cached_market_stats(date)` | 查某日市场统计 |
| `get_cached_capital_flow(date)` | 查某日资金流向 |
| `get_cached_sentiment(date)` | 查某日市场情绪 |
| `get_cached_sectors(date, type)` | 查某日板块排名 |
| `get_db_stats()` | 数据库统计信息 |

## 使用方法

### 统一入口（推荐）

项目使用 `python -m a_stock` 作为统一入口:

```bash
# 查看帮助
python -m a_stock --help

# 数据同步
python -m a_stock sync --help

# 数据分析
python -m a_stock analyze --help

# 发送通知
python -m a_stock notify --help

# 初始化数据库
python -m a_stock init
```

### 一键复盘（最常用）

```bash
# 盘后完整复盘（含近3天对比）
python -m a_stock analyze daily-review

# 指定日期复盘
python -m a_stock analyze daily-review --date 20260304

# 先同步数据再复盘
python -m a_stock analyze daily-review --sync

# 发送通知
python -m a_stock analyze daily-review --notify
```

### 数据同步

```bash
# 同步股票基本信息
python -m a_stock sync stock-info

# 同步日K线数据
python -m a_stock sync stock-daily

# 同步个股资金流向
python -m a_stock sync stock-fund-flow

# 同步板块资金流向
python -m a_stock sync sector-fund-flow

# 同步涨停数据
python -m a_stock sync limit-up

# 历史数据回填
python -m a_stock sync backfill --year 2024
python -m a_stock sync backfill --all
```

### 数据分析

```bash
# 资金流向分析
python -m a_stock analyze capital-flow

# 市场情绪分析
python -m a_stock analyze sentiment

# 板块轮动分析
python -m a_stock analyze sector

# 市场概览
python -m a_stock analyze overview

# 热门股票
python -m a_stock analyze hot
```

### 定时任务

使用 Shell 脚本执行定时任务:

```bash
# 每日同步（15:30）
bash scripts/daily_sync.sh

# 早盘同步（08:30）
bash scripts/morning_sync.sh

# 补偿同步（开机自启）
bash scripts/catch_up_sync.sh

# 安装定时任务
bash scheduler/install.sh
```

## 分析框架（Checklist）

盘面分析时**必须按顺序完成以下全部维度**，每个维度都必须查数据库并输出分析结论。跳过任何一项都是不完整的分析。

### 1. 大盘环境 ✅必查
- [ ] 查 `index_daily` 表：三大指数收盘、涨跌幅
- [ ] 查 `market_stats` 表：成交额、涨跌家数、涨停跌停数
- [ ] 近3天对比：量能趋势（放量/缩量）、指数趋势（连涨/连跌）
- **结论**：判断今天是赚钱市还是亏钱市

### 2. 板块轮动 ✅必查
- [ ] 查 `sector_ranking` 表：行业板块 top10、概念板块 top10
- [ ] 识别主线（连续3天领涨）vs 一日游
- [ ] 找出板块内涨停数 >5 的强势板块
- **结论**：当日最强方向 + 持续性判断

### 3. 资金面 ⚠️ 数据暂停更新，跳过此维度
> **注意**：以下数据表当前均已停止更新，查询会返回空或过期数据，分析时直接跳过，不要尝试查询：
> - `capital_flow`（北向资金、主力资金、融资融券）：最新数据停留在 2026-03-11
> - `dragon_tiger`（龙虎榜）：最新数据停留在 2026-03-11
> - `stock_fund_flow`（个股资金流）：最新数据停留在 2026-03-11
> - `sector_fund_flow`（板块资金流）：最新数据停留在 2026-03-06
>
> 如用户明确询问资金面，直接告知"资金流向数据暂时无法获取，该维度跳过"。

### 4. 市场情绪 ✅必查
- [ ] 查 `sentiment` 表：连板高度、封板率、炸板率
- [ ] 判断情绪周期阶段（冰点/修复/发酵/高潮/退潮）
- [ ] 近3天对比：情绪升温还是降温
- **结论**：当前风险偏好 + 操作策略建议

### 5. 消息面 ✅必查
- [ ] 查 `stock_news` 表：持仓股相关新闻
- [ ] 国内政策/事件催化
- [ ] 外围市场影响（美股/港股/期货）
- **结论**：有无重大催化或风险事件

### 6. 个股技术面 ✅必查
- [ ] 查 `stock_daily` 表：持仓股近5-10日K线
- [ ] 均线位置（5/10/20日均线）
- [ ] 量价分析（量增价涨/量增价跌/缩量企稳/放量下跌）
- [ ] 关键支撑位和压力位
- **结论**：每只持仓股的技术面判断 + 操作建议

### 7. 综合研判
- [ ] 汇总以上6个维度，给出整体判断
- [ ] 明确操作建议（加仓/减仓/持有/观望）
- [ ] 标注风险点和关注指标

每个维度都结合近 3 天数据做对比，判断趋势是加速、持续还是衰减。

## 判断标准速查

采用**动态分位数 + 绝对参考线**双重判断，适应不同市场阶段：

### 动态判断（基于近20个交易日分位数）

| 指标 | 低迷/弱势 | 正常 | 活跃/强势 | 火热/极端 |
|------|-----------|------|-----------|-----------|
| **量能**（两市成交额） | <P25 | P25~P75 | >P75 | >P90 |
| **北向资金**（单日净流入） | <P25 | P25~P75 | >P75 | >P90 | ⚠️ 数据暂停更新，跳过 |
| **连板高度**（最高连板数） | <P25 | P25~P75 | >P75 | >P90 |
| **封板率** | <P25 | P25~P75 | >P75 | >P90 |

> 分析时先计算近20日该指标的分位数分布，再看当日数据落在哪个区间。例如近20日成交额中位数1.2万亿，则当日1.5万亿处于P80+，判定为"活跃偏火热"。

### 固定比值（不随市场阶段变化）

- **涨跌比**：上涨/下跌 >2 = 普涨，1~2 = 偏强，0.5~1 = 偏弱，<0.5 = 普跌

### 绝对参考线（极端情况兜底）

当动态分位数因近期市场单边运行而失真时，用绝对值辅助修正：

- **量能**：<6000亿 = 极度萎缩（无论分位数如何），>2万亿 = 极度亢奋
- **北向资金**：单日净流出 >100亿 = 恐慌性流出，净流入 >100亿 = 疯狂抢筹
- **连板高度**：≤1 = 绝对冰点（断板），≥8 = 绝对高潮

## 详细参考

- **AKShare API 速查**: 见 `references/akshare_api.md`
- **分析框架详解**: 见 `references/analysis_framework.md`

## 目录结构

```
a-stock-analysis/
├── a_stock/                  # 核心 Python 包
│   ├── __init__.py
│   ├── __main__.py          # 主入口
│   ├── db/                   # 数据库模块
│   │   ├── __init__.py
│   │   └── cache.py         # 数据库缓存
│   ├── sync/                 # 数据同步 (10个模块)
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── stock_info.py    # 股票基本信息
│   │   ├── stock_daily.py   # 日K线数据
│   │   ├── stock_news.py    # 股票新闻
│   │   ├── stock_events.py  # 股票事件
│   │   ├── stock_fund_flow.py    # 个股资金流
│   │   ├── sector_fund_flow.py   # 板块资金流
│   │   ├── limit_up.py      # 涨停数据
│   │   ├── dragon_tiger.py  # 龙虎榜
│   │   └── backfill.py      # 历史数据回填
│   ├── analysis/             # 数据分析 (7个模块)
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── market_overview.py    # 市场概览
│   │   ├── sector_analysis.py    # 板块分析
│   │   ├── capital_flow.py       # 资金流向
│   │   ├── market_sentiment.py   # 市场情绪
│   │   ├── hot_stocks.py         # 热门股票
│   │   └── daily_review.py       # 每日复盘
│   ├── notify/               # 通知推送
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── dingtalk.py      # 钉钉推送
│   └── scheduler/            # 定时任务
│       ├── __init__.py
│       └── tasks.py         # 任务定义
├── scripts/                  # Shell 脚本
│   ├── daily_sync.sh        # 每日同步
│   ├── morning_sync.sh      # 早盘同步
│   └── catch_up_sync.sh     # 补偿同步
├── config/                   # 配置文件
│   ├── config.example.yaml  # 配置模板
│   └── config.yaml          # 用户配置
├── data/                     # SQLite 数据库
│   └── market.db            # 数据库文件
├── logs/                     # 运行日志
├── references/               # 参考文档
│   ├── akshare_api.md
│   └── analysis_framework.md
├── scheduler/                # 定时任务安装
│   └── install.sh
├── .gitignore
├── Makefile
├── requirements.txt
├── install.sh
├── README.md
├── SKILL.md
└── AUTO_SYNC_README.md
```
