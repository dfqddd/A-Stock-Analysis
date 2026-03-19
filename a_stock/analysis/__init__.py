"""数据分析模块"""

__all__ = [
    "sync_capital_flow",
    "analyze_capital_flow",
    "analyze_sentiment",
    "analyze_sector",
    "get_market_overview",
    "analyze_hot_stocks",
    "get_top_gainers",
    "get_top_losers",
    "generate_daily_review",
]


def __getattr__(name):
    """延迟导入模块成员"""
    if name == "sync_capital_flow":
        from .capital_flow import sync_capital_flow as func
        return func
    elif name == "analyze_capital_flow":
        from .capital_flow import analyze_capital_flow as func
        return func
    elif name == "analyze_sentiment":
        from .market_sentiment import analyze_sentiment as func
        return func
    elif name == "analyze_sector":
        from .sector_analysis import analyze_sector as func
        return func
    elif name == "get_market_overview":
        from .market_overview import get_market_overview as func
        return func
    elif name == "analyze_hot_stocks":
        from .hot_stocks import analyze_hot_stocks as func
        return func
    elif name == "get_top_gainers":
        from .hot_stocks import get_top_gainers as func
        return func
    elif name == "get_top_losers":
        from .hot_stocks import get_top_losers as func
        return func
    elif name == "generate_daily_review":
        from .daily_review import generate_daily_review as func
        return func
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")