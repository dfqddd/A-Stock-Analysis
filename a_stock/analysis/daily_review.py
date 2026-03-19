"""
每日复盘分析脚本
整合市场概览、板块轮动、资金流向、热门股票等数据，生成每日复盘报告
"""

import argparse
import json
from datetime import datetime

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.analysis.market_overview import get_market_overview
from a_stock.analysis.market_sentiment import analyze_sentiment
from a_stock.analysis.sector_analysis import analyze_sector
from a_stock.sync import sync_sentiment, sync_market_stats, sync_sector_ranking
from a_stock.analysis.capital_flow import analyze_capital_flow, sync_capital_flow
from a_stock.analysis.hot_stocks import analyze_hot_stocks


def generate_daily_review(date: str = None, sync: bool = False) -> dict:
    """
    生成每日复盘报告

    Args:
        date: 指定日期（可选）
        sync: 是否先同步数据

    Returns:
        复盘报告数据
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    if sync:
        log_info(f"同步 {target_date} 数据...")
        sync_market_stats(date=target_date)
        sync_sentiment(date=target_date)
        sync_sector_ranking(date=target_date)
        sync_capital_flow()

    # 获取各模块数据
    market_overview = get_market_overview(date=target_date)
    sentiment = analyze_sentiment(date=target_date)
    sector = analyze_sector(date=target_date, top_n=5)
    capital_flow = analyze_capital_flow(date=target_date)
    hot_stocks = analyze_hot_stocks(top_n=10)

    # 生成报告摘要
    summary = generate_summary(market_overview, sentiment, sector, capital_flow)

    return {
        "date": target_date,
        "summary": summary,
        "market_overview": market_overview,
        "sentiment": sentiment,
        "sector": sector,
        "capital_flow": capital_flow,
        "hot_stocks": hot_stocks,
    }


def generate_summary(market: dict, sentiment: dict, sector: dict, capital: dict) -> str:
    """
    生成复盘摘要

    Args:
        market: 市场概览数据
        sentiment: 情绪数据
        sector: 板块数据
        capital: 资金流向数据

    Returns:
        复盘摘要文本
    """
    parts = []

    # 市场表现
    if market:
        mb = market.get("market_bread", {})
        up_ratio = mb.get("up_ratio", 0)
        lm = market.get("limit_move", {})
        parts.append(f"今日市场上涨{up_ratio:.1f}%，涨停{lm.get('limit_up', 0)}只，跌停{lm.get('limit_down', 0)}只。")

    # 情绪分析
    if sentiment:
        parts.append(f"市场{sentiment.get('market_status', '未知')}，情绪{sentiment.get('emotion', '未知')}。")

    # 资金流向
    if capital and "north" in capital:
        north = capital["north"]
        direction = "流入" if north.get("net_flow", 0) > 0 else "流出"
        parts.append(f"北向资金净{direction}{abs(north.get('net_flow', 0)):.2f}亿。")

    # 板块轮动
    if sector and sector.get("industry_top"):
        top_industries = [s["sector"] for s in sector["industry_top"][:3]]
        parts.append(f"领涨板块：{', '.join(top_industries)}。")

    return " ".join(parts)


def format_text_report(report: dict) -> str:
    """
    格式化文本报告

    Args:
        report: 复盘报告数据

    Returns:
        文本格式报告
    """
    lines = []

    lines.append(f"{'=' * 50}")
    lines.append(f"每日复盘报告 - {report['date']}")
    lines.append(f"{'=' * 50}")

    # 摘要
    lines.append(f"\n【摘要】")
    lines.append(report.get("summary", "无数据"))

    # 市场概览
    market = report.get("market_overview", {})
    if market:
        lines.append(f"\n【市场概览】")
        mb = market.get("market_bread", {})
        lines.append(f"上涨: {mb.get('up_count', 0)} ({mb.get('up_ratio', 0):.1f}%)")
        lines.append(f"下跌: {mb.get('down_count', 0)} ({mb.get('down_ratio', 0):.1f}%)")
        lm = market.get("limit_move", {})
        lines.append(f"涨停: {lm.get('limit_up', 0)}, 跌停: {lm.get('limit_down', 0)}")

    # 情绪分析
    sentiment = report.get("sentiment", {})
    if sentiment:
        lines.append(f"\n【情绪分析】")
        lines.append(f"多空指数: {sentiment.get('bull_bear_index', 'N/A')}")
        lines.append(f"恐惧贪婪: {sentiment.get('fear_greed_index', 'N/A')} ({sentiment.get('emotion', 'N/A')})")

    # 资金流向
    capital = report.get("capital_flow", {})
    if capital and "north" in capital:
        lines.append(f"\n【资金流向】")
        north = capital["north"]
        direction = "流入" if north.get("net_flow", 0) > 0 else "流出"
        lines.append(f"北向资金: 净{direction} {abs(north.get('net_flow', 0)):.2f}亿")

    # 板块轮动
    sector = report.get("sector", {})
    if sector and sector.get("industry_top"):
        lines.append(f"\n【板块轮动】")
        lines.append("行业涨幅榜:")
        for s in sector["industry_top"][:5]:
            lines.append(f"  {s['sector']}: +{s['change_pct']:.2f}%")

    # 热门股票
    hot = report.get("hot_stocks", {})
    if hot and hot.get("top_gainers"):
        lines.append(f"\n【热门股票】")
        lines.append("涨幅榜:")
        for s in hot["top_gainers"][:5]:
            lines.append(f"  {s['code']} {s['name']}: +{s['change_pct']:.2f}%")

    lines.append(f"\n{'=' * 50}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="每日复盘分析")
    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--sync", action="store_true", help="先同步数据")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")

    args = parser.parse_args()

    report = generate_daily_review(date=args.date, sync=args.sync)

    if args.output == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text_report(report))


if __name__ == "__main__":
    main()
