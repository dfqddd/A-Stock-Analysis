"""
A股板块轮动分析脚本
基于 AKShare 获取行业板块和概念板块的涨跌幅排名、资金流向等信息
输出结构化 JSON 格式数据
"""

import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error


def save_sector_ranking(records: List[Dict]):
    """将板块排名数据写入数据库"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO sector_ranking
                (date, sector_type, name, change_pct, leading_stock, lead_stock_change, amount, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record["sector_type"],
                    record["sector"],
                    record.get("change_pct"),
                    record.get("lead_stock"),
                    record.get("lead_stock_change", 0),
                    record.get("amount", 0),
                    record.get("rank"),
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条板块排名数据")
    finally:
        conn.close()


def fetch_industry_ranking() -> List[Dict]:
    """
    获取行业板块涨跌幅排名

    Returns:
        行业板块排名列表
    """
    try:
        # 使用 AKShare 获取行业板块数据
        df = ak.stock_board_industry_name_em()

        if df is None or df.empty:
            return []

        records = []
        for i, (_, row) in enumerate(df.iterrows()):
            records.append({
                "sector_type": "industry",
                "sector": row.get("板块名称", ""),
                "change_pct": row.get("涨跌幅", 0),
                "lead_stock": row.get("领涨股票", ""),
                "lead_stock_change": row.get("领涨股票-涨跌幅", 0),
                "amount": row.get("总市值", 0),
                "rank": i + 1,
            })

        return records

    except Exception as e:
        log_error(f"获取行业板块排名失败: {e}")
        return []


def fetch_concept_ranking() -> List[Dict]:
    """
    获取概念板块涨跌幅排名

    Returns:
        概念板块排名列表
    """
    try:
        # 使用 AKShare 获取概念板块数据
        df = ak.stock_board_concept_name_em()

        if df is None or df.empty:
            return []

        records = []
        for i, (_, row) in enumerate(df.iterrows()):
            records.append({
                "sector_type": "concept",
                "sector": row.get("板块名称", ""),
                "change_pct": row.get("涨跌幅", 0),
                "lead_stock": row.get("领涨股票", ""),
                "lead_stock_change": row.get("领涨股票-涨跌幅", 0),
                "amount": row.get("总市值", 0),
                "rank": i + 1,
            })

        return records

    except Exception as e:
        log_error(f"获取概念板块排名失败: {e}")
        return []


def sync_sector_ranking(date: str = None):
    """
    同步板块排名数据

    Args:
        date: 指定日期（可选）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步板块排名数据: {target_date}")

    # 获取行业板块
    industry_records = fetch_industry_ranking()
    for record in industry_records:
        record["date"] = target_date

    # 获取概念板块
    concept_records = fetch_concept_ranking()
    for record in concept_records:
        record["date"] = target_date

    # 合并并写入
    all_records = industry_records + concept_records

    if all_records:
        save_sector_ranking(all_records)
        log_info(f"已写入 {len(all_records)} 条板块排名数据 (行业 {len(industry_records)}, 概念 {len(concept_records)})")
    else:
        log_error("获取板块排名数据失败")


def analyze_sector(date: str = None, top_n: int = 10) -> Dict[str, Any]:
    """
    分析板块轮动情况

    Args:
        date: 指定日期（可选）
        top_n: 返回前 N 个板块

    Returns:
        板块分析结果
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 获取当日行业板块排名
        industry_top = cursor.execute(
            """
            SELECT * FROM sector_ranking
            WHERE date = ? AND type = 'industry'
            ORDER BY change_pct DESC LIMIT ?
            """,
            (target_date, top_n),
        ).fetchall()

        # 获取当日概念板块排名
        concept_top = cursor.execute(
            """
            SELECT * FROM sector_ranking
            WHERE date = ? AND type = 'concept'
            ORDER BY change_pct DESC LIMIT ?
            """,
            (target_date, top_n),
        ).fetchall()

        # 获取行业板块跌幅榜
        industry_bottom = cursor.execute(
            """
            SELECT * FROM sector_ranking
            WHERE date = ? AND type = 'industry'
            ORDER BY change_pct ASC LIMIT ?
            """,
            (target_date, top_n),
        ).fetchall()

        if not industry_top and not concept_top:
            log_debug(f"无 {target_date} 板块排名数据，请先同步")
            return {}

        return {
            "date": target_date,
            "industry_top": [dict(r) for r in industry_top],
            "industry_bottom": [dict(r) for r in industry_bottom],
            "concept_top": [dict(r) for r in concept_top],
        }

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="板块轮动分析")
    parser.add_argument("--sync", action="store_true", help="同步数据")
    parser.add_argument("--analyze", action="store_true", help="分析数据")
    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--top", type=int, default=10, help="返回前 N 个板块")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")

    args = parser.parse_args()

    if args.sync:
        sync_sector_ranking(date=args.date)
    elif args.analyze:
        result = analyze_sector(date=args.date, top_n=args.top)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"板块轮动分析 ({result.get('date', 'N/A')})")
            print("\n行业涨幅榜:")
            for s in result.get("industry_top", [])[:5]:
                print(f"  {s['sector']}: +{s['change_pct']:.2f}%")
            print("\n概念涨幅榜:")
            for s in result.get("concept_top", [])[:5]:
                print(f"  {s['sector']}: +{s['change_pct']:.2f}%")
    else:
        # 默认执行同步和分析
        sync_sector_ranking(date=args.date)
        result = analyze_sector(date=args.date, top_n=args.top)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
