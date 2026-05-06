"""
三大指数数据同步模块
同步上证指数、深证成指、创业板指的数据

数据源：
  - 东方财富（主数据源，优先级 0）
  - 新浪财经（备选数据源，优先级 1）
"""

from datetime import datetime
from typing import List, Dict

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.datasource import DataSource, get_manager


def save_index_daily(records: List[Dict]):
    """将指数数据写入数据库"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO index_daily
                (date, code, name, open, close, high, low, change_pct, amount_yi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record["code"],
                    record["name"],
                    record.get("open"),
                    record.get("close"),
                    record.get("high"),
                    record.get("low"),
                    record.get("change_pct"),
                    record.get("amount_yi", 0),
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条指数数据")
    finally:
        conn.close()


def fetch_index_from_eastmoney(symbol: str, target_date: str) -> Dict:
    """
    从东方财富获取指数数据
    
    东方财富接口返回中文列名：日期/开盘/收盘/最高/最低/成交量/成交额/振幅/涨跌幅/涨跌额/换手率
    成交量单位：手；成交额单位：元
    
    Args:
        symbol: 指数代码
        target_date: 目标日期
        
    Returns:
        指数数据字典（含 open/close/high/low/change_pct/amount_yi）
    """
    df = ak.index_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=target_date.replace("-", ""),
        end_date=target_date.replace("-", ""),
    )
    
    if df is None or df.empty:
        raise ValueError(f"东财数据源无 {target_date} 数据")
    
    row = df.iloc[0]
    return {
        "open": float(row["开盘"]) if "开盘" in row else None,
        "close": float(row["收盘"]),
        "high": float(row["最高"]) if "最高" in row else None,
        "low": float(row["最低"]) if "最低" in row else None,
        "change_pct": float(row["涨跌幅"]),
        # 东方财富接口有成交额字段，但 amount_yi 统一存成交量（手）以保持一致
        "amount_yi": round(float(row["成交量"]) / 100000000, 2) if "成交量" in row else 0,
    }


def fetch_index_from_tx(symbol: str, target_date: str) -> Dict:
    """
    从腾讯财经获取指数数据（主数据源，数据更新最快）
    
    Args:
        symbol: 指数代码
        target_date: 目标日期
        
    Returns:
        指数数据字典
    """
    # 腾讯接口使用不同代码格式
    tx_symbol = f"sh{symbol}" if symbol.startswith("0") else f"sz{symbol}"
    
    # 获取数据（该接口获取全部历史数据）
    df = ak.stock_zh_index_daily_tx(symbol=tx_symbol)
    
    if df is None or df.empty:
        raise ValueError(f"腾讯数据源返回空数据")
    
    # 只保留最近30天的数据以提高性能
    df = df.tail(30).copy()
    
    # 筛选目标日期
    df["date"] = df["date"].astype(str)
    target_df = df[df["date"] == target_date]
    
    if target_df.empty:
        raise ValueError(f"腾讯数据源无 {target_date} 数据")
    
    row = target_df.iloc[0]
    close_price = float(row["close"])
    
    # 腾讯接口没有 change_pct 字段，需要计算涨跌幅
    # 从已获取的数据中找到前一日
    prev_close = None
    sorted_df = df.sort_values("date")
    for i, r in enumerate(sorted_df.itertuples()):
        if str(r.date) == target_date and i > 0:
            prev_close = float(sorted_df.iloc[i-1]["close"])
            break
    
    # 计算涨跌幅
    if prev_close and prev_close > 0:
        change_pct = round((close_price - prev_close) / prev_close * 100, 2)
    else:
        change_pct = 0.0
    
    return {
        "open": float(row["open"]) if "open" in row else None,
        "close": close_price,
        "high": float(row["high"]) if "high" in row else None,
        "low": float(row["low"]) if "low" in row else None,
        "change_pct": change_pct,
        # 腾讯接口的 amount 字段是成交量（手），除以 1 亿换算为亿手
        "amount_yi": round(float(row["amount"]) / 100000000, 2) if "amount" in row else 0,
    }

def fetch_index_from_sina(symbol: str, target_date: str) -> Dict:
    """
    从新浪财经获取指数数据（备选数据源）
    
    Args:
        symbol: 指数代码
        target_date: 目标日期
        
    Returns:
        指数数据字典
    """
    # 新浪接口使用不同代码格式
    sina_symbol = f"sh{symbol}" if symbol.startswith("0") else f"sz{symbol}"
    
    # 获取数据（该接口获取全部历史数据，但只取最后几行）
    df = ak.stock_zh_index_daily_tx(symbol=sina_symbol)
    
    if df is None or df.empty:
        raise ValueError(f"新浪数据源返回空数据")
    
    # 只保留最近30天的数据以提高性能
    df = df.tail(30).copy()
    
    # 筛选目标日期
    df["date"] = df["date"].astype(str)
    target_df = df[df["date"] == target_date]
    
    if target_df.empty:
        raise ValueError(f"新浪数据源无 {target_date} 数据")
    
    row = target_df.iloc[0]
    close_price = float(row["close"])
    
    # 新浪接口没有 change_pct 字段，需要计算涨跌幅
    # 从已获取的数据中找到前一日
    prev_close = None
    sorted_df = df.sort_values("date")
    for i, r in enumerate(sorted_df.itertuples()):
        if str(r.date) == target_date and i > 0:
            prev_close = float(sorted_df.iloc[i-1]["close"])
            break
    
    # 计算涨跌幅
    if prev_close and prev_close > 0:
        change_pct = round((close_price - prev_close) / prev_close * 100, 2)
    else:
        change_pct = 0.0
    
    return {
        "open": float(row["open"]) if "open" in row else None,
        "close": close_price,
        "high": float(row["high"]) if "high" in row else None,
        "low": float(row["low"]) if "low" in row else None,
        "change_pct": change_pct,
        # 腾讯/新浪接口的 amount 字段是成交量（手），除以 1 亿换算为亿手
        "amount_yi": round(float(row["amount"]) / 100000000, 2) if "amount" in row else 0,
    }


def register_index_datasources():
    """注册指数数据源"""
    manager = get_manager()
    
    # 注册腾讯数据源（优先级 0，数据更新最快）
    manager.register(
        "index_daily",
        DataSource(
            name="tencent",
            fetch_func=fetch_index_from_tx,
            priority=0,
            retry_count=3,
            retry_delay=2.0,
        )
    )
    
    # 注册东财数据源（优先级 1）
    manager.register(
        "index_daily",
        DataSource(
            name="eastmoney",
            fetch_func=fetch_index_from_eastmoney,
            priority=1,
            retry_count=3,
            retry_delay=2.0,
        )
    )
    
    # 注册新浪数据源（优先级 2，备用）
    manager.register(
        "index_daily",
        DataSource(
            name="sina",
            fetch_func=fetch_index_from_sina,
            priority=2,
            retry_count=3,
            retry_delay=2.0,
        )
    )


def sync_index_daily(date: str = None):
    """
    同步三大指数数据（支持多数据源自动降级）
    
    Args:
        date: 指定日期（可选，默认为今天）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步三大指数数据: {target_date}")

    # 注册数据源
    register_index_datasources()
    manager = get_manager()

    # 三大指数代码
    index_codes = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
    }

    records = []
    
    for code, name in index_codes.items():
        try:
            # 使用数据源管理器获取数据（自动降级）
            data = manager.fetch("index_daily", code, target_date)
            
            record = {
                "date": target_date,
                "code": code,
                "name": name,
                "open": data.get("open"),
                "close": data["close"],
                "high": data.get("high"),
                "low": data.get("low"),
                "change_pct": data["change_pct"],
                "amount_yi": data["amount_yi"],
            }
            records.append(record)
            log_debug(f"{name}: 开盘 {record['open']}, 收盘 {record['close']}, 涨跌幅 {record['change_pct']}%")

        except Exception as e:
            log_error(f"同步 {name}({code}) 失败: {e}")

    if records:
        save_index_daily(records)
        log_info(f"三大指数数据同步完成: {len(records)} 条记录")
    else:
        log_error("三大指数数据同步失败: 没有获取到任何数据")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="三大指数数据同步")
    parser.add_argument("--date", help="指定日期")
    
    args = parser.parse_args()
    sync_index_daily(date=args.date)
