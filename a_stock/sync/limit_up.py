"""
涨停股数据同步脚本

数据来源：
  - 东财涨停数据（主数据源，优先级 0）
  - 东财跌停数据（主数据源，优先级 0）
"""

import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.datasource import DataSource, get_manager


def fetch_limit_up_eastmoney(date: str) -> List[Dict]:
    """
    使用东财数据源获取涨停数据

    Args:
        date: 日期（格式：YYYY-MM-DD）

    Returns:
        涨停数据列表
    """
    try:
        # API 需要 YYYYMMDD 格式
        api_date = date.replace("-", "")
        
        df_zt = ak.stock_zt_pool_em(date=api_date)
        
        if df_zt is None or df_zt.empty:
            return []
        
        log_debug(f"从东财获取到 {len(df_zt)} 只涨停股")
        
        records = []
        for _, row in df_zt.iterrows():
            record = {
                "date": date,
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "status": "涨停",
                "change_pct": row.get("涨跌幅"),
                "close": row.get("最新价"),
                "limit_up_price": row.get("最新价"),
                "amount_yi": row.get("成交额", 0) / 100000000 if row.get("成交额") else 0,
                "circulating_cap_yi": row.get("流通市值", 0) / 100000000 if row.get("流通市值") else 0,
                "total_cap_yi": row.get("总市值", 0) / 100000000 if row.get("总市值") else 0,
                "turnover_rate": row.get("换手率"),
                "seal_amount_yi": row.get("封板资金", 0) / 100000000 if row.get("封板资金") else 0,
                "first_seal_time": str(row.get("首次封板时间", "")),
                "last_seal_time": str(row.get("最后封板时间", "")),
                "broken_count": row.get("炸板次数", 0),
                "continuous_board": row.get("连板数", 1),
                "limit_up_stat": str(row.get("涨停统计", "")),
                "amplitude": row.get("涨跌幅"),
                "speed": 0,
                "industry": row.get("所属行业"),
            }
            records.append(record)
        
        return records
    except Exception as e:
        log_debug(f"东财数据源获取涨停数据失败: {e}")
        raise

def fetch_limit_down_eastmoney(date: str) -> List[Dict]:
    """
    使用东财数据源获取跌停数据

    Args:
        date: 日期（格式：YYYY-MM-DD）

    Returns:
        跌停数据列表
    """
    try:
        # API 需要 YYYYMMDD 格式
        api_date = date.replace("-", "")
        
        df_dt = ak.stock_zt_pool_dtgc_em(date=api_date)
        
        if df_dt is None or df_dt.empty:
            return []
        
        log_debug(f"从东财获取到 {len(df_dt)} 只跌停股")
        
        records = []
        for _, row in df_dt.iterrows():
            record = {
                "date": date,
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "status": "跌停",
                "change_pct": row.get("涨跌幅"),
                "close": row.get("最新价"),
                "limit_up_price": row.get("最新价"),
                "amount_yi": row.get("成交额", 0) / 100000000 if row.get("成交额") else 0,
                "circulating_cap_yi": row.get("流通市值", 0) / 100000000 if row.get("流通市值") else 0,
                "total_cap_yi": row.get("总市值", 0) / 100000000 if row.get("总市值") else 0,
                "turnover_rate": row.get("换手率"),
                "seal_amount_yi": row.get("封单资金", 0) / 100000000 if row.get("封单资金") else 0,
                "first_seal_time": str(row.get("最后封板时间", "")),
                "last_seal_time": str(row.get("最后封板时间", "")),
                "broken_count": row.get("开板次数", 0),
                "continuous_board": row.get("连续跌停", 1),
                "limit_up_stat": "",
                "amplitude": row.get("涨跌幅"),
                "speed": 0,
                "industry": row.get("所属行业"),
            }
            records.append(record)
        
        return records
    except Exception as e:
        log_debug(f"东财数据源获取跌停数据失败: {e}")
        raise

def register_datasources():
    """注册数据源到管理器"""
    manager = get_manager()
    
    # 注册东财涨停数据源（优先级 0）
    manager.register(
        "limit_up",
        DataSource(
            name="eastmoney",
            fetch_func=fetch_limit_up_eastmoney,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )
    
    # 注册东财跌停数据源（优先级 0）
    manager.register(
        "limit_down",
        DataSource(
            name="eastmoney",
            fetch_func=fetch_limit_down_eastmoney,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )

def save_limit_up_detail(records: List[Dict]):
    """将涨停详情写入数据库"""
    if not records:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO limit_up_detail
                (date, code, name, status, change_pct, close, limit_up_price,
                 amount_yi, circulating_cap_yi, total_cap_yi, turnover_rate,
                 seal_amount_yi, first_seal_time, last_seal_time, broken_count,
                 continuous_board, limit_up_stat, amplitude, speed, industry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record["code"],
                    record["name"],
                    record.get("status", "涨停"),
                    record.get("change_pct"),
                    record.get("close"),
                    record.get("limit_up_price"),
                    record.get("amount_yi"),
                    record.get("circulating_cap_yi"),
                    record.get("total_cap_yi"),
                    record.get("turnover_rate"),
                    record.get("seal_amount_yi"),
                    record.get("first_seal_time"),
                    record.get("last_seal_time"),
                    record.get("broken_count", 0),
                    record.get("continuous_board", 1),
                    record.get("limit_up_stat"),
                    record.get("amplitude"),
                    record.get("speed"),
                    record.get("industry"),
                ),
            )

        conn.commit()
        log_debug(f"已写入 {len(records)} 条涨停详情")
    finally:
        conn.close()


def sync_limit_up(date: str = None):
    """
    同步涨停股和跌停股数据

    Args:
        date: 指定日期（可选，格式：YYYY-MM-DD）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"开始同步涨停跌停数据: {target_date}")

    # 交易日校验：非交易日不同步，避免写入重复数据
    try:
        from a_stock.utils.trading_calendar import is_trading_day
        if not is_trading_day(target_date):
            log_info(f"⚠️ {target_date} 非交易日，跳过涨停数据同步")
            return
    except Exception as e:
        log_debug(f"交易日校验异常({e})，继续同步")

    try:
        # 注册数据源
        register_datasources()
        
        # 获取数据源管理器
        manager = get_manager()
        
        records = []
        
        # 1. 使用数据源管理器同步涨停数据
        try:
            limit_up_records = manager.fetch("limit_up", target_date)
            records.extend(limit_up_records)
        except Exception as e:
            log_debug(f"获取涨停数据失败: {e}")
        
        # 2. 使用数据源管理器同步跌停数据
        try:
            limit_down_records = manager.fetch("limit_down", target_date)
            records.extend(limit_down_records)
        except Exception as e:
            log_debug(f"获取跌停数据失败: {e}")

        # 写入数据库
        if records:
            save_limit_up_detail(records)
            log_info(f"已写入 {len(records)} 条涨跌停详情")

    except Exception as e:
        log_error(f"同步涨跌停数据失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="同步涨停股数据")
    parser.add_argument("--date", help="指定日期")

    args = parser.parse_args()
    sync_limit_up(date=args.date)


if __name__ == "__main__":
    main()
