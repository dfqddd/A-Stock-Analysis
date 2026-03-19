"""
市场概览分析脚本
获取全市场涨跌统计、成交量、成交额等数据
"""

import argparse
import json
from datetime import datetime

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error


def save_market_stats(records: list):
    """将市场统计数据写入数据库"""
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
                 limit_up_count, limit_down_count, new_high_count, new_low_count,
                 avg_turnover, total_volume, up_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record.get("total_amount"),  # total_amount 对应 total_amount_yi
                    record.get("up_count"),
                    record.get("down_count"),
                    record.get("flat_count"),
                    record.get("limit_up_count"),
                    record.get("limit_down_count"),
                    record.get("new_high_count", 0),
                    record.get("new_low_count", 0),
                    record.get("avg_turnover", 0),
                    record.get("total_volume", 0),
                    record.get("up_ratio", 0),
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条市场统计数据")
    finally:
        conn.close()


def sync_market_stats(date: str = None):
    """
    同步市场统计数据

    Args:
        date: 指定日期（可选）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步市场统计数据: {target_date}")

    try:
        # 获取全市场行情数据
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            log_error("获取市场数据失败")
            return

        # 计算涨跌数量
        up_count = len(df[df["涨跌幅"] > 0])
        down_count = len(df[df["涨跌幅"] < 0])
        flat_count = len(df[df["涨跌幅"] == 0])

        # 从 limit_up_detail 表获取准确的涨停和跌停数据（带重试机制）
        limit_up_count = 0
        limit_down_count = 0
        
        # 重试3次，每次等待2秒（给 sync_limit_up 任务留出写入时间）
        import time
        for attempt in range(3):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # 先检查 limit_up_detail 表是否有数据
                check_result = cursor.execute(
                    "SELECT COUNT(*) as c FROM limit_up_detail WHERE date = ?",
                    (target_date,)
                ).fetchone()
                total_records = check_result["c"] if check_result else 0
                
                if total_records > 0:
                    # 有数据，获取涨停数（兼容中英文status）
                    result = cursor.execute(
                        "SELECT COUNT(*) as c FROM limit_up_detail WHERE date = ? AND (status = '涨停' OR status = 'limit_up')",
                        (target_date,)
                    ).fetchone()
                    limit_up_count = result["c"] if result else 0
                    
                    # 获取跌停数
                    result = cursor.execute(
                        "SELECT COUNT(*) as c FROM limit_up_detail WHERE date = ? AND status = '跌停'",
                        (target_date,)
                    ).fetchone()
                    limit_down_count = result["c"] if result else 0
                    
                    conn.close()
                    log_debug(f"从 limit_up_detail 获取涨跌停数据成功: 涨停{limit_up_count}, 跌停{limit_down_count}")
                    break
                else:
                    conn.close()
                    if attempt < 2:  # 不是最后一次尝试
                        log_debug(f"limit_up_detail 表暂无数据，等待2秒后重试 ({attempt + 1}/3)...")
                        time.sleep(2)
                    else:
                        log_error(f"limit_up_detail 表没有 {target_date} 的数据，请确保先执行 sync_limit_up")
                        
            except Exception as e:
                log_debug(f"从 limit_up_detail 获取涨跌停数据失败 (尝试 {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(2)

        # 计算创新高/新低数量
        new_high_count = len(df[df["最高"] >= df["昨收"] * 1.09])
        new_low_count = len(df[df["最低"] <= df["昨收"] * 0.91])

        # 计算平均换手率
        avg_turnover = df["换手率"].mean() if "换手率" in df.columns else 0

        # 计算总成交额和成交量
        total_amount = df["成交额"].sum() if "成交额" in df.columns else 0
        total_volume = df["成交量"].sum() if "成交量" in df.columns else 0

        # 计算上涨比例
        total = up_count + down_count + flat_count
        up_ratio = round(up_count / total * 100, 2) if total > 0 else 0

        record = {
            "date": target_date,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "new_high_count": new_high_count,
            "new_low_count": new_low_count,
            "avg_turnover": round(avg_turnover, 2),
            "total_volume": round(total_volume / 10000, 2),  # 转换为万股
            "up_ratio": up_ratio,
            "total_amount": round(total_amount / 100000000, 2),  # 转换为亿元
        }

        save_market_stats([record])
        log_info(f"市场统计: 上涨 {up_count}, 下跌 {down_count}, 涨停 {limit_up_count}, 跌停 {limit_down_count}")

    except Exception as e:
        log_error(f"同步市场统计失败: {e}")


def get_market_overview(date: str = None) -> dict:
    """
    获取市场概览

    Args:
        date: 指定日期（可选）

    Returns:
        市场概览数据
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 获取市场统计
        stats = cursor.execute(
            "SELECT * FROM market_stats WHERE date = ?", (target_date,)
        ).fetchone()

        if not stats:
            log_debug(f"无 {target_date} 市场统计数据，请先同步")
            return {}

        total = stats["up_count"] + stats["down_count"] + stats["flat_count"]

        return {
            "date": target_date,
            "market_bread": {
                "up_count": stats["up_count"],
                "down_count": stats["down_count"],
                "flat_count": stats["flat_count"],
                "up_ratio": stats["up_ratio"],
                "down_ratio": round(stats["down_count"] / total * 100, 2) if total > 0 else 0,
            },
            "limit_move": {
                "limit_up": stats["limit_up_count"],
                "limit_down": stats["limit_down_count"],
            },
            "turnover": {
                "total_amount": stats["total_amount_yi"],
            },
        }

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="市场概览分析")
    parser.add_argument("--sync", action="store_true", help="同步数据")
    parser.add_argument("--analyze", action="store_true", help="分析数据")
    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")

    args = parser.parse_args()

    if args.sync:
        sync_market_stats(date=args.date)
    elif args.analyze:
        result = get_market_overview(date=args.date)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"市场概览 ({result.get('date', 'N/A')})")
            mb = result.get("market_bread", {})
            print(f"涨跌比: 上涨 {mb.get('up_count', 0)} ({mb.get('up_ratio', 0)}%), "
                  f"下跌 {mb.get('down_count', 0)} ({mb.get('down_ratio', 0)}%)")
            lm = result.get("limit_move", {})
            print(f"涨跌停: 涨停 {lm.get('limit_up', 0)}, 跌停 {lm.get('limit_down', 0)}")
    else:
        sync_market_stats(date=args.date)
        result = get_market_overview(date=args.date)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
