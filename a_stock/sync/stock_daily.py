"""
个股日K线数据同步脚本

数据来源：
  - Tushare Pro（主数据源，优先级 0）- 批量获取，一次请求5000+只股票
  - 腾讯/东财股票数据（备选数据源，优先级 1）- 使用 AKShare 通用接口
  - 新浪股票数据（备选数据源，优先级 2）
"""

import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd
import tushare as ts

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error, get_latest_date
from a_stock.db.repository import StockDailyRepository
from a_stock.db.datasource import DataSource, get_manager


def fetch_stock_daily_tushare(trade_date: str) -> List[Dict]:
    """
    使用 Tushare Pro 批量获取日K数据（主数据源）
    
    优势：一次请求获取所有 5000+ 只股票的日K数据
    
    Args:
        trade_date: 交易日期 (YYYY-MM-DD)
        
    Returns:
        日K数据列表
    """
    try:
        # 初始化 Tushare Pro
        pro = ts.pro_api('11e60f09feabbe8dd7daeb63005a1348c3d02a2c1285ec0ff7e82388')
        
        # 转换日期格式
        date_str = trade_date.replace('-', '')
        
        # 调用 Tushare Pro 的 daily 接口，一次获取所有股票
        df = pro.daily(trade_date=date_str)
        
        if df is None or df.empty:
            log_debug(f"Tushare 返回空数据: {trade_date}")
            return []
        
        records = []
        for _, row in df.iterrows():
            # Tushare 的 ts_code 格式为 000001.SZ，需要转换为 000001
            ts_code = str(row.get('ts_code', ''))
            code = ts_code.split('.')[0] if '.' in ts_code else ts_code
            
            # Tushare 日期格式为 YYYYMMDD，转换为 YYYY-MM-DD
            trade_date_raw = str(row.get('trade_date', ''))
            if len(trade_date_raw) == 8:
                formatted_date = f"{trade_date_raw[:4]}-{trade_date_raw[4:6]}-{trade_date_raw[6:]}"
            else:
                formatted_date = trade_date_raw
            
            record = {
                'code': code,
                'date': formatted_date,
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': float(row.get('vol', 0)) * 100,  # 手转股
                'amount': float(row.get('amount', 0)) * 1000,  # 千元转元
                'change_pct': float(row.get('pct_chg', 0)),
                'turnover_rate': 0.0,  # Tushare daily 接口没有换手率
            }
            records.append(record)
        
        log_debug(f"Tushare 成功获取 {len(records)} 条记录")
        return records
        
    except Exception as e:
        log_debug(f"Tushare 获取数据失败: {e}")
        raise


def fetch_stock_daily_tencent(code: str, days: int = 30) -> List[Dict]:
    """
    使用腾讯/东财数据源获取日K数据（备选数据源）
    
    Args:
        code: 股票代码（如 000001）
        days: 获取最近多少天的数据

    Returns:
        日K数据列表
    """
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")

        if df is None or df.empty:
            return []

        if days and len(df) > days:
            df = df.tail(days)

        column_mapping = {
            "date": "date", "日期": "date",
            "open": "open", "开盘": "open",
            "high": "high", "最高": "high",
            "low": "low", "最低": "low",
            "close": "close", "收盘": "close",
            "volume": "volume", "成交量": "volume",
            "amount": "amount", "成交额": "amount",
            "change_pct": "change_pct", "涨跌幅": "change_pct",
            "turnover_rate": "turnover_rate", "换手率": "turnover_rate",
        }

        df = df.rename(columns=column_mapping)

        required_fields = ["date", "open", "high", "low", "close", "volume"]
        for field in required_fields:
            if field not in df.columns:
                log_debug(f"缺少必要字段: {field}")
                return []

        records = []
        for _, row in df.iterrows():
            record = {
                "code": code,
                "date": str(row.get("date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
                "amount": float(row.get("amount", 0) or 0),
                "change_pct": float(row.get("change_pct", 0) or 0),
                "turnover_rate": float(row.get("turnover_rate", 0) or 0),
            }
            records.append(record)

        return records
    except Exception as e:
        log_debug(f"腾讯数据源获取 {code} 失败: {e}")
        raise


def fetch_stock_daily_sina(code: str, days: int = 30) -> List[Dict]:
    """
    使用新浪数据源获取日K数据（备选）
    
    Args:
        code: 股票代码（如 000001）
        days: 获取最近多少天的数据
    
    Returns:
        日K数据列表
    """
    try:
        # 新浪数据源需要使用 sh/sz 前缀
        if code.startswith('6'):
            symbol = f"sh{code}"
        else:
            symbol = f"sz{code}"
        
        df = ak.stock_zh_a_daily(symbol=symbol)
        
        if df is None or df.empty:
            return []
        
        if days and len(df) > days:
            df = df.tail(days)
        
        column_mapping = {
            "date": "date", 
            "open": "open", 
            "high": "high", 
            "low": "low", 
            "close": "close", 
            "volume": "volume", 
            "amount": "amount", 
            "outstanding_share": "outstanding_share",
            "turnover": "turnover",
        }
        
        df = df.rename(columns=column_mapping)
        
        required_fields = ["date", "open", "high", "low", "close", "volume"]
        for field in required_fields:
            if field not in df.columns:
                log_debug(f"新浪数据源缺少必要字段: {field}")
                return []
        
        records = []
        for _, row in df.iterrows():
            record = {
                "code": code,
                "date": str(row.get("date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
                "amount": float(row.get("amount", 0) or 0),
                "change_pct": 0.0,  # 新浪数据源没有涨跌幅字段
                "turnover_rate": float(row.get("turnover", 0) or 0),
            }
            records.append(record)
        
        return records
    except Exception as e:
        log_debug(f"新浪数据源获取 {code} 失败: {e}")
        raise


def fetch_stock_daily_tencent(code: str, days: int = 30) -> List[Dict]:
    """
    使用腾讯/东财数据源获取日K数据（主数据源，通过AKShare通用接口）
    
    Args:
        code: 股票代码（如 000001）
        days: 获取最近多少天的数据

    Returns:
        日K数据列表
    """
    try:
        # 使用AKShare的通用日K接口（东财数据源）
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")

        if df is None or df.empty:
            return []

        if days and len(df) > days:
            df = df.tail(days)

        column_mapping = {
            "date": "date", "日期": "date",
            "open": "open", "开盘": "open",
            "high": "high", "最高": "high",
            "low": "low", "最低": "low",
            "close": "close", "收盘": "close",
            "volume": "volume", "成交量": "volume",
            "amount": "amount", "成交额": "amount",
            "change_pct": "change_pct", "涨跌幅": "change_pct",
            "turnover_rate": "turnover_rate", "换手率": "turnover_rate",
        }

        df = df.rename(columns=column_mapping)

        required_fields = ["date", "open", "high", "low", "close", "volume"]
        for field in required_fields:
            if field not in df.columns:
                log_debug(f"缺少必要字段: {field}")
                return []

        records = []
        for _, row in df.iterrows():
            record = {
                "code": code,
                "date": str(row.get("date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
                "amount": float(row.get("amount", 0) or 0),
                "change_pct": float(row.get("change_pct", 0) or 0),
                "turnover_rate": float(row.get("turnover_rate", 0) or 0),
            }
            records.append(record)

        return records
    except Exception as e:
        log_debug(f"腾讯/东财数据源获取 {code} 失败: {e}")
        raise


def register_datasources():
    """注册数据源到管理器"""
    manager = get_manager()
    
    # 注册腾讯/东财数据源（优先级 0，最高）- 使用AKShare通用接口
    manager.register(
        "stock_daily",
        DataSource(
            name="tencent",
            fetch_func=fetch_stock_daily_tencent,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )
    
    # 注册新浪数据源（优先级 1）
    manager.register(
        "stock_daily",
        DataSource(
            name="sina",
            fetch_func=fetch_stock_daily_sina,
            priority=1,
            retry_count=3,
            retry_delay=1.0,
        )
    )


def sync_stock_daily(code: str = None, date: str = None, days: int = 30):
    """
    同步个股日K数据（智能增量同步）
    
    优先使用 Tushare Pro 批量接口（一次获取所有股票），
    如果 Tushare 失败则回退到 AKShare 逐只获取。
    
    Args:
        code: 股票代码（可选，不传则同步全部）
        date: 指定日期（可选）
        days: 同步最近多少天（默认30天，仅对 AKShare 数据源有效）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步个股日K数据: {target_date}")
    
    # 获取 Repository
    repository = StockDailyRepository()
    
    # 优先尝试使用 Tushare Pro 批量获取（如果未指定单只股票）
    if code is None:
        try:
            log_info("尝试使用 Tushare Pro 批量获取...")
            records = fetch_stock_daily_tushare(target_date)
            
            if records:
                # 过滤已存在的数据
                filtered_records = []
                for record in records:
                    stock_code = record.get('code')
                    record_date = record.get('date')
                    
                    # 检查是否已存在
                    existing = repository.find_by_id(date=record_date, code=stock_code)
                    if not existing:
                        filtered_records.append(record)
                
                if filtered_records:
                    repository.save_batch(filtered_records)
                    log_info(f"Tushare 批量同步完成: 新增 {len(filtered_records)} 条记录")
                else:
                    log_info("Tushare 数据已是最新，无需更新")
                return
            else:
                log_info("Tushare 返回空数据，回退到 AKShare 数据源")
                
        except Exception as e:
            log_error(f"Tushare 批量获取失败: {e}，回退到 AKShare 数据源")
    
    # 使用 AKShare 数据源（逐只获取）
    log_info("使用 AKShare 数据源逐只获取...")
    
    # 注册数据源
    register_datasources()
    
    # 获取股票列表
    conn = get_connection()
    cursor = conn.cursor()
    
    if code:
        stocks = cursor.execute(
            "SELECT code, name FROM stock_info WHERE code = ?", (code,)
        ).fetchall()
    else:
        stocks = cursor.execute(
            "SELECT code, name FROM stock_info"
        ).fetchall()
    
    conn.close()
    
    if not stocks:
        log_debug("没有找到股票信息，请先同步 stock_info")
        return
    
    total = len(stocks)
    success = 0
    failed = 0
    skipped = 0
    total_records = 0
    
    manager = get_manager()
    
    for i, stock in enumerate(stocks):
        stock_code = stock[0]
        stock_name = stock[1]
        
        try:
            # 查询该股票在数据库中的最新日期
            latest_date = repository.find_latest_date(stock_code)
            
            # 计算需要同步的天数
            if latest_date:
                # 计算从最新日期到今天的天数差
                from datetime import datetime as dt
                # 处理不同日期格式（20260313 或 2026-03-13）
                if len(latest_date) == 8 and '-' not in latest_date:
                    latest_dt = dt.strptime(latest_date, "%Y%m%d")
                else:
                    latest_dt = dt.strptime(latest_date, "%Y-%m-%d")
                target_dt = dt.strptime(target_date, "%Y-%m-%d")
                days_to_sync = (target_dt - latest_dt).days
                
                if days_to_sync <= 0:
                    # 数据已是最新的，跳过
                    skipped += 1
                    continue
                
                # 同步最新日期之后的数据
                records = manager.fetch("stock_daily", stock_code, days=days_to_sync)
            else:
                # 数据库中没有该股票数据，同步最近 days 天
                records = manager.fetch("stock_daily", stock_code, days=days)
            
            if records:
                # 过滤掉已存在的数据（只保留最新日期之后的）
                if latest_date:
                    records = [r for r in records if r.get("date", "") > latest_date]
                
                if records:
                    repository.save_batch(records)
                    total_records += len(records)
                    success += 1
                else:
                    skipped += 1
            else:
                failed += 1
        
        except Exception as e:
            log_error(f"同步 {stock_code} {stock_name} 失败: {e}")
            failed += 1
        
        # 每 100 只股票打印一次进度
        if (i + 1) % 100 == 0:
            log_info(f"进度: {i + 1}/{total}, 成功: {success}, 跳过: {skipped}, 失败: {failed}")
    
    log_info(f"日K数据同步完成: 总计 {total}, 成功 {success}, 跳过 {skipped}, 失败 {failed}, 新增记录 {total_records} 条")


def main():
    parser = argparse.ArgumentParser(description="同步个股日K数据")
    parser.add_argument("--code", help="指定股票代码")
    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--days", type=int, default=30, help="同步最近多少天")

    args = parser.parse_args()
    sync_stock_daily(code=args.code, date=args.date, days=args.days)


if __name__ == "__main__":
    main()
