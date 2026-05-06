"""
用 Tushare 批量回补 stock_daily 历史数据

解决问题：历史数据（2018-2025）通过 AKShare 逐只股票同步，
amount/volume 单位未转换，导致数值偏小约 10 倍。

修复方案：用 Tushare Pro 批量接口按交易日重新拉取并覆盖写入，
Tushare 的 vol（手）× 100 = 股，amount（千元）× 1000 = 元。

用法：
  # 回补指定年份
  python -m a_stock.sync.backfill_stock_daily_tushare --year 2024

  # 回补指定日期范围
  python -m a_stock.sync.backfill_stock_daily_tushare --start 2024-01-01 --end 2024-12-31

  # 回补 2018-2025 全量
  python -m a_stock.sync.backfill_stock_daily_tushare --all
"""

import argparse
import time
from datetime import datetime
from typing import List

import tushare as ts

from a_stock.db.cache import log_info, log_error, log_debug
from a_stock.db.repository import StockDailyRepository

TUSHARE_TOKEN = "11e60f09feabbe8dd7daeb63005a1348c3d02a2c1285ec0ff7e82388"


def get_trading_days(start_date: str, end_date: str) -> List[str]:
    """
    获取指定日期范围内的交易日列表（YYYY-MM-DD 格式）

    优先从本地 stock_daily 表获取，若本地无数据则从 Tushare 交易日历获取。

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        交易日列表，如 ['2024-01-02', '2024-01-03', ...]
    """
    from a_stock.db.cache import get_connection

    # 优先从本地 stock_daily 获取
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT date FROM stock_daily WHERE date >= ? AND date <= ? ORDER BY date",
        (start_date, end_date),
    )
    trading_days = [row[0] for row in cursor.fetchall()]
    conn.close()

    if trading_days:
        return trading_days

    # 本地无数据，从 AKShare 交易日历获取
    log_info(f"本地无 {start_date}~{end_date} 数据，从 AKShare 交易日历获取")
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        start_compact = start_date.replace("-", "")
        end_compact = end_date.replace("-", "")
        all_days = sorted(df['trade_date'].astype(str).tolist())
        for d in all_days:
            if start_compact <= d <= end_compact:
                trading_days.append(f"{d[:4]}-{d[4:6]}-{d[6:8]}")
        log_info(f"从 AKShare 获取到 {len(trading_days)} 个交易日")
    except Exception as e:
        log_error(f"从 AKShare 获取交易日历失败: {e}")

    return trading_days


def fetch_and_save_one_day(pro, repository: StockDailyRepository, trade_date: str) -> int:
    """
    从 Tushare 拉取指定交易日的全市场日K数据并覆盖写入数据库

    Args:
        pro: Tushare Pro API 实例
        repository: StockDailyRepository 实例
        trade_date: 交易日期 YYYY-MM-DD

    Returns:
        写入记录数
    """
    date_compact = trade_date.replace("-", "")

    # 带限频重试：最多重试 3 次，遇到限频时等待 60 秒
    max_retries = 3
    df = None
    for attempt in range(max_retries):
        try:
            df = pro.daily(trade_date=date_compact)
            break
        except Exception as retry_error:
            error_msg = str(retry_error)
            if "每分钟最多访问" in error_msg:
                wait_seconds = 65
                log_info(f"{trade_date} 触发限频，等待 {wait_seconds}s 后重试 ({attempt + 1}/{max_retries})")
                time.sleep(wait_seconds)
            else:
                raise

    if df is None or df.empty:
        log_debug(f"{trade_date} Tushare 返回空数据，跳过")
        return 0

    records = []
    for _, row in df.iterrows():
        ts_code = str(row.get("ts_code", ""))
        code = ts_code.split(".")[0] if "." in ts_code else ts_code

        record = {
            "code": code,
            "date": trade_date,
            "open": float(row.get("open", 0) or 0),
            "high": float(row.get("high", 0) or 0),
            "low": float(row.get("low", 0) or 0),
            "close": float(row.get("close", 0) or 0),
            "volume": float(row.get("vol", 0) or 0) * 100,   # 手 → 股
            "amount": float(row.get("amount", 0) or 0) * 1000,  # 千元 → 元
            "change_pct": float(row.get("pct_chg", 0) or 0),
            "turnover_rate": 0.0,
        }
        records.append(record)

    repository.save_batch(records)
    return len(records)


def backfill_date_range(start_date: str, end_date: str, delay: float = 1.5):
    """
    回补指定日期范围的 stock_daily 数据

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        delay: 每次请求间隔秒数，避免触发 Tushare 频率限制
    """
    log_info(f"开始回补 stock_daily: {start_date} ~ {end_date}")

    log_info("获取交易日历...")
    trading_days = get_trading_days(start_date, end_date)
    log_info(f"共 {len(trading_days)} 个交易日需要回补")

    pro = ts.pro_api(TUSHARE_TOKEN)
    repository = StockDailyRepository()

    success_count = 0
    fail_count = 0
    total_records = 0

    for index, trade_date in enumerate(trading_days):
        try:
            count = fetch_and_save_one_day(pro, repository, trade_date)
            total_records += count
            success_count += 1

            if (index + 1) % 10 == 0 or index == 0:
                log_info(
                    f"进度 [{index + 1}/{len(trading_days)}] {trade_date}"
                    f" 本日写入 {count} 条，累计 {total_records} 条"
                )

            time.sleep(delay)

        except Exception as error:
            log_error(f"回补 {trade_date} 失败: {error}")
            fail_count += 1
            # 失败后稍作等待再继续
            time.sleep(delay * 3)

    log_info(
        f"回补完成: 成功 {success_count} 天，失败 {fail_count} 天，"
        f"共写入 {total_records} 条记录"
    )


def backfill_year(year: int, delay: float = 1.5):
    """回补指定年份"""
    backfill_date_range(
        start_date=f"{year}-01-01",
        end_date=f"{year}-12-31",
        delay=delay,
    )


def backfill_all(delay: float = 1.5):
    """回补 2018-2025 年全量数据"""
    for year in range(2018, 2026):
        log_info(f"===== 开始回补 {year} 年 =====")
        backfill_year(year, delay=delay)
        log_info(f"===== {year} 年回补完成 =====")


def main():
    parser = argparse.ArgumentParser(description="用 Tushare 回补 stock_daily 历史数据")
    parser.add_argument("--year", type=int, help="回补指定年份，如 2024")
    parser.add_argument("--start", help="回补开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="回补结束日期 YYYY-MM-DD")
    parser.add_argument("--all", action="store_true", help="回补 2018-2025 年全量数据")
    parser.add_argument("--delay", type=float, default=1.5, help="请求间隔秒数（默认 1.5，Tushare 限频 50次/分钟）")

    args = parser.parse_args()

    if args.all:
        backfill_all(delay=args.delay)
    elif args.year:
        backfill_year(args.year, delay=args.delay)
    elif args.start and args.end:
        backfill_date_range(args.start, args.end, delay=args.delay)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
