#!/bin/bash
# 个股日K数据同步脚本（17:30 执行）
# 使用 Tushare Pro 批量接口，一次请求获取所有股票当日数据

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/stock_daily_$(date +%Y%m%d_%H%M).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "个股日K数据同步开始"
log "=========================================="

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

python3 -m a_stock.scheduler.tasks stock-daily 2>&1 | tee -a "$LOG_FILE"

log "=========================================="
log "个股日K数据同步完成"
log "=========================================="
