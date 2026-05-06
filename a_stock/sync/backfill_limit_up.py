
"""
历史涨停跌停数据回填脚本

数据来源：
  1. 东财涨停接口（只能获取最近几个月的数据）
  2. 日K数据推导（通过涨跌幅判断涨停跌停）

涨停跌停判断规则：
  - 主板：±10%
  - 科创板（688xxx）：±20%
  - 创业板注册制（300xxx且2020-08-24之后）：±20%
  - ST股：±5%
"""

import argparse
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

import akshare as ak

from a_stock.db import get_connection, DB_PATH
from a_stock.db.cache import log_info, log_debug, log_error


def get_trading_days(start_year: int = 2018, end_year: int = None) -> List[str]:
    """
    获取交易日列表
    
    Args:
        start_year: 开始年份
        end_year: 结束年份
        
    Returns:
        交易日列表 ['2018-01-02', ...]
    """
    if end_year is None:
        end_year = datetime.now().year
    
    try:
        df = ak.tool_trade_date_hist_sina()
        
        trading_days = []
        for trade_date in df['trade_date'].tolist():
            # trade_date 可能是 datetime.date 对象或字符串
            if hasattr(trade_date, 'year'):
                # datetime.date 对象
                year = trade_date.year
                date_str = trade_date.strftime("%Y-%m-%d")
            else:
                # 字符串格式 YYYYMMDD
                date_str = str(trade_date)
                if len(date_str) == 8:
                    year = int(date_str[:4])
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    continue
            
            if start_year <= year <= end_year:
                trading_days.append(date_str)
        
        log_debug(f"共获取 {len(trading_days)} 个交易日")
        return trading_days
        
    except Exception as e:
        log_error(f"获取交易日历失败: {e}")
        return []


def is_limit_up(code: str, change_pct: float, name: str = "", date: str = "") -> bool:
    """
    判断是否涨停

    Args:
        code: 股票代码
        change_pct: 涨跌幅（%）
        name: 股票名称（用于判断ST股）
        date: 日期（用于判断创业板注册制）

    Returns:
        是否涨停
    """
    # ST股（涨跌幅限制5%）
    if "ST" in name.upper() or "*ST" in name.upper():
        return change_pct >= 4.9

    # 科创板（688/689开头，涨跌幅限制20%）
    if code.startswith("688") or code.startswith("689"):
        return change_pct >= 19.9

    # 创业板注册制（300/301/302开头，2020-08-24之后涨跌幅限制20%）
    if code.startswith("300") or code.startswith("301") or code.startswith("302"):
        if date >= "2020-08-24":
            return change_pct >= 19.9
        else:
            return change_pct >= 9.9

    # 北交所（8开头6位代码，涨跌幅限制30%）
    if code.startswith("8") and len(code) == 6:
        return change_pct >= 29.9

    # 主板（涨跌幅限制10%）
    return change_pct >= 9.99


def is_limit_down(code: str, change_pct: float, name: str = "", date: str = "") -> bool:
    """
    判断是否跌停

    Args:
        code: 股票代码
        change_pct: 涨跌幅（%）
        name: 股票名称（用于判断ST股）
        date: 日期（用于判断创业板注册制）

    Returns:
        是否跌停
    """
    # ST股（涨跌幅限制5%）
    if "ST" in name.upper() or "*ST" in name.upper():
        return change_pct <= -4.9

    # 科创板（688/689开头，涨跌幅限制20%）
    if code.startswith("688") or code.startswith("689"):
        return change_pct <= -19.9

    # 创业板注册制（300/301/302开头，2020-08-24之后涨跌幅限制20%）
    if code.startswith("300") or code.startswith("301") or code.startswith("302"):
        if date >= "2020-08-24":
            return change_pct <= -19.9
        else:
            return change_pct <= -9.9

    # 北交所（8开头6位代码，涨跌幅限制30%）
    if code.startswith("8") and len(code) == 6:
        return change_pct <= -29.9

    # 主板（涨跌幅限制10%）
    return change_pct <= -9.99


def get_limit_from_daily(date: str) -> List[Dict]:
    """
    从日K数据推导涨停跌停信息
    
    Args:
        date: 日期 (YYYY-MM-DD)
        
    Returns:
        涨停跌停记录列表
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 查询当天所有股票的日K数据
        rows = cursor.execute(
            """
            SELECT sd.code, si.name, sd.close, sd.volume, sd.amount, 
                   sd.turnover_rate, sd.change_pct
            FROM stock_daily sd
            LEFT JOIN stock_info si ON sd.code = si.code
            WHERE sd.date = ?
            """,
            (date,)
        ).fetchall()
        
        records = []
        for row in rows:
            code = row[0]
            name = row[1] or ""
            close = row[2]
            volume = row[3]
            amount = row[4]
            turnover_rate = row[5]
            change_pct = row[6]
            
            if change_pct is None:
                continue
            
            # 判断涨停
            if is_limit_up(code, change_pct, name, date):
                records.append({
                    "date": date,
                    "code": code,
                    "name": name,
                    "status": "涨停",
                    "change_pct": change_pct,
                    "close": close,
                    "limit_up_price": close,
                    "amount_yi": amount / 100000000 if amount else 0,
                    "circulating_cap_yi": 0,  # 暂无数据
                    "total_cap_yi": 0,
                    "turnover_rate": turnover_rate or 0,
                    "seal_amount_yi": 0,
                    "first_seal_time": "",
                    "last_seal_time": "",
                    "broken_count": 0,
                    "continuous_board": 1,
                    "limit_up_stat": "",
                    "amplitude": change_pct,
                    "speed": 0,
                    "industry": "",
                })
            
            # 判断跌停
            elif is_limit_down(code, change_pct, name, date):
                records.append({
                    "date": date,
                    "code": code,
                    "name": name,
                    "status": "跌停",
                    "change_pct": change_pct,
                    "close": close,
                    "limit_up_price": close,
                    "amount_yi": amount / 100000000 if amount else 0,
                    "circulating_cap_yi": 0,
                    "total_cap_yi": 0,
                    "turnover_rate": turnover_rate or 0,
                    "seal_amount_yi": 0,
                    "first_seal_time": "",
                    "last_seal_time": "",
                    "broken_count": 0,
                    "continuous_board": 1,
                    "limit_up_stat": "",
                    "amplitude": change_pct,
                    "speed": 0,
                    "industry": "",
                })
        
        return records
        
    finally:
        conn.close()


def save_limit_up_detail(records: List[Dict]):
    """将涨停详情写入数据库"""
    if not records:
        return
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO limit_up_detail
                (date, code, name, status, change_pct, close, limit_up_price,
                 amount_yi, circulating_cap_yi, total_cap_yi, turnover_rate,
                 seal_amount_yi, first_seal_time, last_seal_time, broken_count,
                 continuous_board, limit_up_stat, amplitude, speed, industry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record["code"],
                    record["name"],
                    record.get("status", "涨停"),
                    record.get("change_pct"),
                    record.get("close"),
                    record.get("limit_up_price"),
                    record.get("amount_yi"),
                    record.get("circulating_cap_yi"),
                    record.get("total_cap_yi"),
                    record.get("turnover_rate"),
                    record.get("seal_amount_yi"),
                    record.get("first_seal_time"),
                    record.get("last_seal_time"),
                    record.get("broken_count", 0),
                    record.get("continuous_board", 1),
                    record.get("limit_up_stat"),
                    record.get("amplitude"),
                    record.get("speed"),
                    record.get("industry"),
                ),
            )
        
        conn.commit()
        
    finally:
        conn.close()


def backfill_limit_up(start_year: int = 2018, end_year: int = None, delay: float = 0.1):
    """
    回填涨停跌停历史数据
    
    Args:
        start_year: 开始年份
        end_year: 结束年份
        delay: 每次请求间隔（秒）
    """
    if end_year is None:
        end_year = datetime.now().year
    
    log_info(f"开始回填 {start_year}-{end_year} 年涨停跌停历史数据...")
    
    # 获取交易日列表
    trading_days = get_trading_days(start_year, end_year)
    
    if not trading_days:
        log_error("无法获取交易日，跳过")
        return
    
    # 检查已有数据的日期范围
    conn = get_connection()
    cursor = conn.cursor()
    existing_dates = set(
        row[0] for row in cursor.execute(
            "SELECT DISTINCT date FROM limit_up_detail"
        ).fetchall()
    )
    conn.close()
    
    log_info(f"已有数据的日期数: {len(existing_dates)}")
    
    total = len(trading_days)
    success = 0
    skipped = 0
    failed = 0
    total_records = 0
    
    for i, date in enumerate(trading_days):
        try:
            # 跳过已有数据
            if date in existing_dates:
                skipped += 1
                continue
            
            # 从日K数据推导涨停跌停
            records = get_limit_from_daily(date)
            
            if records:
                save_limit_up_detail(records)
                total_records += len(records)
                log_debug(f"[{i+1}/{total}] {date}: 写入 {len(records)} 条记录")
            else:
                log_debug(f"[{i+1}/{total}] {date}: 无涨停跌停数据")
            
            success += 1
            
            # 每100个交易日打印进度
            if (i + 1) % 100 == 0:
                log_info(f"进度: {i+1}/{total}, 成功: {success}, 跳过: {skipped}, 失败: {failed}, 总记录: {total_records}")
            
            # 延迟（避免CPU占用过高）
            if delay > 0:
                time.sleep(delay)
            
        except Exception as e:
            log_error(f"回填 {date} 失败: {e}")
            failed += 1
    
    log_info(f"回填完成: 总计 {total}, 成功 {success}, 跳过 {skipped}, 失败 {failed}, 总记录 {total_records} 条")


def backfill_from_eastmoney(days: int = 30):
    """
    从东财接口回填最近的涨停跌停数据（带详细信息）
    
    Args:
        days: 回填最近多少天
    """
    log_info(f"从东财回填最近 {days} 天的涨停跌停数据...")
    
    from a_stock.sync.limit_up import sync_limit_up
    
    # 获取交易日
    trading_days = get_trading_days()
    recent_days = trading_days[-days:] if len(trading_days) >= days else trading_days
    
    for date in recent_days:
        try:
            sync_limit_up(date=date)
            log_debug(f"{date}: 东财数据同步完成")
            time.sleep(0.5)
        except Exception as e:
            log_error(f"{date}: 东财数据同步失败: {e}")


def update_continuous_board():
    """
    更新连板数据
    
    通过遍历每只股票的历史涨停记录，计算连续涨停天数
    """
    log_info("开始更新连板数据...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 获取所有交易日（排序）
    trading_days = [row[0] for row in cursor.execute(
        "SELECT DISTINCT date FROM limit_up_detail WHERE status='涨停' ORDER BY date"
    ).fetchall()]
    
    log_info(f"共 {len(trading_days)} 个交易日有涨停数据")
    
    # 获取所有涨停股票代码
    limit_up_codes = set(row[0] for row in cursor.execute(
        "SELECT DISTINCT code FROM limit_up_detail WHERE status='涨停'"
    ).fetchall())
    
    log_info(f"共 {len(limit_up_codes)} 只股票有过涨停")
    
    # 构建日期索引（快速查找前一个交易日）
    date_index = {d: i for i, d in enumerate(trading_days)}
    
    updated_count = 0
    
    for code in limit_up_codes:
        # 获取该股票所有涨停日期
        limit_dates = set(row[0] for row in cursor.execute(
            "SELECT date FROM limit_up_detail WHERE code=? AND status='涨停'",
            (code,)
        ).fetchall())
        
        # 计算每个日期的连板数
        for date in limit_dates:
            if date not in date_index:
                continue
            
            # 向前追溯连续涨停天数
            continuous = 1
            idx = date_index[date]
            
            while idx > 0:
                prev_date = trading_days[idx - 1]
                if prev_date in limit_dates:
                    continuous += 1
                    idx -= 1
                else:
                    break
            
            # 更新连板数
            cursor.execute(
                "UPDATE limit_up_detail SET continuous_board = ? WHERE date = ? AND code = ?",
                (continuous, date, code)
            )
            updated_count += 1
        
        # 每1000只股票提交一次
        if updated_count % 1000 == 0:
            conn.commit()
            log_debug(f"已更新 {updated_count} 条记录...")
    
    conn.commit()
    log_info(f"连板数据更新完成，共更新 {updated_count} 条记录")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="回填涨停跌停历史数据")
    parser.add_argument("--start-year", type=int, default=2018, help="开始年份")
    parser.add_argument("--end-year", type=int, help="结束年份")
    parser.add_argument("--delay", type=float, default=0.1, help="请求间隔（秒）")
    parser.add_argument("--eastmoney", action="store_true", help="使用东财接口回填最近数据")
    parser.add_argument("--days", type=int, default=30, help="东财接口回填天数")
    parser.add_argument("--update-board", action="store_true", help="更新连板数据")

    args = parser.parse_args()

    if args.update_board:
        update_continuous_board()
    elif args.eastmoney:
        backfill_from_eastmoney(days=args.days)
    else:
        backfill_limit_up(
            start_year=args.start_year,
            end_year=args.end_year,
            delay=args.delay
        )


if __name__ == "__main__":
    main()
