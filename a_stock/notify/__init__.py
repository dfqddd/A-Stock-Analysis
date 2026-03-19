"""通知模块"""

__all__ = [
    "send_dingtalk_message",
    "send_markdown_message",
    "send_market_alert",
    "send_daily_report",
    "get_dingtalk_webhook",
    "main",
]


def __getattr__(name):
    """延迟导入模块成员"""
    if name == "send_dingtalk_message":
        from .dingtalk import send_dingtalk_message as func
        return func
    elif name == "send_markdown_message":
        from .dingtalk import send_markdown_message as func
        return func
    elif name == "send_market_alert":
        from .dingtalk import send_market_alert as func
        return func
    elif name == "send_daily_report":
        from .dingtalk import send_daily_report as func
        return func
    elif name == "get_dingtalk_webhook":
        from .dingtalk import get_dingtalk_webhook as func
        return func
    elif name == "main":
        from .dingtalk import main as func
        return func
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")