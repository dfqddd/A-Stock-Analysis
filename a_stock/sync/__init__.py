"""数据同步模块"""

# 使用延迟导入避免循环导入问题
__all__ = [
    "sync_stock_daily",
    "sync_stock_info",
    "sync_limit_up",
    "sync_stock_events",
    "sync_stock_news",
    "sync_stock_hot_ranking",
    "sync_sentiment",
    "sync_market_stats",
    "sync_sector_ranking",
    "backfill_year",
    "backfill_all",
]


def __getattr__(name):
    """延迟导入模块成员"""
    if name == "sync_stock_daily":
        from .stock_daily import sync_stock_daily as func
        return func
    elif name == "sync_stock_info":
        from .stock_info import sync_stock_info as func
        return func
    elif name == "sync_limit_up":
        from .limit_up import sync_limit_up as func
        return func
    elif name == "sync_stock_events":
        from .stock_events import sync_stock_events as func
        return func
    elif name == "sync_stock_news":
        from .stock_news import sync_stock_news as func
        return func
    elif name == "sync_stock_hot_ranking":
        from .stock_hot_ranking import sync_stock_hot_ranking as func
        return func
    elif name == "sync_sentiment":
        from .sentiment_sync import sync_sentiment as func
        return func
    elif name == "sync_market_stats":
        from .market_stats_sync import sync_market_stats as func
        return func
    elif name == "sync_sector_ranking":
        from .sector_ranking_sync import sync_sector_ranking as func
        return func
    elif name == "backfill_year":
        from .backfill import backfill_year as func
        return func
    elif name == "backfill_all":
        from .backfill import backfill_all as func
        return func
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")