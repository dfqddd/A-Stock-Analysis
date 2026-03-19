"""
股票事件同步脚本

数据来源：
  - 东财 stock_tfp_em（停复牌数据，主数据源，优先级 0）
  - 巨潮 stock_dividend_cninfo（分红送转数据，主数据源，优先级 0）
  - 其他备选数据源（自动降级）
"""

import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.datasource import DataSource, get_manager


def save_stock_events(records: List[Dict]):
    """将股票事件写入数据库"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO stock_events
                (date, code, event_type, event_desc)
                VALUES (?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record["code"],
                    record["event_type"],
                    record.get("event_desc"),
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条股票事件")
    finally:
        conn.close()


def fetch_trading_suspend_em(date: str) -> List[Dict]:
    """
    使用东财数据源获取停复牌数据（主数据源）

    Args:
        date: 指定日期

    Returns:
        停牌事件列表
    """
    events = []

    try:
        # 获取停复牌数据
        df = ak.stock_tfp_em(date=date)

        if df is None or df.empty:
            return events

        for _, row in df.iterrows():
            # 筛选停牌的股票
            status = str(row.get("停牌状态", ""))
            if "停牌" in status or "暂停" in status:
                events.append({
                    "date": date,
                    "code": str(row.get("代码", "")),
                    "event_type": "suspend",
                    "event_desc": f"停牌 - {row.get('停牌原因', '未知原因')}",
                })
            elif "复牌" in status:
                events.append({
                    "date": date,
                    "code": str(row.get("代码", "")),
                    "event_type": "resume",
                    "event_desc": "复牌",
                })

    except Exception as e:
        log_debug(f"东财数据源获取停复牌数据失败: {e}")
        raise

    return events


def fetch_dividend_cninfo(date: str) -> List[Dict]:
    """
    使用巨潮数据源获取分红送转数据（主数据源）

    Args:
        date: 指定日期

    Returns:
        分红事件列表
    """
    events = []

    try:
        # 获取分红送转数据
        df = ak.stock_dividend_cninfo(date=date)

        if df is None or df.empty:
            return events

        for _, row in df.iterrows():
            dividend_type = []
            if row.get("送股比例", 0) > 0:
                dividend_type.append(f"送股{row['送股比例']}股")
            if row.get("转增比例", 0) > 0:
                dividend_type.append(f"转增{row['转增比例']}股")
            if row.get("派息比例", 0) > 0:
                dividend_type.append(f"派息{row['派息比例']}元")

            if dividend_type:
                events.append({
                    "date": date,
                    "code": str(row.get("股票代码", "")),
                    "event_type": "dividend",
                    "event_desc": f"分红送转 - {', '.join(dividend_type)}",
                })

    except Exception as e:
        log_debug(f"巨潮数据源获取分红送转数据失败: {e}")
        raise

    return events


def fetch_trading_suspend_sina(date: str) -> List[Dict]:
    """
    使用新浪数据源获取停复牌数据（备选数据源）

    Args:
        date: 指定日期

    Returns:
        停牌事件列表
    """
    events = []

    try:
        # 新浪停复牌数据接口
        df = ak.stock_suspension_em(date=date)

        if df is None or df.empty:
            return events

        for _, row in df.iterrows():
            # 筛选停牌的股票
            status = str(row.get("停牌状态", ""))
            if "停牌" in status or "暂停" in status:
                events.append({
                    "date": date,
                    "code": str(row.get("代码", "")),
                    "event_type": "suspend",
                    "event_desc": f"停牌 - {row.get('停牌原因', '未知原因')}",
                })
            elif "复牌" in status:
                events.append({
                    "date": date,
                    "code": str(row.get("代码", "")),
                    "event_type": "resume",
                    "event_desc": "复牌",
                })

    except Exception as e:
        log_debug(f"新浪数据源获取停复牌数据失败: {e}")
        raise

    return events

def fetch_dividend_eastmoney(date: str) -> List[Dict]:
    """
    使用东财数据源获取分红送转数据（备选数据源）

    Args:
        date: 指定日期

    Returns:
        分红事件列表
    """
    events = []

    try:
        # 东财分红送转数据接口
        df = ak.stock_dividend_detail_em()

        if df is None or df.empty:
            return events

        # 按日期过滤
        for _, row in df.iterrows():
            dividend_date = str(row.get("除权除息日", ""))
            if dividend_date == date:
                dividend_type = []
                if row.get("送股比例", 0) > 0:
                    dividend_type.append(f"送股{row['送股比例']}股")
                if row.get("转增比例", 0) > 0:
                    dividend_type.append(f"转增{row['转增比例']}股")
                if row.get("派息比例", 0) > 0:
                    dividend_type.append(f"派息{row['派息比例']}元")

                if dividend_type:
                    events.append({
                        "date": date,
                        "code": str(row.get("股票代码", "")),
                        "event_type": "dividend",
                        "event_desc": f"分红送转 - {', '.join(dividend_type)}",
                    })

    except Exception as e:
        log_debug(f"东财数据源获取分红送转数据失败: {e}")
        raise

    return events

def register_datasources():
    """注册数据源到管理器"""
    manager = get_manager()

    # 注册东财停复牌数据源（优先级 0，最高）
    manager.register(
        "trading_suspend",
        DataSource(
            name="eastmoney_suspend",
            fetch_func=fetch_trading_suspend_em,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )

    # 注册新浪停复牌数据源（优先级 1，备选）
    manager.register(
        "trading_suspend",
        DataSource(
            name="sina_suspend",
            fetch_func=fetch_trading_suspend_sina,
            priority=1,
            retry_count=3,
            retry_delay=1.0,
        )
    )

    # 注册巨潮分红送转数据源（优先级 0，最高）
    manager.register(
        "dividend",
        DataSource(
            name="cninfo_dividend",
            fetch_func=fetch_dividend_cninfo,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )

    # 注册东财分红送转数据源（优先级 1，备选）
    manager.register(
        "dividend",
        DataSource(
            name="eastmoney_dividend",
            fetch_func=fetch_dividend_eastmoney,
            priority=1,
            retry_count=3,
            retry_delay=1.0,
        )
    )

def sync_stock_events(date: str = None):
    """
    同步股票事件（停复牌、分红送转等）

    Args:
        date: 指定日期（可选）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步股票事件: {target_date}")

    # 注册数据源
    register_datasources()

    # 获取管理器
    manager = get_manager()

    all_events = []

    # 同步停复牌事件（使用多数据源）
    suspend_events = manager.fetch("trading_suspend", date=target_date)
    all_events.extend(suspend_events)

    # 同步分红送转事件（使用多数据源）
    dividend_events = manager.fetch("dividend", date=target_date)
    all_events.extend(dividend_events)

    # 写入数据库
    if all_events:
        save_stock_events(all_events)
        log_info(f"已写入 {len(all_events)} 条股票事件")
    else:
        log_debug("无股票事件需要写入")


def main():
    parser = argparse.ArgumentParser(description="同步股票事件")
    parser.add_argument("--date", help="指定日期")

    args = parser.parse_args()
    sync_stock_events(date=args.date)


if __name__ == "__main__":
    main()
