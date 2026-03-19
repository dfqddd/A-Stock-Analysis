#!/bin/bash
# 每日数据同步脚本
# 使用新的 a_stock 包结构

set -e

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 日志文件
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_sync_$(date +%Y%m%d_%H%M).log"

# 记录日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "每日数据同步开始"
log "=========================================="

# 使用系统 python3（虚拟环境有问题，akshare 未安装）
PYTHON_CMD="python3"

# 设置 PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 执行同步任务
$PYTHON_CMD -m a_stock.scheduler.tasks daily 2>&1 | tee -a "$LOG_FILE"

log "=========================================="
log "每日数据同步完成"
log "=========================================="

# 更新最后同步时间
echo "$(date +%Y-%m-%d)" > "$PROJECT_ROOT/data/sync_status/daily_sync.last"
