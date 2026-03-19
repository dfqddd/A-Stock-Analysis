"""
A 股数据本地 SQLite 缓存模块

功能：
- 自动建表、读写、缓存判断
- 历史数据优先走缓存，当天实时数据（15:00 前）不缓存
- 收盘后（15:00 后）当天数据也写入缓存

表结构：
- index_daily: 大盘指数日K线
- market_stats: 全市场涨跌统计
- sector_ranking: 板块排名
- capital_flow: 资金流向
- sentiment: 市场情绪
- stock_daily: 个股日K线（含换手率 turnover_rate，东财/同花顺数据源提供，腾讯/新浪无此字段）
"""

import json
import os
import sqlite3
from datetime import datetime, date as date_type
from pathlib import Path
from typing import Any, Dict, List, Optional


def _find_project_root() -> Path:
    """查找项目根目录，确保始终使用同一个数据库"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        # 检查是否是项目根目录（包含 data 目录）
        if (parent / "data").is_dir() and (parent / "data" / "market.db").exists():
            return parent
    # 如果找不到，使用默认路径
    return current.parent.parent


# 数据库文件路径 - 始终使用项目根目录下的 data/market.db
PROJECT_ROOT = _find_project_root()
DB_DIR = PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "market.db"


# ============================================================================
# 工具函数
# ============================================================================


def log_debug(msg: str):
    """调试日志"""
    print(f"[DEBUG] {msg}")


def log_info(msg: str):
    """信息日志"""
    print(f"[INFO] {msg}")


def log_error(msg: str):
    """错误日志"""
    print(f"[ERROR] {msg}")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，设置 row_factory"""
    # 确保 data 目录存在
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提高并发
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 大盘指数日K线
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS index_daily (
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                pct_change REAL,
                PRIMARY KEY (date, code)
            )
            """
        )

        # 全市场涨跌统计
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS market_stats (
                date TEXT PRIMARY KEY,
                up_count INTEGER,
                down_count INTEGER,
                flat_count INTEGER,
                limit_up_count INTEGER,
                limit_down_count INTEGER,
                new_high_count INTEGER,
                new_low_count INTEGER,
                avg_turnover REAL,
                total_amount REAL,
                total_volume REAL
            )
            """
        )

        # 板块排名（行业、概念）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sector_ranking (
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                change_pct REAL,
                leading_stock TEXT,
                leading_stock_change REAL,
                amount REAL,
                rank INTEGER,
                PRIMARY KEY (date, type, name)
            )
            """
        )

        # 资金流向（北向、南向）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS capital_flow (
                date TEXT PRIMARY KEY,
                north_net REAL,
                north_sh REAL,
                north_sz REAL,
                south_net REAL,
                south_hk REAL
            )
            """
        )

        # 市场情绪指标
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sentiment (
                date TEXT PRIMARY KEY,
                bull_bear_index REAL,
                fear_greed_index REAL,
                new_high_ratio REAL,
                new_low_ratio REAL,
                limit_up_ratio REAL,
                limit_down_ratio REAL,
                turnover_rate REAL
            )
            """
        )

        # 个股日K线
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_daily (
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                turnover_rate REAL,
                pct_change REAL,
                source TEXT,
                PRIMARY KEY (date, code)
            )
            """
        )

        # 股票基础信息
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_info (
                code TEXT PRIMARY KEY,
                name TEXT,
                market TEXT,
                board TEXT,
                industry TEXT,
                concepts TEXT,
                main_business TEXT,
                total_market_cap_yi REAL,
                circulating_cap_yi REAL,
                pe_ratio REAL,
                pb_ratio REAL,
                roe REAL,
                gross_margin REAL,
                net_profit_yi REAL,
                revenue_yi REAL,
                profit_yoy REAL,
                revenue_yoy REAL,
                updated_at TEXT
            )
            """
        )

        # 涨停股详情
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS limit_up_detail (
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                limit_up_time TEXT,
                first_limit_up_time TEXT,
                open_limit_up INTEGER DEFAULT 0,
                seal_amount REAL,
                seal_times INTEGER,
                reason TEXT,
                industry TEXT,
                turn_ratio REAL,
                PRIMARY KEY (date, code)
            )
            """
        )

        # 个股资金流向
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_fund_flow (
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                main_net_inflow REAL,
                main_net_inflow_ratio REAL,
                retail_net_inflow REAL,
                retail_net_inflow_ratio REAL,
                PRIMARY KEY (date, code)
            )
            """
        )

        # 板块资金流向
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sector_fund_flow (
                date TEXT NOT NULL,
                sector TEXT NOT NULL,
                main_net_inflow REAL,
                main_net_inflow_ratio REAL,
                retail_net_inflow REAL,
                retail_net_inflow_ratio REAL,
                PRIMARY KEY (date, sector)
            )
            """
        )

        # 股票事件（复牌、停牌、分红等）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_events (
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_desc TEXT,
                PRIMARY KEY (date, code, event_type)
            )
            """
        )

        # 股票新闻
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                code TEXT,
                title TEXT NOT NULL,
                source TEXT,
                url TEXT,
                sentiment TEXT,
                created_at TEXT
            )
            """
        )

        # 龙虎榜汇总表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dragon_tiger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                
                -- 股票基本信息
                close_price REAL,
                change_pct REAL,
                turnover_rate REAL,
                
                -- 龙虎榜原因
                lhb_reason TEXT,
                
                -- 龙虎榜汇总数据
                buy_value REAL,
                sell_value REAL,
                net_buy_value REAL,
                total_value REAL,
                
                -- 买卖原因分析
                reason TEXT,
                
                -- 更新时间
                updated_at TEXT,
                
                UNIQUE(date, code)
            )
            """
        )

        # 热门股票榜单表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_hot_ranking (
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                
                -- 综合热度
                total_rank INTEGER,
                total_score REAL,
                
                -- 各平台热度
                ths_rank INTEGER,
                ths_score REAL,
                tgb_rank INTEGER,
                tgb_score REAL,
                dcb_rank INTEGER,
                dcb_score REAL,
                xq_rank INTEGER,
                xq_score REAL,
                
                -- 聚合来源数
                source_count INTEGER,
                
                PRIMARY KEY (date, code)
            )
            """
        )

        # 个股异动表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_abnormal_movement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT,
                
                -- 异动类型
                movement_type TEXT NOT NULL,
                
                -- 异动阶段
                stage TEXT NOT NULL,
                
                -- 时间信息
                enter_date TEXT,
                exit_date TEXT,
                duration_days INTEGER,
                
                -- 异动详情
                trigger_price REAL,
                trigger_change REAL,
                trigger_volume REAL,
                trigger_amount REAL,
                trigger_amplitude REAL,
                
                -- 当前状态
                current_price REAL,
                current_change REAL,
                
                -- 风险等级
                risk_level TEXT,
                
                -- 更新时间
                updated_at TEXT,
                
                UNIQUE(code, movement_type, enter_date)
            )
            """
        )

        conn.commit()
        log_debug("数据库表结构初始化完成")
    finally:
        conn.close()


# ============================================================================
# 缓存判断
# ============================================================================


def is_trading_time() -> bool:
    """判断当前是否在交易时间内（9:30-11:30, 13:00-15:00）"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # 上午 9:30-11:30
    if hour == 9 and minute >= 30:
        return True
    if hour == 10:
        return True
    if hour == 11 and minute <= 30:
        return True

    # 下午 13:00-15:00
    if hour == 13:
        return True
    if hour == 14:
        return True
    if hour == 15 and minute == 0:
        return True

    return False


def is_after_close() -> bool:
    """判断是否已收盘（15:00 后）"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    if hour > 15:
        return True
    if hour == 15 and minute > 0:
        return True

    return False


def should_use_cache(date_str: str) -> bool:
    """
    判断是否应该使用缓存数据

    规则：
    - 如果 date_str 是历史日期，使用缓存
    - 如果 date_str 是今天：
      - 交易时间内：不使用缓存（数据实时变化）
      - 收盘后：可以使用缓存（数据已定）
    """
    today = date_type.today().isoformat()

    # 历史日期，使用缓存
    if date_str < today:
        return True

    # 今天的数据
    if date_str == today:
        # 收盘后，可以使用缓存
        if is_after_close():
            return True
        # 交易时间内，不使用缓存
        return False

    # 未来日期（不应该出现）
    return False


# ============================================================================
# 数据读写工具
# ============================================================================


def upsert_records(
    table: str,
    records: List[Dict],
    primary_keys: List[str],
    date_field: str = "date",
):
    """
    批量写入记录，存在则更新

    Args:
        table: 表名
        records: 记录列表
        primary_keys: 主键字段列表
        date_field: 日期字段名，用于缓存判断
    """
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 获取所有列名
        all_columns = list(records[0].keys())

        for record in records:
            # 构建列名和占位符
            columns = ", ".join(all_columns)
            placeholders = ", ".join(["?" for _ in all_columns])
            values = [record.get(col) for col in all_columns]

            # 构建 UPDATE 部分（排除主键）
            update_columns = [col for col in all_columns if col not in primary_keys]
            update_set = ", ".join([f"{col} = ?" for col in update_columns])
            update_values = [record.get(col) for col in update_columns]

            # 构建 WHERE 条件
            where_clause = " AND ".join([f"{pk} = ?" for pk in primary_keys])
            where_values = [record.get(pk) for pk in primary_keys]

            # 使用 INSERT OR REPLACE
            sql = f"""
                INSERT OR REPLACE INTO {table} ({columns})
                VALUES ({placeholders})
            """
            cursor.execute(sql, values)

        conn.commit()
        log_debug(f"已写入 {len(records)} 条记录到 {table}")
    except Exception as e:
        log_error(f"写入 {table} 失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def query_records(
    table: str,
    date_str: str = None,
    where_clause: str = None,
    params: tuple = None,
    order_by: str = None,
    limit: int = None,
) -> List[Dict]:
    """
    查询记录

    Args:
        table: 表名
        date_str: 日期（可选）
        where_clause: WHERE 条件（可选）
        params: WHERE 参数（可选）
        order_by: 排序字段（可选）
        limit: 返回数量限制（可选）

    Returns:
        记录列表（字典格式）
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        sql = f"SELECT * FROM {table}"
        conditions = []
        all_params = []

        if date_str:
            conditions.append("date = ?")
            all_params.append(date_str)

        if where_clause:
            conditions.append(where_clause)
            if params:
                all_params.extend(params if isinstance(params, (list, tuple)) else [params])

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        if order_by:
            sql += f" ORDER BY {order_by}"

        if limit:
            sql += f" LIMIT {limit}"

        cursor.execute(sql, all_params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_latest_date(table: str, date_field: str = "date") -> Optional[str]:
    """获取表中最新日期"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT MAX({date_field}) FROM {table}")
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        conn.close()


def get_table_count(table: str, date_str: str = None) -> int:
    """获取表中记录数"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if date_str:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE date = ?", (date_str,))
        else:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
        result = cursor.fetchone()
        return result[0] if result else 0
    finally:
        conn.close()


# 初始化数据库
if DB_PATH.exists():
    log_debug(f"数据库已存在: {DB_PATH}")
else:
    log_info(f"创建新数据库: {DB_PATH}")
    init_db()
