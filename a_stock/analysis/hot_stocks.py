"""
热门股票分析脚本
获取涨幅榜、跌幅榜、成交额榜、换手率榜等热门股票数据
"""

import argparse
import json
from datetime import datetime

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error


def get_top_gainers(top_n: int = 50) -> list:
    """
    获取涨幅榜

    Args:
        top_n: 返回数量

    Returns:
        涨幅榜列表
    """
    try:
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            return []

        # 按涨跌幅排序
        df = df.sort_values("涨跌幅", ascending=False).head(top_n)

        result = []
        for _, row in df.iterrows():
            result.append({
                "code": str(row["代码"]),
                "name": str(row["名称"]),
                "change_pct": round(row["涨跌幅"], 2),
                "price": round(row["最新价"], 2),
                "amount": round(row["成交额"], 2) if "成交额" in row else 0,
                "turnover_rate": round(row["换手率"], 2) if "换手率" in row else 0,
            })

        return result

    except Exception as e:
        log_error(f"获取涨幅榜失败: {e}")
        return []


def get_top_losers(top_n: int = 50) -> list:
    """
    获取跌幅榜

    Args:
        top_n: 返回数量

    Returns:
        跌幅榜列表
    """
    try:
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            return []

        # 按涨跌幅排序（升序）
        df = df.sort_values("涨跌幅", ascending=True).head(top_n)

        result = []
        for _, row in df.iterrows():
            result.append({
                "code": str(row["代码"]),
                "name": str(row["名称"]),
                "change_pct": round(row["涨跌幅"], 2),
                "price": round(row["最新价"], 2),
                "amount": round(row["成交额"], 2) if "成交额" in row else 0,
                "turnover_rate": round(row["换手率"], 2) if "换���率" in row else 0,
            })

        return result

    except Exception as e:
        log_error(f"获取跌幅榜失败: {e}")
        return []


def get_top_volume(top_n: int = 50) -> list:
    """
    获取成交额榜

    Args:
        top_n: 返回数量

    Returns:
        成交额榜列表
    """
    try:
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            return []

        # 按成交额排序
        df = df.sort_values("成交额", ascending=False).head(top_n)

        result = []
        for _, row in df.iterrows():
            result.append({
                "code": str(row["代码"]),
                "name": str(row["名称"]),
                "change_pct": round(row["涨跌幅"], 2),
                "price": round(row["最新价"], 2),
                "amount": round(row["成交额"], 2) if "成交额" in row else 0,
                "turnover_rate": round(row["换手率"], 2) if "换手率" in row else 0,
            })

        return result

    except Exception as e:
        log_error(f"获取成交额榜失败: {e}")
        return []


def get_top_turnover(top_n: int = 50) -> list:
    """
    获取换手率榜

    Args:
        top_n: 返回数量

    Returns:
        换手率榜列表
    """
    try:
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            return []

        # 按换手率排序
        df = df.sort_values("换手率", ascending=False).head(top_n)

        result = []
        for _, row in df.iterrows():
            result.append({
                "code": str(row["代码"]),
                "name": str(row["名称"]),
                "change_pct": round(row["涨跌幅"], 2),
                "price": round(row["最新价"], 2),
                "amount": round(row["成交额"], 2) if "成交额" in row else 0,
                "turnover_rate": round(row["换手率"], 2) if "换手率" in row else 0,
            })

        return result

    except Exception as e:
        log_error(f"获取换手率榜失败: {e}")
        return []


def analyze_hot_stocks(top_n: int = 20) -> dict:
    """
    分析热门股票

    Args:
        top_n: 返回数量

    Returns:
        热门股票分析结果
    """
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "top_gainers": get_top_gainers(top_n),
        "top_losers": get_top_losers(top_n),
        "top_volume": get_top_volume(top_n),
        "top_turnover": get_top_turnover(top_n),
    }


def main():
    parser = argparse.ArgumentParser(description="热门股票分析")
    parser.add_argument("--top", type=int, default=20, help="返回数量")
    parser.add_argument("--type", choices=["gainers", "losers", "volume", "turnover", "all"],
                        default="all", help="榜单类型")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")

    args = parser.parse_args()

    if args.type == "gainers":
        result = get_top_gainers(args.top)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("涨幅榜:")
            for s in result:
                print(f"  {s['code']} {s['name']}: +{s['change_pct']:.2f}%")
    elif args.type == "losers":
        result = get_top_losers(args.top)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("跌幅榜:")
            for s in result:
                print(f"  {s['code']} {s['name']}: {s['change_pct']:.2f}%")
    elif args.type == "volume":
        result = get_top_volume(args.top)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("成交额榜:")
            for s in result:
                print(f"  {s['code']} {s['name']}: {s['amount']/100000000:.2f}亿")
    elif args.type == "turnover":
        result = get_top_turnover(args.top)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("换手率榜:")
            for s in result:
                print(f"  {s['code']} {s['name']}: {s['turnover_rate']:.2f}%")
    else:
        result = analyze_hot_stocks(args.top)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"热门股票分析 ({result['date']} {result['time']})")
            print("\n涨幅榜:")
            for s in result["top_gainers"][:10]:
                print(f"  {s['code']} {s['name']}: +{s['change_pct']:.2f}%")
            print("\n跌幅榜:")
            for s in result["top_losers"][:10]:
                print(f"  {s['code']} {s['name']}: {s['change_pct']:.2f}%")


if __name__ == "__main__":
    main()
