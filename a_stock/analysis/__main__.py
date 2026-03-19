"""分析模块命令行入口"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="数据分析")
    subparsers = parser.add_subparsers(dest="command", help="分析命令")

    # capital_flow
    subparsers.add_parser("capital-flow", help="资金流向分析")

    # sentiment
    subparsers.add_parser("sentiment", help="市场情绪分析")

    # sector
    subparsers.add_parser("sector", help="板块轮动分析")

    # overview
    subparsers.add_parser("overview", help="市场概览")

    # hot
    subparsers.add_parser("hot", help="热门股票")

    # daily_review
    review_parser = subparsers.add_parser("daily-review", help="每日复盘")
    review_parser.add_argument("--sync", action="store_true", help="先同步数据")
    review_parser.add_argument("--notify", action="store_true", help="发送通知")

    # 通用参数
    for sub in [subparsers._actions[-1] for _ in range(6)]:
        pass  # 占位

    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")

    args = parser.parse_args()

    if args.command == "capital-flow":
        from a_stock.analysis import sync_capital_flow, analyze_capital_flow
        sync_capital_flow()
        result = analyze_capital_flow(date=args.date)
        print_result(result, args.output)
    elif args.command == "sentiment":
        from a_stock.sync import sync_sentiment
        from a_stock.analysis import analyze_sentiment
        sync_sentiment(date=args.date)
        result = analyze_sentiment(date=args.date)
        print_result(result, args.output)
    elif args.command == "sector":
        from a_stock.sync import sync_sector_ranking
        from a_stock.analysis import analyze_sector
        sync_sector_ranking(date=args.date)
        result = analyze_sector(date=args.date)
        print_result(result, args.output)
    elif args.command == "overview":
        from a_stock.sync import sync_market_stats
        from a_stock.analysis import get_market_overview
        sync_market_stats(date=args.date)
        result = get_market_overview(date=args.date)
        print_result(result, args.output)
    elif args.command == "hot":
        from a_stock.analysis import analyze_hot_stocks
        result = analyze_hot_stocks()
        print_result(result, args.output)
    elif args.command == "daily-review":
        from a_stock.analysis import generate_daily_review
        from a_stock.notify import send_daily_report
        result = generate_daily_review(date=args.date, sync=args.sync)
        if args.output == "json":
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            from a_stock.analysis.daily_review import format_text_report
            print(format_text_report(result))
        if args.notify:
            send_daily_report(result)
    else:
        parser.print_help()


def print_result(result: dict, output: str):
    """打印结果"""
    import json
    if output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
