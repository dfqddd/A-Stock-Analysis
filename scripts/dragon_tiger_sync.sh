#!/bin/bash
# 龙虎榜数据同步脚本
# 使用新的 a_stock 包结构

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/dragon_tiger_$(date +%Y%m%d_%H%M).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "龙虎榜数据同步开始"

# 使用系统 python3（虚拟环境有问题，akshare 未安装）
PYTHON_CMD="python3"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

$PYTHON_CMD -m a_stock.scheduler.tasks dragon-tiger 2>&1 | tee -a "$LOG_FILE"

log "龙虎榜数据同步完成"
