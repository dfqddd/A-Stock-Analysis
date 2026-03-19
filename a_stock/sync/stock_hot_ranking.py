"""
热门股票榜单数据同步

数据来源:
  - 同花顺热门股
  - 淘股吧热门股
  - 东财吧热门股
  - 雪球热门股
"""

import argparse
from datetime import datetime
from typing import Dict, List

from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.repository import StockHotRankingRepository
from a_stock.db.datasource import DataSource, get_manager


def save_hot_ranking(records: List[Dict]):
    """将热门股票数据写入数据库"""
    if not records:
        return
    
    repository = StockHotRankingRepository()
    repository.save_batch(records)
    log_debug(f"已写入 {len(records)} 条热门股票数据")


def sync_stock_hot_ranking(date: str = None):
    """
    同步热门股票榜单数据
    
    Args:
        date: 指定日期（可选）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步热门股票榜单数据: {target_date}")
    
    try:
        # 初始化数据源管理器
        manager = get_manager()
        repository = StockHotRankingRepository()
        
        # 定义数据获取函数
        def fetch_hot_ranking():
            import akshare as ak
            return ak.stock_hot_rank_em()
        
        # 注册数据源（单一数据源，不需要降级）
        source = DataSource(
            name="akshare_em",
            fetch_func=fetch_hot_ranking,
            priority=0,
            enabled=True
        )
        manager.register("stock_hot_ranking", source)
        
        # 获取数据
        df = manager.fetch("stock_hot_ranking")
        
        if df is None or df.empty:
            log_debug(f"{target_date} 无热门股票数据")
            return
        
        log_debug(f"获取到 {len(df)} 条热门股票记录")
        
        # 处理数据
        records = []
        for idx, row in df.iterrows():
            record = {
                "date": target_date,
                "code": str(row.get("代码", "")),
                "name": str(row.get("股票名称", "")),
                "total_rank": idx + 1,  # 排名
                "total_score": row.get("个股热度", 0),  # 热度值
                "ths_rank": None,  # 同花顺暂无数据
                "ths_score": None,
                "tgb_rank": None,  # 淘股吧暂无数据
                "tgb_score": None,
                "dcb_rank": idx + 1,  # 东财吧排名
                "dcb_score": row.get("个股热度", 0),
                "xq_rank": None,  # 雪球暂无数据
                "xq_score": None,
                "source_count": 1,  # 目前只有东财数据
            }
            records.append(record)
        
        # 写入数据库
        if records:
            repository.save_batch(records)
            log_info(f"已写入 {len(records)} 条热门股票数据")
    
    except Exception as e:
        log_error(f"同步热门股票榜单数据失败: {e}")
        import traceback
        traceback.print_exc()
    
    log_info(f"热门股票榜单数据同步完成")


def main():
    parser = argparse.ArgumentParser(description="同步热门股票榜单数据")
    parser.add_argument("--date", help="指定日期")
    
    args = parser.parse_args()
    sync_stock_hot_ranking(date=args.date)


if __name__ == "__main__":
    main()
