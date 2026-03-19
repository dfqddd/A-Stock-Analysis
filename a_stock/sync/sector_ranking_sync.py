"""
板块排名数据同步模块
同步行业板块和概念板块的涨跌幅排名

数据源：
  - 东方财富板块数据（主数据源，优先级 0）
  - 同花顺板块数据（备选数据源，优先级 1）
  - 新浪财经板块数据（备选数据源，优先级 2）
"""

from datetime import datetime
from typing import Dict, List

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.datasource import DataSource, get_manager


def save_sector_ranking(records: List[Dict]):
    """将板块排名数据写入数据库（适配现有表结构）"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO sector_ranking
                (date, type, rank, name, change_pct, leading_stock, turnover_rate, up_count, down_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record.get("sector_type", "industry"),  # 使用 type 而不是 sector_type
                    record.get("rank", 0),
                    record.get("sector", ""),
                    record.get("change_pct", 0),
                    record.get("lead_stock", ""),
                    0,  # turnover_rate
                    0,  # up_count
                    0,  # down_count
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条板块排名数据")
    finally:
        conn.close()


def fetch_sector_ranking_from_eastmoney(target_date: str) -> List[Dict]:
    """
    从东方财富获取板块排名数据（主数据源）
    
    Args:
        target_date: 目标日期
        
    Returns:
        板块排名数据列表
    """
    records = []
    
    # 获取行业板块数据
    try:
        df_industry = ak.stock_board_industry_name_em()
        
        if df_industry is not None and not df_industry.empty:
            for i, (_, row) in enumerate(df_industry.iterrows()):
                records.append({
                    "date": target_date,
                    "sector_type": "industry",
                    "sector": row.get("板块名称", ""),
                    "change_pct": row.get("涨跌幅", 0),
                    "lead_stock": row.get("领涨股票", ""),
                    "lead_stock_change": row.get("领涨股票-涨跌幅", 0),
                    "amount": row.get("总市值", 0),
                    "rank": i + 1,
                })
            log_debug(f"从东财获取到 {len(df_industry)} 个行业板块")
    except Exception as e:
        log_debug(f"从东财获取行业板块数据失败: {e}")
        raise
    
    # 获取概念板块数据
    try:
        df_concept = ak.stock_board_concept_name_em()
        
        if df_concept is not None and not df_concept.empty:
            for i, (_, row) in enumerate(df_concept.iterrows()):
                records.append({
                    "date": target_date,
                    "sector_type": "concept",
                    "sector": row.get("板块名称", ""),
                    "change_pct": row.get("涨跌幅", 0),
                    "lead_stock": row.get("领涨股票", ""),
                    "lead_stock_change": row.get("领涨股票-涨跌幅", 0),
                    "amount": row.get("总市值", 0),
                    "rank": i + 1,
                })
            log_debug(f"从东财获取到 {len(df_concept)} 个概念板块")
    except Exception as e:
        log_debug(f"从东财获取概念板块数据失败: {e}")
        raise
    
    if not records:
        raise ValueError("东财数据源返回空数据")
    
    return records


def fetch_sector_ranking_from_sina(target_date: str) -> List[Dict]:
    """
    从新浪财经获取板块排名数据（备选数据源）
    
    Args:
        target_date: 目标日期
        
    Returns:
        板块排名数据列表
    """
    records = []
    
    # 获取新浪行业板块数据
    try:
        # 新浪行业板块接口
        df_industry = ak.stock_sector_spot(indicator="新浪行业")
        
        if df_industry is not None and not df_industry.empty:
            for i, (_, row) in enumerate(df_industry.iterrows()):
                records.append({
                    "date": target_date,
                    "sector_type": "industry",
                    "sector": row.get("板块", "") or row.get("名称", ""),
                    "change_pct": row.get("涨跌幅", 0),
                    "lead_stock": row.get("领涨股", "") or "",
                    "lead_stock_change": row.get("领涨股涨幅", 0) or 0,
                    "amount": row.get("成交额", 0) or 0,
                    "rank": i + 1,
                })
            log_debug(f"从新浪获取到 {len(df_industry)} 个行业板块")
    except Exception as e:
        log_debug(f"从新浪获取行业板块数据失败: {e}")
        # 新浪可能没有这个接口，继续尝试概念板块
    
    # 获取新浪概念板块数据
    try:
        # 新浪概念板块接口
        df_concept = ak.stock_sector_spot(indicator="概念")
        
        if df_concept is not None and not df_concept.empty:
            for i, (_, row) in enumerate(df_concept.iterrows()):
                records.append({
                    "date": target_date,
                    "sector_type": "concept",
                    "sector": row.get("板块", "") or row.get("名称", ""),
                    "change_pct": row.get("涨跌幅", 0),
                    "lead_stock": row.get("领涨股", "") or "",
                    "lead_stock_change": row.get("领涨股涨幅", 0) or 0,
                    "amount": row.get("成交额", 0) or 0,
                    "rank": i + 1,
                })
            log_debug(f"从新浪获取到 {len(df_concept)} 个概念板块")
    except Exception as e:
        log_debug(f"从新浪获取概念板块数据失败: {e}")
    
    # 如果新浪接口都失败了，尝试其他备选
    if not records:
        raise ValueError("新浪数据源返回空数据或不支持板块数据")
    
    return records


def fetch_sector_ranking_from_ths(target_date: str) -> List[Dict]:
    """
    从同花顺获取板块排名数据（备选数据源）
    
    Args:
        target_date: 目标日期
        
    Returns:
        板块排名数据列表
    """
    records = []
    
    # 获取同花顺行业板块数据
    try:
        df_industry = ak.stock_board_industry_name_ths()
        
        if df_industry is not None and not df_industry.empty:
            for i, (_, row) in enumerate(df_industry.iterrows()):
                records.append({
                    "date": target_date,
                    "sector_type": "industry",
                    "sector": row.get("name", ""),
                    "change_pct": 0,  # 同花顺接口不返回涨跌幅
                    "lead_stock": "",
                    "lead_stock_change": 0,
                    "amount": 0,
                    "rank": i + 1,
                })
            log_debug(f"从同花顺获取到 {len(df_industry)} 个行业板块")
    except Exception as e:
        log_debug(f"从同花顺获取行业板块数据失败: {e}")
        raise
    
    # 获取同花顺概念板块数据
    try:
        df_concept = ak.stock_board_concept_name_ths()
        
        if df_concept is not None and not df_concept.empty:
            for i, (_, row) in enumerate(df_concept.iterrows()):
                records.append({
                    "date": target_date,
                    "sector_type": "concept",
                    "sector": row.get("name", ""),
                    "change_pct": 0,
                    "lead_stock": "",
                    "lead_stock_change": 0,
                    "amount": 0,
                    "rank": i + 1,
                })
            log_debug(f"从同花顺获取到 {len(df_concept)} 个概念板块")
    except Exception as e:
        log_debug(f"从同花顺获取概念板块数据失败: {e}")
        raise
    
    if not records:
        raise ValueError("同花顺数据源返回空数据")
    
    return records


def register_sector_ranking_datasources():
    """注册板块排名数据源"""
    manager = get_manager()
    
    # 注册东财数据源（优先级 0）
    manager.register(
        "sector_ranking",
        DataSource(
            name="eastmoney",
            fetch_func=fetch_sector_ranking_from_eastmoney,
            priority=0,
            retry_count=3,
            retry_delay=2.0,
        )
    )
    
    # 注册同花顺数据源（优先级 1，备用）
    manager.register(
        "sector_ranking",
        DataSource(
            name="ths",
            fetch_func=fetch_sector_ranking_from_ths,
            priority=1,
            retry_count=2,
            retry_delay=2.0,
        )
    )
    
    # 注册新浪数据源（优先级 2，备用）
    manager.register(
        "sector_ranking",
        DataSource(
            name="sina",
            fetch_func=fetch_sector_ranking_from_sina,
            priority=2,
            retry_count=2,
            retry_delay=2.0,
        )
    )


def sync_sector_ranking(date: str = None):
    """
    同步板块排名数据（支持多数据源自动降级）
    
    Args:
        date: 指定日期（可选，默认为今天）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步板块排名数据: {target_date}")

    # 注册数据源
    register_sector_ranking_datasources()
    manager = get_manager()

    try:
        # 使用数据源管理器获取数据（自动降级）
        records = manager.fetch("sector_ranking", target_date)
        
        if records:
            save_sector_ranking(records)
            
            # 统计行业和概念板块数量
            industry_count = len([r for r in records if r["sector_type"] == "industry"])
            concept_count = len([r for r in records if r["sector_type"] == "concept"])
            
            log_info(f"板块排名数据同步完成: 行业 {industry_count} 个, 概念 {concept_count} 个")
        else:
            log_error("板块排名数据同步失败: 没有获取到任何数据")

    except Exception as e:
        log_error(f"同步板块排名数据失败: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="板块排名数据同步")
    parser.add_argument("--date", help="指定日期")
    
    args = parser.parse_args()
    sync_sector_ranking(date=args.date)
