"""
钉钉通知模块
发送市场预警、每日复盘等消息到钉钉群
"""

import json
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

from a_stock.db.cache import log_debug, log_info, log_error


def get_dingtalk_webhook() -> Optional[str]:
    """
    获取钉钉 Webhook URL
    
    优先从环境变量获取，其次从配置文件获取
    
    Returns:
        Webhook URL 或 None
    """
    # 从环境变量获取
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    if webhook:
        return webhook
    
    # 从配置文件获取
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                return config.get("dingtalk", {}).get("webhook")
        except Exception as e:
            log_error(f"读取配置文件失败: {e}")
    
    return None


def send_dingtalk_message(
    content: str,
    webhook: str = None,
    at_mobiles: List[str] = None,
    at_all: bool = False,
) -> bool:
    """
    发送钉钉消息
    
    Args:
        content: 消息内容
        webhook: Webhook URL（可选，默认从配置获取）
        at_mobiles: @ 的手机号列表
        at_all: 是否 @ 所有人
        
    Returns:
        是否发送成功
    """
    webhook_url = webhook or get_dingtalk_webhook()
    
    if not webhook_url:
        log_error("未配置钉钉 Webhook")
        return False
    
    # 构建消息体
    message = {
        "msgtype": "text",
        "text": {
            "content": content
        },
        "at": {
            "atMobiles": at_mobiles or [],
            "isAtAll": at_all
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(message),
            timeout=10
        )
        
        result = response.json()
        if result.get("errcode") == 0:
            log_debug("钉钉消息发送成功")
            return True
        else:
            log_error(f"钉钉消息发送失败: {result.get('errmsg', '未知错误')}")
            return False
            
    except Exception as e:
        log_error(f"发送钉钉消息异常: {e}")
        return False


def send_markdown_message(
    title: str,
    content: str,
    webhook: str = None,
    at_mobiles: List[str] = None,
    at_all: bool = False,
) -> bool:
    """
    发送 Markdown 格式的钉钉消息
    
    Args:
        title: 消息标题
        content: Markdown 格式的消息内容
        webhook: Webhook URL（可选）
        at_mobiles: @ 的手机号列表
        at_all: 是否 @ 所有人
        
    Returns:
        是否发送成功
    """
    webhook_url = webhook or get_dingtalk_webhook()
    
    if not webhook_url:
        log_error("未配置钉钉 Webhook")
        return False
    
    # 构建消息体
    message = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content
        },
        "at": {
            "atMobiles": at_mobiles or [],
            "isAtAll": at_all
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(message),
            timeout=10
        )
        
        result = response.json()
        if result.get("errcode") == 0:
            log_debug("钉钉 Markdown 消息发送成功")
            return True
        else:
            log_error(f"钉钉消息发送失败: {result.get('errmsg', '未知错误')}")
            return False
            
    except Exception as e:
        log_error(f"发送钉钉消息异常: {e}")
        return False


def send_market_alert(
    alert_type: str,
    title: str,
    content: Dict[str, Any],
    webhook: str = None,
) -> bool:
    """
    发送市场预警消息
    
    Args:
        alert_type: 预警类型（如 "limit_up", "capital_flow", "sentiment"）
        title: 预警标题
        content: 预警内容
        webhook: Webhook URL（可选）
        
    Returns:
        是否发送成功
    """
    # 构建 Markdown 内容
    md_content = f"## {title}\n\n"
    md_content += f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_content += f"**类型**: {alert_type}\n\n"
    
    # 添加具体内容
    for key, value in content.items():
        md_content += f"- **{key}**: {value}\n"
    
    return send_markdown_message(
        title=f"[{alert_type}] {title}",
        content=md_content,
        webhook=webhook
    )


def format_market_card(market: Dict) -> str:
    """格式化市场概览卡片"""
    mb = market.get("market_bread", {})
    lm = market.get("limit_move", {})
    amount = market.get("total_amount", 0)
    
    up_ratio = mb.get('up_ratio', 0)
    emoji = "🔴" if up_ratio > 60 else "🟢" if up_ratio < 40 else "⚪"
    
    return f"""{emoji} **涨跌分布**: 涨{mb.get('up_count', 0)}/跌{mb.get('down_count', 0)}/平{mb.get('flat_count', 0)}
📈 **涨停跌停**: 涨停{lm.get('limit_up', 0)}家 / 跌停{lm.get('limit_down', 0)}家
💰 **两市成交**: {amount/10000:.2f}万亿
"""

def format_sector_list(sectors: List[Dict], title: str = "领涨板块") -> str:
    """格式化板块列表"""
    if not sectors:
        return ""
    
    lines = [f"### {title}"]
    for i, s in enumerate(sectors[:5], 1):
        emoji = "🔥" if i <= 3 else "📊"
        lines.append(f"{emoji} **{s.get('name', s.get('sector', 'N/A'))}**: +{s.get('change_pct', 0):.2f}%")
    return "\n".join(lines) + "\n\n"

def format_stock_list(stocks: List[Dict], title: str = "热门个股") -> str:
    """格式化个股列表"""
    if not stocks:
        return ""
    
    lines = [f"### {title}"]
    for i, s in enumerate(stocks[:5], 1):
        change = s.get('change_pct', 0)
        emoji = "🔴" if change > 5 else "🟡" if change > 0 else "🟢"
        lines.append(f"{emoji} **{s.get('name', s.get('code', 'N/A'))}**: {change:+.2f}%")
    return "\n".join(lines) + "\n\n"

def send_market_report(
    report_type: str,
    report: Dict[str, Any],
    webhook: str = None
) -> bool:
    """
    发送市场报告（支持多种时段类型）
    
    Args:
        report_type: 报告类型 (premarket/midday/postmarket/evening)
        report: 报告数据
        webhook: Webhook URL（可选）
        
    Returns:
        是否发送成功
    """
    date_str = report.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # 根据类型设置标题和emoji
    type_config = {
        "premarket": {"emoji": "🌅", "title": "开盘预判", "time": "08:45"},
        "midday": {"emoji": "⏰", "title": "盘中速递", "time": "盘中"},
        "postmarket": {"emoji": "📊", "title": "收盘复盘", "time": "15:35"},
        "evening": {"emoji": "🌙", "title": "晚间深度", "time": "18:30"},
    }
    
    config = type_config.get(report_type, type_config["postmarket"])
    title = f"{config['emoji']} {config['title']} - {date_str}"
    
    # 构建 Markdown 内容
    md_content = f"## {title}\n\n"
    
    # 一句话摘要
    if report.get("summary"):
        md_content += f"> 💡 **{report['summary']}**\n\n"
    
    # 市场概览
    market = report.get("market_overview", {})
    if market:
        md_content += format_market_card(market)
        md_content += "\n"
    
    # 情绪分析（仅盘后和晚间显示）
    if report_type in ["postmarket", "evening"]:
        sentiment = report.get("sentiment", {})
        if sentiment:
            md_content += "### 市场情绪\n"
            fear_greed = sentiment.get('fear_greed_index', 50)
            emotion_emoji = "😱" if fear_greed < 30 else "😰" if fear_greed < 45 else "😐" if fear_greed < 55 else "😊" if fear_greed < 70 else "🤩"
            md_content += f"{emotion_emoji} **恐惧贪婪指数**: {fear_greed}/100 ({sentiment.get('emotion', '中性')})\n"
            md_content += f"📈 **连板高度**: {sentiment.get('max_height', 0)}板\n"
            md_content += f"🔒 **封板率**: {sentiment.get('seal_rate', 0):.1f}%\n\n"
    
    # 板块轮动
    sector = report.get("sector", {})
    if sector:
        if sector.get("industry_top"):
            md_content += format_sector_list(sector["industry_top"], "🔥 领涨板块")
        if sector.get("concept_top"):
            md_content += format_sector_list(sector["concept_top"], "💡 热门概念")
    
    # 龙虎榜（仅晚间显示）
    if report_type == "evening" and report.get("dragon_tiger"):
        dt = report["dragon_tiger"]
        md_content += "### 🐉 龙虎榜亮点\n"
        md_content += f"📌 今日上榜: {dt.get('total_count', 0)}只\n"
        if dt.get("top_buy"):
            md_content += "💰 **机构净买入TOP3**:\n"
            for item in dt["top_buy"][:3]:
                md_content += f"  - {item.get('name', 'N/A')}: {item.get('net_buy', 0):.0f}万\n"
        md_content += "\n"
    
    # 操作建议
    if report.get("suggestion"):
        md_content += f"### 🎯 操作建议\n{report['suggestion']}\n\n"
    
    # 发送时间
    md_content += f"---\n⏰ 发送时间: {datetime.now().strftime('%H:%M:%S')}"
    
    return send_markdown_message(title=title, content=md_content, webhook=webhook)

def send_daily_report(report: Dict[str, Any], webhook: str = None) -> bool:
    """
    发送每日复盘报告（兼容旧接口，默认盘后格式）
    
    Args:
        report: 复盘报告数据
        webhook: Webhook URL（可选）
        
    Returns:
        是否发送成功
    """
    return send_market_report("postmarket", report, webhook)


def send_premarket_report(webhook: str = None) -> bool:
    """发送开盘预判报告（使用详细数据格式）"""
    from a_stock.analysis.market_detail import get_market_summary, format_premarket_message
    
    # 获取昨日详细市场数据
    data = get_market_summary()
    
    # 格式化消息
    message = format_premarket_message(data)
    
    # 发送Markdown消息
    return send_markdown_message("盘前分析", message, webhook)

def send_postmarket_report(webhook: str = None) -> bool:
    """发送收盘复盘报告（使用盘前格式，取当天数据）"""
    from a_stock.analysis.market_detail import get_market_summary, format_premarket_message
    from datetime import datetime, timedelta
    
    # 获取当天日期
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 使用当天数据生成市场汇总（通过传入当天日期，让函数内部计算昨天为今天）
    # 这里需要特殊处理：get_market_summary 默认取昨天数据，我们需要让它取今天数据
    # 传入明天日期，这样计算出的"昨天"就是今天
    # 盘后报告不允许回退到历史日期，必须显示当天数据
    tomorrow = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    data = get_market_summary(tomorrow, allow_fallback=False)
    
    if not data or not data.get("date"):
        log_error("获取当天市场数据失败")
        return False
    
    # 修改日期显示为当天（让 format_premarket_message 认为 yesterday 是 today-1）
    # 这样函数内部计算的 today 就会是正确的当天日期
    actual_today = today
    fake_yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    data["date"] = fake_yesterday
    
    # 使用盘前格式生成消息，但标题改为收盘复盘
    message = format_premarket_message(data)
    # 替换标题
    message = message.replace("盘前分析", "收盘复盘")
    message = message.replace(f"基于昨日（{fake_yesterday}）数据", f"今日（{actual_today}）数据")
    
    # 发送Markdown消息
    return send_markdown_message(f"📊 收盘复盘 - {actual_today}", message, webhook)

def send_evening_report(webhook: str = None) -> bool:
    """发送晚间深度报告（含龙虎榜）"""
    from a_stock.analysis.daily_review import generate_daily_review
    from a_stock.db.repository import DragonTigerRepository
    from datetime import datetime
    
    # 生成复盘报告
    report = generate_daily_review()
    
    # 获取今日龙虎榜数据
    today = datetime.now().strftime("%Y-%m-%d")
    repository = DragonTigerRepository()
    dragon_tiger_data = repository.find_by_date(today)
    
    # 整理龙虎榜数据
    if dragon_tiger_data:
        # 按净买入金额排序，取前3名
        top_buy = sorted(
            [d for d in dragon_tiger_data if d.get("net_buy_value", 0) > 0],
            key=lambda x: x.get("net_buy_value", 0),
            reverse=True
        )[:3]
        
        # 按净卖出金额排序，取前3名
        top_sell = sorted(
            [d for d in dragon_tiger_data if d.get("net_buy_value", 0) < 0],
            key=lambda x: abs(x.get("net_buy_value", 0)),
            reverse=True
        )[:3]
        
        report["dragon_tiger"] = {
            "total_count": len(dragon_tiger_data),
            "top_buy": [
                {
                    "name": d.get("name", d.get("code", "N/A")),
                    "net_buy": d.get("net_buy_value", 0) / 10000  # 转换为万元
                }
                for d in top_buy
            ],
            "top_sell": [
                {
                    "name": d.get("name", d.get("code", "N/A")),
                    "net_sell": abs(d.get("net_buy_value", 0)) / 10000  # 转换为万元
                }
                for d in top_sell
            ]
        }
    else:
        report["dragon_tiger"] = {
            "total_count": 0,
            "top_buy": [],
            "top_sell": []
        }
    
    return send_market_report("evening", report, webhook)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="钉钉通知")
    parser.add_argument("command", nargs="?", choices=["premarket", "postmarket", "evening", "test"], 
                       help="发送指定类型的报告 (premarket:开盘预判, postmarket:收盘复盘, evening:晚间深度)")
    parser.add_argument("--message", help="发送文本消息")
    parser.add_argument("--markdown", help="发送 Markdown 消息")
    parser.add_argument("--title", help="Markdown 消息标题")
    parser.add_argument("--test", action="store_true", help="发送测试消息")
    
    args = parser.parse_args()
    
    if args.command == "premarket":
        send_premarket_report()
    elif args.command == "postmarket":
        send_postmarket_report()
    elif args.command == "evening":
        send_evening_report()
    elif args.test or args.command == "test":
        send_dingtalk_message("【分析】🧪 这是一条测试消息，如果您收到说明钉钉配置正常！")
    elif args.message:
        send_dingtalk_message(args.message)
    elif args.markdown:
        send_markdown_message(args.title or "通知", args.markdown)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
