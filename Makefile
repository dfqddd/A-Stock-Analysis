# A 股数据分析系统 Makefile

.PHONY: help install sync analyze notify test clean

# 默认目标
help:
	@echo "A股数据分析系统 - 可用命令："
	@echo ""
	@echo "  make install      # 安装依赖"
	@echo "  make sync         # 同步今日数据"
	@echo "  make analyze      # 市场分析"
	@echo "  make notify       # 发送盘后推送"
	@echo "  make test         # 运行测试"
	@echo "  make clean        # 清理临时文件"
	@echo ""

# 安装
install:
	pip3 install -r requirements.txt

# 数据同步
sync:
	python -m a_stock sync --help

# 数据分析
analyze:
	python -m a_stock analyze --help

# 消息推送
notify:
	python -m a_stock analyze daily-review --notify

# 定时任务
schedule-install:
	bash scheduler/install.sh

schedule-uninstall:
	bash scheduler/uninstall.sh

# 测试
test:
	python -m pytest tests/ -v

# 清理
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov/

# 数据库
db-init:
	python -m a_stock init

db-backup:
	sqlite3 data/market.db ".backup data/market.db.bak"

db-vacuum:
	sqlite3 data/market.db "VACUUM;"

# 日志
logs:
	tail -f logs/app.log

logs-clean:
	rm -f logs/*.log