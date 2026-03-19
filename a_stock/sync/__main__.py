"""同步模块命令行入口"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="数据同步")
    subparsers = parser.add_subparsers(dest="command", help="同步命令")

    # stock_info
    subparsers.add_parser("stock-info", help="同步股票基础信息")

    # stock_daily
    subparsers.add_parser("stock-daily", help="同步个股日K数据")

    # limit_up
    subparsers.add_parser("limit-up", help="同步涨停数据")

    # stock_hot_ranking
    subparsers.add_parser("hot-ranking", help="同步热门股票榜单")

    # backfill
    backfill_parser = subparsers.add_parser("backfill", help="回填历史数据")
    backfill_parser.add_argument("--year", type=int, help="指定年份")
    backfill_parser.add_argument("--all", action="store_true", help="回填所有历史数据")

    args = parser.parse_args()

    if args.command == "stock-info":
        from a_stock.sync import sync_stock_info
        sync_stock_info()
    elif args.command == "stock-daily":
        from a_stock.sync import sync_stock_daily
        sync_stock_daily()
    elif args.command == "limit-up":
        from a_stock.sync import sync_limit_up
        sync_limit_up()
    elif args.command == "hot-ranking":
        from a_stock.sync import sync_stock_hot_ranking
        sync_stock_hot_ranking()
    elif args.command == "backfill":
        from a_stock.sync import backfill_year, backfill_all
        if args.all:
            backfill_all()
        elif args.year:
            backfill_year(args.year)
        else:
            parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
