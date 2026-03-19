"""
资金面分析脚本
基于 AKShare 获取主力资金流向、龙虎榜、融资融券等数据
（北向资金已停止披露，已移除相关功能）

已移除不稳定的东方财富数据源，改用腾讯、新浪、同花顺等稳定数据源
"""

import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error, get_latest_date


def save_capital_flow(records: List[Dict]):
    """将资金流向数据写入数据库"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO capital_flow
                (date, north_net_yi, sh_connect_yi, sz_connect_yi)
                VALUES (?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record.get("north_net"),  # north_net 对应 north_net_yi
                    record.get("north_sh"),   # north_sh 对应 sh_connect_yi
                    record.get("north_sz"),   # north_sz 对应 sz_connect_yi
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条资金流向数据")
    finally:
        conn.close()


def fetch_north_flow(days: int = 30) -> pd.DataFrame:
    """
    获取北向资金数据

    Args:
        days: 获取最近多少天的数据

    Returns:
        北向资金数据 DataFrame
    """
    try:
        # 使用 AKShare 获取资金流向汇总数据
        df = ak.stock_hsgt_fund_flow_summary_em()

        if df is None or df.empty:
            return None

        # 筛选北向资金数据
        north_df = df[df['资金方向'] == '北向'].copy()
        
        if north_df.empty:
            return None

        # 只保留最近 days 天（每天有2行：沪股通+深股通）
        if days:
            unique_dates = north_df['交易日'].unique()
            if len(unique_dates) > days:
                recent_dates = unique_dates[-days:]
                north_df = north_df[north_df['交易日'].isin(recent_dates)]

        return north_df
    except Exception as e:
        log_error(f"获取北向资金失败: {e}")
        return None


def fetch_south_flow(days: int = 30) -> pd.DataFrame:
    """
    获取南向资金数据

    Args:
        days: 获取最近多少天的数据

    Returns:
        南向资金数据 DataFrame
    """
    try:
        # 使用 AKShare 获取资金流向汇总数据
        df = ak.stock_hsgt_fund_flow_summary_em()

        if df is None or df.empty:
            return None

        # 筛选南向资金数据
        south_df = df[df['资金方向'] == '南向'].copy()
        
        if south_df.empty:
            return None

        # 只保留最近 days 天（每天有2行：港股通沪+港股通深）
        if days:
            unique_dates = south_df['交易日'].unique()
            if len(unique_dates) > days:
                recent_dates = unique_dates[-days:]
                south_df = south_df[south_df['交易日'].isin(recent_dates)]

        return south_df
    except Exception as e:
        log_error(f"获取南向资金失败: {e}")
        return None


def sync_capital_flow(days: int = 30):
    """
    同步资金流向数据

    Args:
        days: 同步最近多少天
    """
    log_info("开始同步资金流向数据...")

    # 获取北向资金
    north_df = fetch_north_flow(days=days)
    # 获取南向资金
    south_df = fetch_south_flow(days=days)

    if north_df is None and south_df is None:
        log_error("获取资金流向数据失败")
        return

    # 合并数据
    records = []

    if north_df is not None:
        for _, row in north_df.iterrows():
            date_str = str(row.get("交易日", ""))[:10]
            if not date_str:
                continue

            # 根据板块区分沪股通和深股通
            board = row.get("板块", "")
            # 成交净买额 单位是亿元
            net_flow = row.get("成交净买额", 0)
            
            # 只处理北向资金（沪股通、深股通）
            if board not in ["沪股通", "深股通"]:
                continue
            
            record = {
                "date": date_str,
                "north_net": net_flow,
                "north_sh": net_flow if board == "沪股通" else None,
                "north_sz": net_flow if board == "深股通" else None,
            }
            
            # 如果该日期的记录已存在，更新数据
            existing = next((r for r in records if r["date"] == date_str), None)
            if existing:
                if board == "沪股通":
                    existing["north_sh"] = net_flow
                elif board == "深股通":
                    existing["north_sz"] = net_flow
                # 累加北向资金总额
                if existing["north_net"] is None:
                    existing["north_net"] = net_flow
                else:
                    existing["north_net"] += net_flow
            else:
                records.append(record)

    # 合并南向资金数据
    if south_df is not None:
        south_by_date = {}
        for _, row in south_df.iterrows():
            date_str = str(row.get("交易日", ""))[:10]
            if date_str:
                # 根据板块区分港股通(沪)和港股通(深)
                board = row.get("板块", "")
                net_flow = row.get("资金净流入", 0)
                
                if date_str not in south_by_date:
                    south_by_date[date_str] = {
                        "south_net": 0,
                        "south_hk": 0,
                    }
                
                # 累加南向资金
                south_by_date[date_str]["south_net"] += net_flow
                south_by_date[date_str]["south_hk"] += net_flow

        # 更新 records 中的南向数据
        for record in records:
            date_str = record["date"]
            if date_str in south_by_date:
                record.update(south_by_date[date_str])

    # 写入数据库
    if records:
        save_capital_flow(records)
        log_info(f"已写入 {len(records)} 条资金流向数据")


def analyze_capital_flow(date: str = None) -> Dict[str, Any]:
    """
    分析资金流向情况

    Args:
        date: 指定日期（可选，默认今天）

    Returns:
        资金流向分析结果
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 获取当日资金流向
        today_flow = cursor.execute(
            "SELECT * FROM capital_flow WHERE date = ?", (target_date,)
        ).fetchone()

        if not today_flow:
            log_debug(f"无 {target_date} 资金流向数据，请先同步")
            return {}

        # 获取最近5日资金流向
        recent_flows = cursor.execute(
            """
            SELECT date, north_net_yi FROM capital_flow
            ORDER BY date DESC LIMIT 5
            """
        ).fetchall()

        # 计算资金流向趋势
        north_trend = "流入" if today_flow["north_net_yi"] and today_flow["north_net_yi"] > 0 else "流出"

        # 计算近5日净流入
        north_5d_sum = sum([r["north_net_yi"] or 0 for r in recent_flows])

        return {
            "date": target_date,
            "north": {
                "net_flow": today_flow["north_net_yi"],
                "sh_flow": today_flow["sh_connect_yi"],
                "sz_flow": today_flow["sz_connect_yi"],
                "trend": north_trend,
                "flow_5d": north_5d_sum,
            },
            "south": {
                "net_flow": None,
                "hk_flow": None,
                "trend": "未知",
                "flow_5d": 0,
            },
            "recent_flows": [dict(r) for r in recent_flows],
        }

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="资金面分析")
    parser.add_argument("--sync", action="store_true", help="同步数据")
    parser.add_argument("--analyze", action="store_true", help="分析数据")
    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--days", type=int, default=30, help="同步天数")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")

    args = parser.parse_args()

    if args.sync:
        sync_capital_flow(days=args.days)
    elif args.analyze:
        result = analyze_capital_flow(date=args.date)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"资金流向分析 ({result.get('date', 'N/A')})")
            print(f"北向资金: 净{result['north']['trend']} {result['north']['net_flow']}亿")
            print(f"南向资金: 净{result['south']['trend']} {result['south']['net_flow']}亿")
    else:
        # 默认执行同步和分析
        sync_capital_flow(days=args.days)
        result = analyze_capital_flow(date=args.date)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
