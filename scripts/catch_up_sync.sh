#!/bin/bash
# 补数据同步脚本（增强版）
# 每天晚上 22:00 执行，包含数据完整性检查和自动补偿

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/catch_up_$(date +%Y%m%d_%H%M).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "补数据同步开始（含完整性检查和补偿）"
log "========================================"

# 使用系统 python3（虚拟环境有问题，akshare 未安装）
PYTHON_CMD="python3"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 执行增强版补数据同步
$PYTHON_CMD -m a_stock.scheduler.tasks catchup 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    log "========================================"
    log "补数据同步完成"
    log "========================================"
else
    log "========================================"
    log "补数据同步异常退出 (code: $EXIT_CODE)"
    log "========================================"
fi

exit $EXIT_CODE
