"""
从 stock_daily 表聚合回补 market_stats 历史数据

stock_daily 表有完整的个股日K数据，可以从中聚合出：
- up_count / down_count / flat_count（按 change_pct 统计）
- limit_up_count / limit_down_count（change_pct >= 9.9 / <= -9.9）
- total_amount_yi（amount 字段求和转亿元）
- up_ratio（上涨比例）
"""

import argparse
from typing import List, Dict

from a_stock.db import get_connection
from a_stock.db.cache import log_info, log_error


def aggregate_market_stats_from_stock_daily(target_date: str) -> Dict:
    """
    从 stock_daily 表聚合指定日期的市场统计数据

    Args:
        target_date: 目标日期（格式：YYYY-MM-DD）

    Returns:
        市场统计数据字典，若无数据则返回 None
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) as up_count,
                SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) as down_count,
                SUM(CASE WHEN change_pct = 0 THEN 1 ELSE 0 END) as flat_count,
                SUM(CASE WHEN change_pct >= 9.9 THEN 1 ELSE 0 END) as limit_up_count,
                SUM(CASE WHEN change_pct <= -9.9 THEN 1 ELSE 0 END) as limit_down_count,
                ROUND(SUM(amount) / 100000000, 2) as total_amount_yi
            FROM stock_daily
            WHERE date = ?
            """,
            (target_date,),
        )
        row = cursor.fetchone()

        if not row or row[0] == 0:
            return None

        total = row[0]
        up_count = row[1] or 0
        down_count = row[2] or 0
        flat_count = row[3] or 0
        limit_up_count = row[4] or 0
        limit_down_count = row[5] or 0
        total_amount_yi = row[6] or 0.0

        up_ratio = round(up_count / total * 100, 2) if total > 0 else 0.0

        return {
            "date": target_date,
            "total_amount_yi": total_amount_yi,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "up_ratio": up_ratio,
        }
    finally:
        conn.close()


def save_market_stats(records: List[Dict]):
    """将市场统计数据写入 market_stats 表"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO market_stats
                (date, total_amount_yi, up_count, down_count, flat_count,
                 limit_up_count, limit_down_count, up_ratio, distribution_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record["total_amount_yi"],
                    record["up_count"],
                    record["down_count"],
                    record["flat_count"],
                    record["limit_up_count"],
                    record["limit_down_count"],
                    record["up_ratio"],
                    "",
                ),
            )
        conn.commit()
        log_info(f"成功写入 {len(records)} 条市场统计数据")
    except Exception as e:
        log_error(f"写入市场统计数据失败：{e}")
        conn.rollback()
    finally:
        conn.close()


def get_all_trading_dates(start_date: str = None, end_date: str = None) -> List[str]:
    """从 stock_daily 表获取所有交易日期"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if start_date and end_date:
            cursor.execute(
                "SELECT DISTINCT date FROM stock_daily WHERE date >= ? AND date <= ? ORDER BY date",
                (start_date, end_date),
            )
        elif start_date:
            cursor.execute(
                "SELECT DISTINCT date FROM stock_daily WHERE date >= ? ORDER BY date",
                (start_date,),
            )
        else:
            cursor.execute("SELECT DISTINCT date FROM stock_daily ORDER BY date")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def backfill_market_stats(start_date: str = None, end_date: str = None):
    """
    回补指定日期范围内的 market_stats 数据

    Args:
        start_date: 开始日期（格式：YYYY-MM-DD），None 表示全部
        end_date: 结束日期（格式：YYYY-MM-DD），None 表示全部
    """
    log_info("=" * 60)
    log_info("开始从 stock_daily 聚合回补 market_stats")
    if start_date:
        log_info(f"日期范围：{start_date} ~ {end_date or '最新'}")
    log_info("=" * 60)

    trading_dates = get_all_trading_dates(start_date, end_date)
    log_info(f"共找到 {len(trading_dates)} 个交易日")

    success_count = 0
    skip_count = 0
    records = []

    for date in trading_dates:
        stats = aggregate_market_stats_from_stock_daily(date)
        if stats:
            records.append(stats)
            success_count += 1
        else:
            log_error(f"✗ {date} 无数据，跳过")
            skip_count += 1

    if records:
        save_market_stats(records)

    log_info("=" * 60)
    log_info(f"回补完成：成功 {success_count} 天，跳过 {skip_count} 天")
    log_info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="从 stock_daily 聚合回补 market_stats 历史数据")
    parser.add_argument("--start", type=str, help="开始日期（格式：YYYY-MM-DD）")
    parser.add_argument("--end", type=str, help="结束日期（格式：YYYY-MM-DD）")
    parser.add_argument("--all", action="store_true", help="回补全部历史数据")

    args = parser.parse_args()

    if args.all:
        backfill_market_stats()
    elif args.start:
        backfill_market_stats(start_date=args.start, end_date=args.end)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
