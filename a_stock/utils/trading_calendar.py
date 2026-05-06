"""
交易日历工具

用于判断指定日期是否为 A 股交易日，防止非交易日写入错误数据。

判断策略（按优先级）：
1. 本地数据库 stock_daily 表：如果该日期有 >= 1000 条记录则确认为交易日
2. AKShare 交易日历接口：tool_trade_date_hist_sina
3. 简单规则兜底：周末一定不是交易日
"""

import sqlite3
from datetime import datetime, date as date_type
from typing import Optional

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info


def is_trading_day(date_str: str) -> bool:
    """
    判断指定日期是否为 A 股交易日。

    Args:
        date_str: 日期字符串，格式 YYYY-MM-DD

    Returns:
        True 表示是交易日，False 表示不是
    """
    target_date = datetime.strptime(date_str, "%Y-%m-%d")

    # 规则 1：周末一定不是交易日
    if target_date.weekday() >= 5:
        log_debug(f"{date_str} 是周末，非交易日")
        return False

    # 规则 2：查本地数据库（历史日期可用）
    result = _check_local_db(date_str)
    if result is not None:
        return result

    # 规则 3：查 AKShare 交易日历
    result = _check_akshare_calendar(date_str)
    if result is not None:
        return result

    # 规则 4：兜底 — 工作日默认按交易日处理（但记录警告）
    log_info(f"⚠️ 无法确认 {date_str} 是否为交易日，工作日默认视为交易日")
    return True


def _check_local_db(date_str: str) -> Optional[bool]:
    """通过本地数据库 stock_daily 判断是否为交易日"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        count = cursor.execute(
            "SELECT COUNT(*) FROM stock_daily WHERE date = ?", (date_str,)
        ).fetchone()[0]

        conn.close()

        if count >= 1000:
            log_debug(f"{date_str} 本地有 {count} 条日线数据，确认为交易日")
            return True
        elif count > 0:
            # 有少量数据（可能是部分同步），无法确定
            log_debug(f"{date_str} 本地有 {count} 条日线数据，数据不完整无法确认")
            return None
        else:
            # 没有数据，可能是非交易日，也可能是还没同步过
            # 检查该日期前后是否有数据来判断
            max_date = cursor.execute(
                "SELECT MAX(date) FROM stock_daily"
            ).fetchone()[0] if hasattr(cursor, 'execute') else None

            # 重新获取连接查询（上面已关闭）
            conn2 = get_connection()
            max_date = conn2.execute(
                "SELECT MAX(date) FROM stock_daily"
            ).fetchone()[0]
            conn2.close()

            if max_date and date_str <= max_date:
                # 日期在已有数据范围内但没有记录，说明是非交易日
                log_debug(f"{date_str} 在数据范围内({max_date})但无记录，非交易日")
                return False

            # 日期超出数据范围，无法判断
            return None
    except Exception:
        return None


def _check_akshare_calendar(date_str: str) -> Optional[bool]:
    """通过 AKShare 交易日历判断是否为交易日"""
    try:
        import akshare as ak

        df = ak.tool_trade_date_hist_sina()
        trading_dates = set(df["trade_date"].astype(str).tolist())

        if date_str in trading_dates:
            log_debug(f"{date_str} AKShare 确认为交易日")
            return True
        else:
            log_debug(f"{date_str} AKShare 确认为非交易日")
            return False
    except Exception as e:
        log_debug(f"AKShare 交易日历查询失败: {e}")
        return None
