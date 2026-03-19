"""
股票新闻同步脚本

数据来源：
  - 东财股票新闻（主数据源，优先级 0）
  - 金融界股票新闻（备选数据源，优先级 1）
  - 财新股票新闻（备选数据源，优先级 2）
"""

import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.datasource import DataSource, get_manager

def fetch_stock_news_em(code: str = None) -> List[Dict]:
    """
    使用东财数据源获取股票新闻（主数据源）

    Args:
        code: 股票代码（可选）

    Returns:
        新闻数据列表
    """
    try:
        # 使用 AKShare 获取股票新闻
        if code:
            df = ak.stock_news_em(symbol=code)
        else:
            # 获取市场热点新闻
            df = ak.stock_news_em(symbol="")

        if df is None or df.empty:
            return []

        log_debug(f"从东财数据源获取到 {len(df)} 条新闻")

        # 处理数据
        records = []
        for _, row in df.iterrows():
            record = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "code": code,
                "title": row.get("新闻标题", ""),
                "source": row.get("新闻来源", ""),
                "url": row.get("新闻链接", ""),
                "sentiment": None,
            }
            records.append(record)

        return records
    except Exception as e:
        log_debug(f"东财数据源获取股票新闻失败: {e}")
        raise

def fetch_stock_news_jr(code: str = None) -> List[Dict]:
    """
    使用金融界数据源获取股票新闻（备选数据源）

    Args:
        code: 股票代码（可选）

    Returns:
        新闻数据列表
    """
    try:
        # 尝试使用金融界数据接口
        df = ak.stock_news_jr(symbol=code if code else "")

        if df is None or df.empty:
            return []

        log_debug(f"从金融界数据源获取到 {len(df)} 条新闻")

        # 处理数据
        records = []
        for _, row in df.iterrows():
            record = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "code": code,
                "title": row.get("标题", ""),
                "source": row.get("来源", ""),
                "url": row.get("链接", ""),
                "sentiment": None,
            }
            records.append(record)

        return records
    except Exception as e:
        log_debug(f"金融界数据源获取股票新闻失败: {e}")
        raise

def fetch_stock_news_main_cx(code: str = None) -> List[Dict]:
    """
    使用财新数据源获取股票新闻（备选数据源）

    Args:
        code: 股票代码（可选）

    Returns:
        新闻数据列表
    """
    try:
        # 尝试使用财新数据接口
        df = ak.stock_news_main_cx()

        if df is None or df.empty:
            return []

        log_debug(f"从财新数据源获取到 {len(df)} 条新闻")

        # 处理数据
        records = []
        for _, row in df.iterrows():
            record = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "code": code,
                "title": row.get("标题", ""),
                "source": row.get("来源", "财新"),
                "url": row.get("链接", ""),
                "sentiment": None,
            }
            records.append(record)

        return records
    except Exception as e:
        log_debug(f"财新数据源获取股票新闻失败: {e}")
        raise

def register_datasources():
    """注册数据源到管理器"""
    manager = get_manager()
    
    # 注册东财数据源（优先级 0，最高）
    manager.register(
        "stock_news",
        DataSource(
            name="eastmoney",
            fetch_func=fetch_stock_news_em,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )
    
    # 注册金融界数据源（优先级 1）
    manager.register(
        "stock_news",
        DataSource(
            name="jr",
            fetch_func=fetch_stock_news_jr,
            priority=1,
            retry_count=3,
            retry_delay=1.0,
        )
    )
    
    # 注册财新数据源（优先级 2）
    manager.register(
        "stock_news",
        DataSource(
            name="main_cx",
            fetch_func=fetch_stock_news_main_cx,
            priority=2,
            retry_count=3,
            retry_delay=1.0,
        )
    )


def save_stock_news(records: List[Dict]):
    """将股票新闻写入数据库"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT INTO stock_news
                (date, code, title, source, url, sentiment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record.get("code"),
                    record["title"],
                    record.get("source"),
                    record.get("url"),
                    record.get("sentiment"),
                    datetime.now().isoformat(),
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条股票新闻")
    finally:
        conn.close()


def sync_stock_news(code: str = None, date: str = None):
    """
    同步股票新闻

    Args:
        code: 股票代码（可选）
        date: 指定日期（可选）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步股票新闻: {target_date}")
    
    # 注册数据源
    register_datasources()
    
    try:
        # 使用数据源管理器获取数据
        manager = get_manager()
        records = manager.fetch("stock_news", code=code)

        if not records:
            log_debug("获取股票新闻为空")
            return

        log_debug(f"获取到 {len(records)} 条新闻")

        # 写入数据库
        save_stock_news(records)
        log_info(f"已写入 {len(records)} 条股票新闻")

    except Exception as e:
        log_error(f"同步股票新闻失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="同步股票新闻")
    parser.add_argument("--code", help="指定股票代码")
    parser.add_argument("--date", help="指定日期")

    args = parser.parse_args()
    sync_stock_news(code=args.code, date=args.date)


if __name__ == "__main__":
    main()
