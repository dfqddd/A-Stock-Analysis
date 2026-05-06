"""
数据同步监控模块

功能：
- 记录任务执行状态
- 检查数据完整性
- 自动补偿缺失数据
- 钉钉告警通知
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from a_stock.db.cache import get_connection, log_info, log_error, log_debug
from a_stock.notify.dingtalk import send_markdown_message


# ============================================================================
# 任务执行状态记录
# ============================================================================

def init_sync_status_table():
    """初始化任务执行状态表"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 任务执行状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_task_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                target_date TEXT NOT NULL,
                status TEXT NOT NULL,  -- success, failed, partial
                message TEXT,
                start_time TEXT,
                end_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(task_name, target_date)
            )
        """)
        
        conn.commit()
        log_debug("任务状态表初始化完成")
    finally:
        conn.close()


def record_task_status(
    task_name: str,
    task_type: str,
    target_date: str,
    status: str,
    message: str = "",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """
    记录任务执行状态
    
    Args:
        task_name: 任务名称
        task_type: 任务类型（daily, morning, catchup, dragon_tiger）
        target_date: 目标日期
        status: 执行状态（success, failed, partial）
        message: 状态消息
        start_time: 开始时间
        end_time: 结束时间
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO sync_task_status 
            (task_name, task_type, target_date, status, message, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            task_name,
            task_type,
            target_date,
            status,
            message,
            start_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            end_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        conn.commit()
    finally:
        conn.close()


def get_task_status(target_date: str, task_type: Optional[str] = None) -> List[Dict]:
    """
    获取指定日期的任务执行状态
    
    Args:
        target_date: 目标日期
        task_type: 任务类型过滤（可选）
        
    Returns:
        任务状态列表
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        if task_type:
            cursor.execute("""
                SELECT * FROM sync_task_status 
                WHERE target_date = ? AND task_type = ?
                ORDER BY created_at DESC
            """, (target_date, task_type))
        else:
            cursor.execute("""
                SELECT * FROM sync_task_status 
                WHERE target_date = ?
                ORDER BY created_at DESC
            """, (target_date,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ============================================================================
# 数据完整性检查
# ============================================================================

# 定义需要检查的数据表和检查逻辑
DATA_CHECKERS = {
    "market_stats": {
        "name": "市场统计",
        "check_sql": "SELECT COUNT(*) as count FROM market_stats WHERE date = ?",
        "min_records": 1,
    },
    "sector_ranking": {
        "name": "板块排名",
        "check_sql": "SELECT COUNT(*) as count FROM sector_ranking WHERE date = ?",
        "min_records": 10,  # 至少要有10个板块
    },
    # "capital_flow": {
    #     "name": "资金流向",
    #     "check_sql": "SELECT COUNT(*) as count FROM capital_flow WHERE date = ?",
    #     "min_records": 1,
    # },
    "sentiment": {
        "name": "市场情绪",
        "check_sql": "SELECT COUNT(*) as count FROM sentiment WHERE date = ?",
        "min_records": 1,
    },
    "limit_up_detail": {
        "name": "涨停数据",
        "check_sql": "SELECT COUNT(*) as count FROM limit_up_detail WHERE date = ?",
        "min_records": 1,  # 正常交易日至少有1只涨停股
    },
    "stock_daily": {
        "name": "日K数据",
        "check_sql": "SELECT COUNT(*) as count FROM stock_daily WHERE date = ?",
        "min_records": 3000,  # 至少要有3000只股票
    },
    "stock_hot_ranking": {
        "name": "热门股票排名",
        "check_sql": "SELECT COUNT(*) as count FROM stock_hot_ranking WHERE date = ?",
        "min_records": 10,
    },
    "stock_news": {
        "name": "股票新闻",
        "check_sql": "SELECT COUNT(*) as count FROM stock_news WHERE date = ?",
        "min_records": 1,
    },
    "stock_events": {
        "name": "股票事件",
        "check_sql": "SELECT COUNT(*) as count FROM stock_events WHERE date = ?",
        "min_records": 0,  # 可以为0
    },
}


def check_data_integrity(target_date: str) -> Dict[str, Dict]:
    """
    检查指定日期的数据完整性
    
    Args:
        target_date: 目标日期
        
    Returns:
        检查结果字典，key为表名，value包含状态信息
    """
    conn = get_connection()
    results = {}
    
    try:
        cursor = conn.cursor()
        
        for table, config in DATA_CHECKERS.items():
            try:
                cursor.execute(config["check_sql"], (target_date,))
                row = cursor.fetchone()
                count = row["count"] if row else 0
                
                results[table] = {
                    "name": config["name"],
                    "table": table,
                    "count": count,
                    "min_required": config["min_records"],
                    "status": "ok" if count >= config["min_records"] else "missing",
                    "message": f"有 {count} 条记录" if count >= config["min_records"] else f"缺失（需要至少 {config['min_records']} 条）"
                }
            except Exception as e:
                results[table] = {
                    "name": config["name"],
                    "table": table,
                    "count": 0,
                    "min_required": config["min_records"],
                    "status": "error",
                    "message": f"检查失败: {str(e)}"
                }
        
        return results
    finally:
        conn.close()


def get_missing_data_tables(target_date: str) -> List[str]:
    """
    获取缺失数据的表名列表
    
    Args:
        target_date: 目标日期
        
    Returns:
        缺失数据的表名列表
    """
    results = check_data_integrity(target_date)
    missing = []
    
    for table, info in results.items():
        if info["status"] != "ok":
            missing.append(table)
    
    return missing


# ============================================================================
# 交易日判断
# ============================================================================

def _is_weekday(date_str: str) -> bool:
    """兜底判断：非周末则视为交易日（不考虑法定节假日）"""
    weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()
    return weekday < 5  # 0-4 为周一到周五


def is_trading_day(date_str: str) -> bool:
    """
    判断指定日期是否为交易日

    优先使用新浪交易日历精确判断。当日历数据不覆盖目标日期时（如新浪日历只到上一年底），
    降级为"非周末即交易日"的兜底判断，避免因日历数据滞后导致任务被错误跳过。

    Args:
        date_str: 日期字符串 (YYYY-MM-DD)

    Returns:
        是否为交易日
    """
    try:
        import akshare as ak

        df = ak.tool_trade_date_hist_sina()
        trading_days = sorted(df['trade_date'].astype(str).tolist())
        date_compact = date_str.replace("-", "")

        # 日历覆盖到目标日期，精确判断
        if trading_days and trading_days[-1] >= date_compact:
            return date_compact in trading_days

        # 日历不覆盖目标日期，降级为非周末判断
        log_info(f"交易日历最新日期 {trading_days[-1]} < {date_compact}，降级为非周末判断")
        return _is_weekday(date_str)

    except Exception as e:
        log_error(f"判断交易日失败: {e}，降级为非周末判断")
        return _is_weekday(date_str)


def get_last_trading_day(date_str: Optional[str] = None) -> str:
    """
    获取最近一个交易日

    优先使用新浪交易日历精确查找。当日历不覆盖目标日期时，降级为向前找最近的工作日。

    Args:
        date_str: 参考日期（可选，默认为今天）

    Returns:
        最近交易日（YYYY-MM-DD）
    """
    target_date = date_str or datetime.now().strftime("%Y-%m-%d")

    try:
        import akshare as ak

        target_compact = target_date.replace("-", "")
        df = ak.tool_trade_date_hist_sina()
        trading_days = sorted(df['trade_date'].astype(str).tolist())

        # 日历覆盖到目标日期，精确查找
        if trading_days and trading_days[-1] >= target_compact:
            for day in reversed(trading_days):
                if day <= target_compact:
                    return f"{day[:4]}-{day[4:6]}-{day[6:8]}"
            return target_date

        # 日历不覆盖目标日期，降级为向前找最近工作日
        log_info(f"交易日历最新日期 {trading_days[-1]} < {target_compact}，降级为向前找工作日")

    except Exception as e:
        log_error(f"获取最近交易日失败: {e}，降级为向前找工作日")

    # 兜底：从目标日期向前找最近的工作日（最多找7天）
    current = datetime.strptime(target_date, "%Y-%m-%d")
    for _ in range(7):
        if current.weekday() < 5:
            return current.strftime("%Y-%m-%d")
        current -= timedelta(days=1)
    return target_date


# ============================================================================
# 补偿任务映射
# ============================================================================

# 表名到同步函数的映射
COMPENSATION_TASKS = {
    "market_stats": ("a_stock.sync.market_stats_sync", "sync_market_stats"),
    "sector_ranking": ("a_stock.sync.sector_ranking_sync", "sync_sector_ranking"),
    "sentiment": ("a_stock.sync.sentiment_sync", "sync_sentiment"),
    "limit_up_detail": ("a_stock.sync.limit_up", "sync_limit_up"),
    "stock_daily": ("a_stock.sync.stock_daily", "sync_stock_daily"),
    "stock_hot_ranking": ("a_stock.sync.stock_hot_ranking", "sync_stock_hot_ranking"),
    "stock_news": ("a_stock.sync.stock_news", "sync_stock_news"),
    "stock_events": ("a_stock.sync.stock_events", "sync_stock_events"),
}


def run_compensation_task(table: str, target_date: str) -> Tuple[bool, str]:
    """
    执行单个补偿任务
    
    Args:
        table: 表名
        target_date: 目标日期
        
    Returns:
        (是否成功, 消息)
    """
    if table not in COMPENSATION_TASKS:
        return False, f"未知的表: {table}"
    
    module_path, func_name = COMPENSATION_TASKS[table]
    
    try:
        # 动态导入模块
        import importlib
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        
        # 执行同步函数
        log_info(f"开始补偿同步: {table} ({target_date})")
        
        if table in ["stock_daily", "capital_flow"]:
            # 这些函数使用 days 参数
            func(days=1)
        else:
            func(date=target_date)
        
        return True, "补偿成功"
        
    except Exception as e:
        error_msg = str(e)
        log_error(f"补偿同步失败 {table}: {error_msg}")
        return False, f"补偿失败: {error_msg}"


# ============================================================================
# 钉钉告警
# ============================================================================

def send_sync_alert(target_date: str, check_results: Dict[str, Dict], missing_tables: List[str]):
    """
    发送同步告警通知
    
    Args:
        target_date: 目标日期
        check_results: 检查结果
        missing_tables: 缺失数据的表名列表
    """
    if not missing_tables:
        return
    
    title = f"📊 数据同步异常告警 - {target_date}"
    
    # 构建 Markdown 内容
    content = f"## {title}\\n\\n"
    content += f"**检查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n"
    content += f"**目标日期**: {target_date}\\n\\n"
    content += "---\\n\\n"
    
    # 缺失数据详情
    content += "### ⚠️ 缺失数据\\n\\n"
    for table in missing_tables:
        info = check_results.get(table, {})
        content += f"- **{info.get('name', table)}**: {info.get('message', '数据缺失')}\\n"
    
    content += "\\n---\\n\\n"
    
    # 正常数据汇总
    ok_tables = [t for t in check_results if t not in missing_tables]
    if ok_tables:
        content += f"### ✅ 正常数据 ({len(ok_tables)} 项)\\n\\n"
        for table in ok_tables[:5]:  # 只显示前5个
            info = check_results[table]
            content += f"- {info['name']}: {info['message']}\\n"
        if len(ok_tables) > 5:
            content += f"- ... 等共 {len(ok_tables)} 项\\n"
    
    content += "\\n---\\n\\n"
    content += "🔧 **系统将自动尝试补偿缺失数据**\\n"
    
    send_markdown_message(title=title, content=content)


def send_compensation_report(target_date: str, results: List[Tuple[str, bool, str]]):
    """
    发送补偿执行报告
    
    Args:
        target_date: 目标日期
        results: 补偿结果列表 [(表名, 是否成功, 消息), ...]
    """
    success_count = sum(1 for _, success, _ in results if success)
    fail_count = len(results) - success_count
    
    title = f"📋 数据补偿报告 - {target_date}"
    
    content = f"## {title}\\n\\n"
    content += f"**补偿时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n"
    content += f"**补偿结果**: 成功 {success_count} / 失败 {fail_count}\\n\\n"
    content += "---\\n\\n"
    
    # 失败的详情
    failed_tasks = [(table, msg) for table, success, msg in results if not success]
    if failed_tasks:
        content += "### ❌ 补偿失败\\n\\n"
        for table, msg in failed_tasks:
            table_name = DATA_CHECKERS.get(table, {}).get("name", table)
            content += f"- **{table_name}**: {msg}\\n"
        content += "\\n"
    
    # 成功的详情
    success_tasks = [table for table, success, _ in results if success]
    if success_tasks:
        content += f"### ✅ 补偿成功 ({len(success_tasks)} 项)\\n\\n"
        for table in success_tasks[:5]:
            table_name = DATA_CHECKERS.get(table, {}).get("name", table)
            content += f"- {table_name}\\n"
        if len(success_tasks) > 5:
            content += f"- ... 等共 {len(success_tasks)} 项\\n"
    
    send_markdown_message(title=title, content=content)


# ============================================================================
# 主入口
# ============================================================================

def run_sync_check_and_compensate(target_date: Optional[str] = None):
    """
    执行同步检查和自动补偿
    
    Args:
        target_date: 目标日期（可选，默认为最近交易日）
    """
    # 初始化表
    init_sync_status_table()
    
    # 确定目标日期
    if target_date is None:
        target_date = get_last_trading_day()
    
    log_info(f"=" * 50)
    log_info(f"开始数据同步检查 - {target_date}")
    log_info(f"=" * 50)
    
    # 检查是否为交易日
    if not is_trading_day(target_date):
        log_info(f"{target_date} 不是交易日，跳过检查")
        return
    
    # 检查数据完整性
    log_info("检查数据完整性...")
    check_results = check_data_integrity(target_date)
    
    # 获取缺失的表
    missing_tables = [t for t, info in check_results.items() if info["status"] != "ok"]
    
    if not missing_tables:
        log_info("✅ 所有数据已同步完成，无需补偿")
        # 记录状态
        record_task_status(
            task_name="sync_check",
            task_type="catchup",
            target_date=target_date,
            status="success",
            message="所有数据已同步"
        )
        return
    
    log_info(f"发现 {len(missing_tables)} 项数据缺失: {missing_tables}")
    
    # 发送告警
    send_sync_alert(target_date, check_results, missing_tables)
    
    # 执行补偿
    log_info("开始执行数据补偿...")
    compensation_results = []
    
    for table in missing_tables:
        success, message = run_compensation_task(table, target_date)
        compensation_results.append((table, success, message))
        
        # 记录补偿状态
        status = "success" if success else "failed"
        record_task_status(
            task_name=f"compensate_{table}",
            task_type="catchup",
            target_date=target_date,
            status=status,
            message=message
        )
    
    # 发送补偿报告
    send_compensation_report(target_date, compensation_results)
    
    # 重新检查
    log_info("重新检查数据完整性...")
    final_results = check_data_integrity(target_date)
    final_missing = [t for t, info in final_results.items() if info["status"] != "ok"]
    
    if final_missing:
        log_error(f"❌ 补偿后仍有 {len(final_missing)} 项数据缺失")
        record_task_status(
            task_name="sync_check",
            task_type="catchup",
            target_date=target_date,
            status="partial",
            message=f"补偿后仍有缺失: {final_missing}"
        )
    else:
        log_info("✅ 补偿完成，所有数据已同步")
        record_task_status(
            task_name="sync_check",
            task_type="catchup",
            target_date=target_date,
            status="success",
            message="补偿完成"
        )
    
    log_info(f"=" * 50)
    log_info(f"数据同步检查完成 - {target_date}")
    log_info(f"=" * 50)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据同步监控")
    parser.add_argument("--date", help="指定日期 (YYYY-MM-DD)")
    parser.add_argument("--check-only", action="store_true", help="仅检查，不执行补偿")
    
    args = parser.parse_args()
    
    if args.check_only:
        # 仅检查模式
        init_sync_status_table()
        target_date = args.date or get_last_trading_day()
        results = check_data_integrity(target_date)
        missing = [t for t, info in results.items() if info["status"] != "ok"]
        
        print(f"\n{'='*50}")
        print(f"数据完整性检查报告 - {target_date}")
        print(f"{'='*50}")
        
        for table, info in results.items():
            status_icon = "✅" if info["status"] == "ok" else "❌"
            print(f"{status_icon} {info['name']}: {info['message']}")
        
        print(f"{'='*50}")
        if missing:
            print(f"缺失数据: {len(missing)} 项")
        else:
            print("所有数据正常")
    else:
        run_sync_check_and_compensate(args.date)
