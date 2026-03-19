"""
A 股市场情绪分析脚本
基于 AKShare 获取市场情绪数据并输出结构化 JSON
"""

import argparse
import json
from datetime import datetime

import akshare as ak
import requests

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error


def save_sentiment(records: list):
    """将市场情绪数据写入数据库"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO sentiment
                (date, bull_bear_index, fear_greed_index, new_high_ratio, 
                 new_low_ratio, limit_up_ratio, limit_down_ratio, turnover_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record.get("bull_bear_index"),
                    record.get("fear_greed_index"),
                    record.get("new_high_ratio"),
                    record.get("new_low_ratio"),
                    record.get("limit_up_ratio"),
                    record.get("limit_down_ratio"),
                    record.get("turnover_rate"),
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条市场情绪数据")
    finally:
        conn.close()


def calc_market_stats(date: str = None) -> dict:
    """
    计算市场统计数据

    Args:
        date: 指定日期（可选，默认今天）

    Returns:
        市场统计数据
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    try:
        # 获取全市场涨跌统计
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            return {}

        # 计算涨跌数量
        up_count = len(df[df["涨跌幅"] > 0])
        down_count = len(df[df["涨跌幅"] < 0])
        flat_count = len(df[df["涨跌幅"] == 0])

        # 计算涨跌停数量
        limit_up_count = len(df[df["涨跌幅"] >= 9.9])
        limit_down_count = len(df[df["涨跌幅"] <= -9.9])

        # 计算创新高/新低数量（简化计算）
        new_high_count = len(df[df["最高"] == df["昨收"] * 1.1])  # 涨停算创新高
        new_low_count = len(df[df["最低"] == df["昨收"] * 0.9])  # 跌停算创新低

        # 计算平均换手率
        avg_turnover = df["换手率"].mean() if "换手率" in df.columns else 0

        total = up_count + down_count + flat_count

        return {
            "date": target_date,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "new_high_count": new_high_count,
            "new_low_count": new_low_count,
            "avg_turnover": avg_turnover,
            "up_ratio": up_count / total if total > 0 else 0,
            "down_ratio": down_count / total if total > 0 else 0,
        }

    except Exception as e:
        log_error(f"计算市场统计失败: {e}")
        return {}


def calc_sentiment_index(date: str = None) -> dict:
    """
    计算市场情绪指标

    Args:
        date: 指定日期（可选，默认今天）

    Returns:
        情绪指标数据
    """
    stats = calc_market_stats(date)

    if not stats:
        return {}

    # 计算多空指数（-100 到 100）
    bull_bear_index = (stats["up_ratio"] - stats["down_ratio"]) * 100

    # 计算恐惧贪婪指数（0 到 100）
    # 综合涨跌比、涨停跌停比、换手率等因素
    fear_greed_index = (
        stats["up_ratio"] * 50
        + (stats["limit_up_count"] / (stats["limit_up_count"] + stats["limit_down_count"] + 1)) * 30
        + min(stats["avg_turnover"] * 2, 20)
    )

    return {
        "date": stats["date"],
        "bull_bear_index": round(bull_bear_index, 2),
        "fear_greed_index": round(fear_greed_index, 2),
        "new_high_ratio": round(stats["new_high_count"] / (stats["up_count"] + 1), 4),
        "new_low_ratio": round(stats["new_low_count"] / (stats["down_count"] + 1), 4),
        "limit_up_ratio": round(stats["limit_up_count"] / (stats["up_count"] + 1), 4),
        "limit_down_ratio": round(stats["limit_down_count"] / (stats["down_count"] + 1), 4),
        "turnover_rate": round(stats["avg_turnover"], 4),
    }


def sync_sentiment(date: str = None):
    """
    同步市场情绪数据

    Args:
        date: 指定日期（可选）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步市场情绪数据: {target_date}")

    sentiment = calc_sentiment_index(date=target_date)

    if sentiment:
        save_sentiment([sentiment])
        log_info(f"已写入市场情绪数据: 多空指数={sentiment['bull_bear_index']}, 恐惧贪婪={sentiment['fear_greed_index']}")
    else:
        log_error("计算市场情绪失败")


def analyze_sentiment(date: str = None) -> dict:
    """
    分析市场情绪

    Args:
        date: 指定日期（可选）

    Returns:
        市场情绪分析结果
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 获取当日情绪数据
        today = cursor.execute(
            "SELECT * FROM sentiment WHERE date = ?", (target_date,)
        ).fetchone()

        if not today:
            log_debug(f"无 {target_date} 情绪数据，请先同步")
            return {}

        # 获取最近5日情绪数据
        recent = cursor.execute(
            """
            SELECT date, bull_bear_index, fear_greed_index FROM sentiment
            ORDER BY date DESC LIMIT 5
            """
        ).fetchall()

        # 判断市场状态
        bb = today["bull_bear_index"]
        fg = today["fear_greed_index"]

        if bb > 30:
            market_status = "强势"
        elif bb > 0:
            market_status = "偏强"
        elif bb > -30:
            market_status = "偏弱"
        else:
            market_status = "弱势"

        if fg > 70:
            emotion = "贪婪"
        elif fg > 50:
            emotion = "乐观"
        elif fg > 30:
            emotion = "中性"
        elif fg > 20:
            emotion = "担忧"
        else:
            emotion = "恐惧"

        return {
            "date": target_date,
            "bull_bear_index": bb,
            "fear_greed_index": fg,
            "market_status": market_status,
            "emotion": emotion,
            "turnover_rate": today["turnover_rate"],
            "limit_up_ratio": today["limit_up_ratio"],
            "limit_down_ratio": today["limit_down_ratio"],
            "recent_trend": [dict(r) for r in recent],
        }

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="市场情绪分析")
    parser.add_argument("--sync", action="store_true", help="同步数据")
    parser.add_argument("--analyze", action="store_true", help="分析数据")
    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")

    args = parser.parse_args()

    if args.sync:
        sync_sentiment(date=args.date)
    elif args.analyze:
        result = analyze_sentiment(date=args.date)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"市场情绪分析 ({result.get('date', 'N/A')})")
            print(f"市场状态: {result.get('market_status', 'N/A')}")
            print(f"多空指数: {result.get('bull_bear_index', 'N/A')}")
            print(f"恐惧贪婪: {result.get('fear_greed_index', 'N/A')} ({result.get('emotion', 'N/A')})")
    else:
        # 默认执行同步和分析
        sync_sentiment(date=args.date)
        result = analyze_sentiment(date=args.date)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
