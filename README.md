# A 股盘面分析 - OpenClaw Skill

> **OpenClaw AI 助手的 A 股市场分析技能**

这是一个部署在 OpenClaw AI 助手框架中的专业 A 股盘面分析 skill,提供完整的数据采集、分析和推送功能。

---

## 📌 项目定位

### OpenClaw Skill

本项目是一个 **OpenClaw Skill**,位于 OpenClaw workspace 的 `skills` 目录下:

```
~/.openclaw/workspace/skills/a-stock-analysis/
```

作为 OpenClaw 的一个技能模块,它可以:
- 通过 OpenClaw 的 AI 模型进行智能盘面分析
- 使用 OpenClaw 的上下文管理能力存储分析结果
- 集成 OpenClaw 的通知推送功能

### 核心功能

- **数据采集**: 自动同步 A 股行情、资金流向、涨停股、龙虎榜等数据
- **盘面分析**: 大盘环境、板块轮动、资金动向、市场情绪、消息面
- **智能推送**: 支持钉钉等多渠道推送盘前预判、盘中速递、盘后复盘
- **定时任务**: 自动化数据同步和分析推送
- **本地数据库**: SQLite 缓存,支持快速查询和离线分析

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本要求 | 必需 | 说明 |
|------|----------|------|------|
| Python | 3.9+ | ✅ 必需 | 核心运行环境 |
| OpenClaw | 最新版 | ✅ 必需 | AI 助手框架 |

### 安装步骤

```bash
# 1. 进入 skill 目录
cd ~/.openclaw/workspace/skills/a-stock-analysis

# 2. 运行安装脚本
bash install.sh

# 3. 配置钉钉 Webhook(如需推送功能)
cp config/config.example.yaml config/config.yaml
vim config/config.yaml

# 4. 同步初始数据
python3 -m a_stock sync backfill --all

# 5. 测试分析功能
python3 -m a_stock analyze overview

# 6. 安装定时任务（可选）
bash scheduler/install.sh
```

---

## 📖 文档导航

| 文档 | 说明 |
|------|------|
| **[SKILL.md](./SKILL.md)** | 完整的技术文档,包含架构设计、数据库结构、API 说明 |
| **[AUTO_SYNC_README.md](./AUTO_SYNC_README.md)** | 自动数据同步功能说明 |
| **[references/akshare_api.md](./references/akshare_api.md)** | AKShare API 速查手册 |
| **[references/analysis_framework.md](./references/analysis_framework.md)** | 分析框架详解 |

---

## 💡 使用场景

### 1. 日常盘面分析

```bash
# 盘后完整复盘
python3 -m a_stock analyze daily-review

# 大盘环境分析
python3 -m a_stock analyze overview

# 板块轮动分析
python3 -m a_stock analyze sector

# 资金面分析
python3 -m a_stock analyze capital-flow

# 市场情绪分析
python3 -m a_stock analyze sentiment
```

### 2. 与 OpenClaw 集成

作为 OpenClaw skill,你可以通过自然语言与 AI 助手交互:

```
用户: 帮我分析今天的大盘环境
AI: [调用 market_overview.py] 今天大盘收涨,成交额1.2万亿,北向资金净流入50亿...

用户: 查看今天的涨停板情况
AI: [调用 market_sentiment.py] 今天共有30只涨停,最高连板5板,封板率75%...

用户: 分析贵州茅台的技术面
AI: [调用 stock_technical.py] 贵州茅台当前处于5日均线之上,量价配合良好...
```

### 3. 定时推送

配置定时任务后,自动推送:

| 时间 | 任务 | 推送内容 |
|------|------|----------|
| 08:30 | morning | 盘前数据同步 |
| 15:30 | daily | 盘后复盘(完整分析) |
| 18:00 | dragon-tiger | 龙虎榜数据同步 |
| 22:00 | catchup | 数据完整性检查与补偿 |

**22:00 补偿同步机制**：
- 自动检查当日 13 个数据表的完整性
- 发现缺失数据自动触发补偿同步
- 同步失败时发送钉钉告警通知

---

## 🗂️ 项目结构

```
a-stock-analysis/
├── SKILL.md                      # 完整技术文档
├── README.md                     # 本文档
├── AUTO_SYNC_README.md           # 自动同步说明
├── a_stock/                      # Python 包
│   ├── __init__.py
│   ├── __main__.py              # 主入口
│   ├── db/                       # 数据库模块
│   │   ├── __init__.py
│   │   └── cache.py             # 数据库缓存
│   ├── sync/                     # 数据同步
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── stock_info.py
│   │   ├── stock_daily.py
│   │   ├── stock_news.py
│   │   ├── stock_events.py
│   │   ├── stock_fund_flow.py
│   │   ├── sector_fund_flow.py
│   │   ├── limit_up.py
│   │   ├── dragon_tiger.py
│   │   └── backfill.py
│   ├── analysis/                 # 数据分析
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── market_overview.py
│   │   ├── sector_analysis.py
│   │   ├── capital_flow.py
│   │   ├── market_sentiment.py
│   │   ├── hot_stocks.py
│   │   └── daily_review.py
│   ├── notify/                   # 通知推送
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── dingtalk.py          # 钉钉推送
│   └── scheduler/                # 定时任务
│       ├── __init__.py
│       └── tasks.py
├── scripts/                      # Shell 脚本
│   ├── init_db.sh               # 数据库初始化
│   ├── daily_sync.sh            # 每日同步 (15:30)
│   ├── morning_sync.sh          # 早盘同步 (08:30)
│   ├── catch_up_sync.sh         # 补偿同步 (22:00)
│   └── dragon_tiger_sync.sh     # 龙虎榜同步 (18:00)
├── config/                       # 配置文件
│   ├── config.example.yaml       # 配置模板
│   └── config.yaml               # 用户配置
├── data/                         # SQLite 数据库
│   └── market.db
├── logs/                         # 运行日志
├── scheduler/                    # 定时任务安装
│   ├── install.sh
│   └── uninstall.sh
├── references/                   # 参考文档
│   ├── akshare_api.md
│   └── analysis_framework.md
├── install.sh                    # 一键安装脚本
├── Makefile                      # 快捷命令
└── requirements.txt              # Python 依赖
```

---

## 🔧 配置说明

### 钉钉推送配置

编辑 `config/config.yaml`:

```yaml
dingtalk:
  enabled: true
  webhook: https://oapi.dingtalk.com/robot/send?access_token=你的token
```

### 自选股配置

```yaml
watchlist:
  holdings:
    - code: "600519"
      name: "贵州茅台"
      cost: 1800.00
      shares: 100
  watch:
    - code: "300750"
      name: "宁德时代"
```

---

## 📊 数据库说明

所有数据缓存在 SQLite 数据库 `data/market.db` 中,支持:

- **大盘指数**: 三大指数日线数据
- **市场统计**: 涨跌家数、成交额等
- **板块排名**: 行业板块、概念板块
- **资金流向**: 北向资金、融资融券、主力资金
- **市场情绪**: 涨停、连板、封板率
- **个股数据**: K线、基本信息、新闻、事件

### 常用查询

```bash
# 查询某只股票最近 K 线
sqlite3 data/market.db "SELECT date, close, change_pct FROM stock_daily WHERE code='600519' ORDER BY date DESC LIMIT 10"

# 查询某日市场统计
sqlite3 data/market.db "SELECT * FROM market_stats WHERE date='2026-03-10'"

# 查询板块排名
sqlite3 data/market.db "SELECT * FROM sector_ranking WHERE date='2026-03-10' AND type='industry' LIMIT 10"
```

---

## 🤝 OpenClaw 集成

### 作为 Skill 使用

1. **配置 OpenClaw**: 在 OpenClaw 配置文件中注册本 skill
2. **自然语言交互**: 通过对话方式调用分析功能
3. **上下文管理**: 分析结果自动存储到 OpenClaw 上下文
4. **智能推送**: 集成 OpenClaw 的通知系统

### AI 模型配置

推荐使用阿里云百炼的 qwen3.5-plus 模型:

```json
{
  "models": {
    "providers": {
      "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "apiKey": "your-api-key",
        "models": [
          {
            "id": "qwen3.5-plus",
            "name": "qwen3.5-plus"
          }
        ]
      }
    }
  }
}
```

---

## 📈 分析框架

盘面分析遵循完整的 **Checklist**:

1. ✅ **大盘环境**: 指数表现、成交额、涨跌家数
2. ✅ **板块轮动**: 行业/概念排名、主线识别
3. ✅ **资金面**: 北向资金、龙虎榜、主力资金、融资融券
4. ✅ **市场情绪**: 连板高度、封板率、情绪周期
5. ✅ **消息面**: 个股新闻、政策催化、外围市场
6. ✅ **个股技术面**: K线、均线、量价分析
7. ✅ **综合研判**: 操作建议、风险提示

详细说明见 [SKILL.md](./SKILL.md) 的"分析框架"章节。

---

## 🛠️ 维护指南

### 数据同步

```bash
# 手动同步所有数据
python3 scripts/sync.py all

# 验证同步结果
python3 scripts/verify_sync.py

# 查看同步日志
tail -f logs/daily_sync_*.log
```

### 定时任务

```bash
# 安装定时任务
bash scheduler/install.sh

# 卸载定时任务
bash scheduler/uninstall.sh

# 查看 launchd 任务
launchctl list | grep com.stock.analysis
```

### 数据库维护

```bash
# 备份数据库
make db-backup

# 优化数据库
make db-vacuum

# 查看数据库统计
python3 scripts/db_cache.py
```

---

## 📝 更新日志

- **2026-03-10**: 整理文档,明确 OpenClaw Skill 定位
- **2026-03-05**: 添加自动数据同步功能
- **2026-03-04**: 完善盘面分析框架

---

## ⚠️ 免责声明

本项目仅供学习和研究使用,不构成任何投资建议。股市有风险,投资需谨慎。

---

## 📧 联系方式

- **作者**: OpenClaw Contributor
- **项目主页**: https://github.com/yourusername/a-stock-analysis

---

**Made with ❤️ for A-Stock Analysis**