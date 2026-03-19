"""
实时热点消息推送模块
抓取财联社/东方财富最新热点消息，推送到钉钉群
"""

from datetime import datetime
from typing import Dict, List, Set, Tuple

import akshare as ak

from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.notify.dingtalk import send_markdown_message

# 热点关键词列表
HOT_KEYWORDS = [
    "涨停", "跌停", "暴涨", "暴跌", "连板", "炸板", "封板",
    "停牌", "复牌", "重组", "收购", "合并", "借壳", "资产注入",
    "重大合同", "中标", "大单", "签约", "订单", "预增", "预亏",
    "业绩暴增", "业绩大增", "净利润", "政策", "央行", "证监会",
    "发改委", "银保监会", "新规", "突发", "紧急", "重磅",
    "风险", "警示", "调查", "股灾", "熔断", "系统性风险", "流动性危机"
]

# 财联社热点标签
CLS_HOT_TAGS = ["今日热点", "CCI快报"]

# 内存去重集合
_seen_titles: Set[str] = set()

def is_hot_news(news: Dict) -> bool:
    """
    判断是否为热点消息
    
    Args:
        news: 消息字典
        
    Returns:
        是否为热点消息
    """
    # 财联社标签判断
    if news.get("source") == "财联社":
        tag = news.get("tag", "")
        if tag in CLS_HOT_TAGS:
            return True
    
    # 标题关键词判断
    title = news.get("title", "")
    for keyword in HOT_KEYWORDS:
        if keyword in title:
            return True
    
    return False

def fetch_eastmoney_hot_news(limit: int = 50) -> List[Dict]:
    """
    从东方财富获取最新资讯
    
    Args:
        limit: 获取条数
        
    Returns:
        消息列表
    """
    try:
        log_info(f"开始从东方财富获取资讯，限制 {limit} 条")
        df = ak.stock_info_global_em()
        
        if df is None or df.empty:
            log_debug("东方财富资讯为空")
            return []
        
        # 解析数据
        records = []
        for _, row in df.head(limit).iterrows():
            try:
                # 解析发布时间
                pub_time_str = row.get("发布时间", "")
                if pub_time_str:
                    pub_time = datetime.strptime(pub_time_str, "%Y-%m-%d %H:%M:%S")
                else:
                    continue
                
                record = {
                    "title": row.get("标题", "").strip(),
                    "summary": row.get("摘要", "").strip(),
                    "url": row.get("链接", ""),
                    "pub_time": pub_time,
                    "source": "东方财富",
                }
                
                # 只保留标题不为空的数据
                if record["title"]:
                    records.append(record)
                    
            except Exception as e:
                log_debug(f"解析单条新闻失败: {e}")
                continue
        
        log_info(f"成功获取 {len(records)} 条东方财富资讯")
        return records
        
    except Exception as e:
        log_error(f"获取东方财富资讯失败: {e}")
        return []

def fetch_cls_hot_news(limit: int = 30) -> List[Dict]:
    """
    从财联社获取最新资讯（实时抓取）
    
    Args:
        limit: 获取条数
        
    Returns:
        消息列表
    """
    try:
        log_info(f"开始从财联社获取资讯，限制 {limit} 条")
        df = ak.stock_news_main_cx()
        
        if df is None or df.empty:
            log_debug("财联社资讯为空")
            return []
        
        # 解析数据（财联社没有时间字段，使用当前时间）
        now = datetime.now()
        records = []
        for _, row in df.head(limit).iterrows():
            try:
                record = {
                    "title": row.get("summary", "").strip(),
                    "summary": "",  # 财联社没有单独摘要，标题即内容
                    "url": row.get("url", ""),
                    "pub_time": now,  # 使用当前时间作为抓取时间
                    "source": "财联社",
                    "tag": row.get("tag", ""),  # 财联社特有的标签
                }
                
                # 只保留标题不为空的数据
                if record["title"]:
                    records.append(record)
                    
            except Exception as e:
                log_debug(f"解析单条财联社新闻失败: {e}")
                continue
        
        log_info(f"成功获取 {len(records)} 条财联社资讯")
        return records
        
    except Exception as e:
        log_error(f"获取财联社资讯失败: {e}")
        return []

def fetch_and_filter_hot_news(eastmoney_limit: int = 30, cls_limit: int = 20) -> List[Dict]:
    """
    从多个数据源获取并过滤热点消息（实时抓取，不依赖数据库）
    
    Args:
        eastmoney_limit: 东方财富获取条数
        cls_limit: 财联社获取条数
        
    Returns:
        过滤后的热点消息列表
    """
    all_news = []
    
    # 获取东方财富数据
    eastmoney_news = fetch_eastmoney_hot_news(limit=eastmoney_limit)
    all_news.extend(eastmoney_news)
    
    # 获取财联社数据
    cls_news = fetch_cls_hot_news(limit=cls_limit)
    all_news.extend(cls_news)
    
    # 过滤热点消息
    hot_news = [news for news in all_news if is_hot_news(news)]
    log_info(f"过滤出 {len(hot_news)} 条热点消息（总消息:{len(all_news)}）")
    
    # 去重（基于标题，内存中去重）
    unique_news = []
    for news in hot_news:
        title = news["title"]
        if title and title not in _seen_titles:
            _seen_titles.add(title)
            unique_news.append(news)
    
    log_info(f"去重后共 {len(unique_news)} 条热点资讯（东方财富:{len(eastmoney_news)}, 财联社:{len(cls_news)}）")
    return unique_news

def format_hot_news_message(news_list: List[Dict]) -> Tuple[str, str]:
    """
    格式化热点消息为 Markdown
    
    Args:
        news_list: 热点消息列表
        
    Returns:
        (标题, Markdown内容)
    """
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    
    title = f"🔥 股票分析 - 实时热点速递 ({time_str})"
    
    md_content = f"## 🔥 股票分析 - 实时热点速递 ({time_str})\n\n"
    
    # 按发布时间排序（最新的在前）
    sorted_news = sorted(news_list, key=lambda x: x.get("pub_time", datetime.min), reverse=True)
    
    # 最多显示10条
    for i, news in enumerate(sorted_news[:10], 1):
        pub_time = news.get("pub_time")
        time_display = pub_time.strftime("%H:%M") if pub_time else "--:--"
        
        # 选择表情
        emoji = "🔴" if i <= 3 else "🟡" if i <= 6 else "⚪"
        
        md_content += f"### {emoji} {news['title']}\n"
        md_content += f"⏰ {time_display} | 📰 {news.get('source', '未知来源')}\n"
        
        # 添加摘要（如果有且不太长）
        summary = news.get("summary", "")
        if summary and len(summary) > 10 and summary != news["title"]:
            # 截断过长的摘要
            if len(summary) > 100:
                summary = summary[:97] + "..."
            md_content += f"> {summary}\n"
        
        # 添加链接
        url = news.get("url", "")
        if url:
            md_content += f"🔗 [查看详情]({url})\n"
        
        md_content += "\n"
    
    # 添加页脚
    md_content += "---\n"
    md_content += f"💡 共 {len(news_list)} 条新消息 | 📊 实时更新\n"
    
    return title, md_content

def send_hot_news() -> bool:
    """
    发送热点消息
    
    Returns:
        是否发送成功
    """
    # 实时抓取并过滤热点消息（东方财富 + 财联社）
    news_list = fetch_and_filter_hot_news(eastmoney_limit=30, cls_limit=20)
    
    if not news_list:
        log_info("未获取到热点消息")
        return False
    
    log_info(f"准备发送 {len(news_list)} 条热点消息")
    
    # 格式化消息
    title, md_content = format_hot_news_message(news_list)
    
    # 发送钉钉消息
    success = send_markdown_message(title=title, content=md_content)
    
    if success:
        log_info(f"成功发送 {len(news_list)} 条热点消息")
    else:
        log_error("发送热点消息失败")
    
    return success

def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="实时热点消息推送")
    args = parser.parse_args()
    
    send_hot_news()

if __name__ == "__main__":
    main()
