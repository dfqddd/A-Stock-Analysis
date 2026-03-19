"""
历史数据回填脚本

用于补全历史数据，支持：
- 指定年份回填
- 指定日期范围回填
- 全量回填
"""

import argparse
from datetime import datetime, timedelta
from typing import List, Optional
import time

from a_stock.db.cache import log_info, log_debug, log_error
from a_stock.sync.stock_daily import sync_stock_daily
from a_stock.sync.stock_info import sync_stock_info
from a_stock.sync.limit_up import sync_limit_up


def get_trading_days(year: int) -> List[str]:
    """
    获取指定年份的交易日列表
    
    Args:
        year: 年份
        
    Returns:
        交易日列表 ['2024-01-02', '2024-01-03', ...]
    """
    try:
        import akshare as ak
        # 获取交易日历
        df = ak.tool_trade_date_hist_sina()
        
        # 筛选指定年份
        trading_days = []
        for date_str in df['trade_date'].astype(str).tolist():
            if date_str.startswith(str(year)):
                trading_days.append(date_str)
                
        log_debug(f"{year} 年共有 {len(trading_days)} 个交易日")
        return trading_days
        
    except Exception as e:
        log_error(f"获取交易日历失败: {e}")
        # 返回空列表，后续会跳过
        return []


def backfill_year(year: int, skip_details: bool = False, delay: float = 0.5):
    """
    回填指定年份的历史数据

    Args:
        year: 年份
        skip_details: 是否跳过详情获取
        delay: 每次请求间隔（秒），避免请求过快
    """
    log_info(f"开始回填 {year} 年历史数据...")

    # 获取交易日列表
    trading_days = get_trading_days(year)
    
    if not trading_days:
        log_error(f"无法获取 {year} 年交易日，跳过")
        return

    success_count = 0
    fail_count = 0

    for i, date in enumerate(trading_days):
        try:
            log_info(f"[{i+1}/{len(trading_days)}] 回填 {date}...")
            
            # 回填日K数据
            sync_stock_daily(date=date, days=1)
            
            # 回填涨停数据
            sync_limit_up(date=date)
            
            success_count += 1
            
            # 避免请求过快
            time.sleep(delay)
            
        except Exception as e:
            log_error(f"回填 {date} 失败: {e}")
            fail_count += 1

    log_info(f"{year} 年历史数据回填完成: 成功 {success_count}, 失败 {fail_count}")


def backfill_date_range(start_date: str, end_date: str, skip_details: bool = False, delay: float = 0.5):
    """
    回填指定日期范围的历史数据
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        skip_details: 是否跳过详情获取
        delay: 每次请求间隔（秒）
    """
    log_info(f"开始回填 {start_date} ~ {end_date} 历史数据...")
    
    try:
        import akshare as ak
        # 获取交易日历
        df = ak.tool_trade_date_hist_sina()
        
        trading_days = []
        for date_str in df['trade_date'].astype(str).tolist():
            if start_date.replace('-', '') <= date_str <= end_date.replace('-', ''):
                trading_days.append(f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}")
                
        log_debug(f"日期范围内共有 {len(trading_days)} 个交易日")
        
        success_count = 0
        fail_count = 0
        
        for i, date in enumerate(trading_days):
            try:
                log_info(f"[{i+1}/{len(trading_days)}] 回填 {date}...")
                
                sync_stock_daily(date=date, days=1)
                sync_limit_up(date=date)
                
                success_count += 1
                time.sleep(delay)
                
            except Exception as e:
                log_error(f"回填 {date} 失败: {e}")
                fail_count += 1
                
        log_info(f"日期范围回填完成: 成功 {success_count}, 失败 {fail_count}")
        
    except Exception as e:
        log_error(f"回填日期范围失败: {e}")


def backfill_all(skip_details: bool = False):
    """
    回填所有历史数据（最近5年）
    """
    current_year = datetime.now().year

    # 先同步股票基础信息
    log_info("同步股票基础信息...")
    sync_stock_info(skip_details=skip_details)

    # 回填最近5年的数据
    for year in range(current_year - 4, current_year + 1):
        backfill_year(year, skip_details=skip_details)
        
    log_info("所有历史数据回填完成")


def main():
    parser = argparse.ArgumentParser(description="回填历史数据")
    parser.add_argument("--year", type=int, help="指定年份")
    parser.add_argument("--start-date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="回填所有历史数据（最近5年）")
    parser.add_argument("--skip-details", action="store_true", help="跳过详情获取")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔（秒）")

    args = parser.parse_args()

    if args.all:
        backfill_all(skip_details=args.skip_details)
    elif args.year:
        backfill_year(args.year, skip_details=args.skip_details, delay=args.delay)
    elif args.start_date and args.end_date:
        backfill_date_range(args.start_date, args.end_date, skip_details=args.skip_details, delay=args.delay)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
