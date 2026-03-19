# 自动数据同步功能

**创建日期**: 2026-03-05  
**版本**: v2.0（增量同步）

---

## 📋 功能说明

每日自动同步 A 股数据到本地数据库，确保分析时使用最新数据。
采用**三段式定时任务**，覆盖盘前、盘后、晚间三个时间节点。

### 定时任务总览

| 时间 | 任务 | 内容 |
|------|------|------|
| **08:30** 盘前 | `morning_sync.sh` | 股票列表更新（新股/退市）、个股新闻、个股事件 |
| **08:45** 盘前 | **钉钉推送** | **📩 开盘预判消息（基于昨日数据）** |
| **15:30** 盘后 | `daily_sync.sh` | 大盘指数、板块排名、资金流向、市场情绪、全量K线、基本信息 |
| **15:35** 盘后 | **钉钉推送** | **📩 收盘复盘消息（基于当天数据）** |
| **18:00** 晚间 | `dragon_tiger_sync.sh` | 龙虎榜数据（交易所 17:00 后披露） |
| **22:00** 夜间 | `catch_up_sync.sh` | 数据完整性检查与补偿同步 |

### 各任务详细内容

#### 盘前同步（08:30）
| 内容 | 说明 |
|------|------|
| 股票列表 (stock_info) | 检测新股上市/退市，更新市值等财务指标 |
| 个股新闻 (stock_news) | 前 500 只按市值，每只 5 条 + 财联社电报 100 条 |
| 个股事件 (stock_events) | 业绩预告/快报/分红/解禁/回购（自动推算当前报告期） |

#### 收盘后主同步（15:30）
| 内容 | 说明 |
|------|------|
| 大盘指数 (index_daily) | 上证/深证/创业板等主要指数 |
| 市场统计 (market_stats) | 涨跌家数、成交额等 |
| 板块排名 (sector_ranking) | 行业板块 + 概念板块 |
| 资金流向 (capital_flow) | 北向资金、融资融券、主力资金 |
| 市场情绪 (sentiment) | 涨停/跌停/炸板/封板率 |
| 全量K线 (stock_daily) | **全量 5,500+ 只股票**，近 5 日强制刷新，含换手率（东财数据源） |
| 基本信息 (stock_info) | 市值/PE/PB 等实时指标（周一含行业+概念全量更新） |

#### 龙虎榜同步（18:00）
| 内容 | 说明 |
|------|------|
| 龙虎榜 (capital_flow) | 当日龙虎榜明细（交易所延迟披露） |

---

## ⏰ Launchd 配置

本项目使用 macOS 的 **launchd** 系统来管理定时任务（替代传统的 cron）。

### 定时任务配置文件

所有任务配置文件位于 `~/Library/LaunchAgents/`:

| 任务 | 配置文件 | 执行时间 |
|------|----------|----------|
| 盘前数据同步 | `com.stock.analysis.morning.plist` | 工作日 08:30 |
| 盘前消息推送 | `com.stock.analysis.premarket.plist` | 工作日 08:45 |
| 收盘后主同步 | `com.stock.analysis.daily.plist` | 工作日 15:30 |
| 盘后消息推送 | `com.stock.analysis.postmarket.plist` | 工作日 15:35 |
| 龙虎榜同步 | `com.stock.analysis.dragon-tiger.plist` | 工作日 18:00 |
| 数据补偿同步 | `com.stock.analysis.catchup.plist` | 工作日 22:00 |

### 安装/卸载定时任务

```bash
# 安装所有定时任务
bash scheduler/install.sh

# 卸载所有定时任务
bash scheduler/uninstall.sh
```

### 查看定时任务状态

```bash
# 列出所有股票分析相关的 launchd 任务
launchctl list | grep com.stock.analysis

# 查看特定任务状态
launchctl list com.stock.analysis.daily

# 查看任务日志
tail -f logs/launchd_*.log
```

### 手动加载/卸载单个任务

```bash
# 加载任务
launchctl load ~/Library/LaunchAgents/com.stock.analysis.daily.plist

# 卸载任务
launchctl unload ~/Library/LaunchAgents/com.stock.analysis.daily.plist
```

---

## 🚀 使用方法

### 1. 手动执行同步

```bash
cd ~/.openclaw/workspace/skills/a-stock-analysis
bash scripts/daily_sync.sh
```

### 2. 验证同步结果

```bash
python3 scripts/verify_sync.py
```

### 3. 查看日志

```bash
# 最新同步日志
tail -f logs/daily_sync_*.log

# 定时任务日志
tail -f logs/cron_sync.log
```

---

## 📁 文件说明

| 文件 | 用途 |
|------|------|
| `scripts/daily_sync.sh` | 主同步脚本（Shell） |
| `scripts/verify_sync.py` | 验证脚本（Python） |
| `scripts/sync_stock_daily.py` | K 线同步（已有） |
| `scripts/sync_stock_news.py` | 新闻同步（已有） |
| `scripts/sync_stock_events.py` | 事件同步（已有） |
| `scripts/sync_stock_info.py` | 基本信息同步（已有） |
| `data/market.db` | SQLite 数据库 |
| `logs/daily_sync_*.log` | 同步日志 |

---

## ✅ 验证标准

验证脚本会检查：

1. **数据量**
   - 个股基本信息 ≥ 5,000 条
   - 个股 K 线 ≥ 300,000 条
   - 个股新闻 ≥ 100 条
   - 个股事件 ≥ 1,000 条

2. **数据时效性**
   - 抽样检查 5 只股票的最新交易日数据
   - 必须包含昨日或今日数据

3. **数据库健康**
   - 数据库文件大小正常
   - 无损坏表

---

## 🔧 自定义配置

### 修改同步股票数量

编辑 `scripts/daily_sync.sh`:
```bash
# 默认同步前 200 只
python3 scripts/sync_stock_daily.py --top 200 --days 60

# 改为同步前 500 只
python3 scripts/sync_stock_daily.py --top 500 --days 60
```

### 修改同步时间

编辑对应的 `.plist` 文件修改执行时间：

```bash
# 例如修改盘后同步时间为 16:00
vim ~/Library/LaunchAgents/com.stock.analysis.daily.plist

# 修改 <key>Hour</key> 和 <key>Minute</key> 的值
# <integer>15</integer> → <integer>16</integer>
# <integer>30</integer> → <integer>0</integer>

# 卸载后重新加载任务
launchctl unload ~/Library/LaunchAgents/com.stock.analysis.daily.plist
launchctl load ~/Library/LaunchAgents/com.stock.analysis.daily.plist
```

### 禁用定时任务

```bash
# 卸载特定任务（例如盘后同步）
launchctl unload ~/Library/LaunchAgents/com.stock.analysis.daily.plist

# 或卸载所有任务
bash scheduler/uninstall.sh
```

---

## 📊 数据库查询示例

```bash
# 进入数据库
sqlite3 ~/.openclaw/workspace/skills/a-stock-analysis/data/market.db

# 查询某只股票最近 10 天 K 线（含换手率）
SELECT date, close, change_pct, turnover_rate FROM stock_daily 
WHERE code='600403' ORDER BY date DESC LIMIT 10;

# 查询某只股票基本信息
SELECT code, name, industry, total_market_cap_yi FROM stock_info 
WHERE code='600403';

# 查询某只股票最近新闻
SELECT date, type, title FROM stock_news 
WHERE code='600403' ORDER BY date DESC LIMIT 10;

# 查询某日所有限售解禁
SELECT code, detail_json FROM stock_events 
WHERE event_type='unlock' AND date='2026-03-05';
```

---

## ⚠️ 注意事项

1. **首次运行较慢**：全量同步约需 5-10 分钟
2. **网络依赖**：需要访问东方财富/新浪/腾讯/同花顺 API
3. **磁盘空间**：数据库约 300-500 MB
4. **交易日判断**：launchd 配置为工作日执行，但无法自动判断节假日

---

## 🐛 故障排查

### 问题 1: 同步失败

```bash
# 查看日志
tail -100 logs/daily_sync_*.log

# 手动测试
python3 scripts/sync_stock_daily.py --top 10 --days 5
```

### 问题 2: 数据缺失

```bash
# 验证数据
python3 scripts/verify_sync.py

# 强制重新同步某只股票
python3 scripts/sync_stock_daily.py --codes 600403 --force
```

### 问题 3: 定时任务未执行

```bash
# 检查 launchd 服务状态
sudo launchctl list | grep com.stock.analysis

# 查看特定任务状态
launchctl print gui/$(id - u)/com.stock.analysis.daily

# 查看 launchd 日志
log show --predicate 'process == "launchd"' --last 1h | grep com.stock.analysis

# 查看任务输出日志
tail -f logs/launchd_*.log
```

---

## 📝 更新日志

- **2026-03-05**: 初始版本，支持自动同步 + 验证

---

**OpenClaw Contributor | 2026-03-05** 📈
