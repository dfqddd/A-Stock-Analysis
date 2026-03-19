"""
股票基础信息同步脚本

数据来源：
  - 上交所、深交所、北交所股票列表（主数据源，优先级 0）
  - 腾讯股票详情接口（市值、PE、PB等，备选数据源，优先级 1）
"""

import argparse
from datetime import datetime
from typing import Dict, List, Optional
import time

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.datasource import DataSource, get_manager


def fetch_stock_list_from_exchanges() -> List[Dict]:
    """
    从交易所获取全部A股股票列表（主数据源）

    Returns:
        股票列表 [{'code': '000001', 'name': '平安银行', 'exchange': 'SZ'}, ...]
    """
    stocks = []

    try:
        # 上交所股票
        df_sh = ak.stock_info_sh_name_code()
        for _, row in df_sh.iterrows():
            stocks.append({
                "code": str(row["证券代码"]).zfill(6),
                "name": row["证券简称"],
                "exchange": "SH",
            })
        log_debug(f"上交所: {len(df_sh)} 只")
    except Exception as e:
        log_error(f"获取上交所股票列表失败: {e}")
        raise

    try:
        # 深交所股票
        df_sz = ak.stock_info_sz_name_code()
        for _, row in df_sz.iterrows():
            stocks.append({
                "code": str(row["A股代码"]).zfill(6),
                "name": row["A股简称"],
                "exchange": "SZ",
            })
        log_debug(f"深交所: {len(df_sz)} 只")
    except Exception as e:
        log_error(f"获取深交所股票列表失败: {e}")
        raise

    try:
        # 北交所股票
        df_bj = ak.stock_info_bj_name_code()
        for _, row in df_bj.iterrows():
            stocks.append({
                "code": str(row["证券代码"]).zfill(6),
                "name": row["证券简称"],
                "exchange": "BJ",
            })
        log_debug(f"北交所: {len(df_bj)} 只")
    except Exception as e:
        log_error(f"获取北交所股票列表失败: {e}")
        raise

    log_info(f"共获取 {len(stocks)} 只股票")
    return stocks


def fetch_stock_list_from_akshare() -> List[Dict]:
    """
    从 AKShare 统一接口获取股票列表（备选数据源）

    Returns:
        股票列表 [{'code': '000001', 'name': '平安银行', 'exchange': 'SZ'}, ...]
    """
    try:
        # 使用 AKShare 统一接口获取所有A股
        df = ak.stock_zh_a_spot_em()
        
        if df is None or df.empty:
            raise ValueError("AKShare 返回空数据")
        
        stocks = []
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).zfill(6)
            # 根据代码前缀判断交易所
            exchange = "SH" if code.startswith("6") else "SZ"
            if code.startswith("8") or code.startswith("4"):
                exchange = "BJ"
            
            stocks.append({
                "code": code,
                "name": row.get("名称", ""),
                "exchange": exchange,
            })
        
        log_info(f"从 AKShare 获取到 {len(stocks)} 只股票")
        return stocks
    except Exception as e:
        log_error(f"从 AKShare 获取股票列表失败: {e}")
        raise


def register_stock_list_datasources():
    """注册股票列表数据源"""
    manager = get_manager()
    
    # 注册交易所数据源（优先级 0，主数据源）
    manager.register(
        "stock_list",
        DataSource(
            name="exchanges",
            fetch_func=fetch_stock_list_from_exchanges,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )
    
    # 注册 AKShare 数据源（优先级 1，备选）
    manager.register(
        "stock_list",
        DataSource(
            name="akshare",
            fetch_func=fetch_stock_list_from_akshare,
            priority=1,
            retry_count=3,
            retry_delay=1.0,
        )
    )


def fetch_stock_details_from_spot(codes: List[str]) -> Dict[str, Dict]:
    """
    从东财实时行情获取股票详情（市值、PE、PB等）

    Args:
        codes: 股票代码列表

    Returns:
        {code: {total_market_cap_yi, pe_ratio, pb_ratio, ...}, ...}
    """
    details = {}
    
    try:
        # 获取全部实时行情数据（批量获取更高效）
        df = ak.stock_zh_a_spot_em()
        
        if df is None or df.empty:
            raise ValueError("东财实时行情接口返回空数据")
        
        for code in codes:
            row = df[df["代码"] == code]
            if not row.empty:
                row = row.iloc[0]
                details[code] = {
                    "total_market_cap_yi": float(row.get("总市值", 0) or 0) / 100000000,
                    "pe_ratio": float(row.get("市盈率-动态", 0) or 0),
                    "pb_ratio": float(row.get("市净率", 0) or 0),
                }
        
        log_debug(f"从东财实时行情获取到 {len(details)} 只股票详情")
        return details
    except Exception as e:
        log_error(f"从东财实时行情获取股票详情失败: {e}")
        raise


def register_stock_details_datasources():
    """注册股票详情数据源"""
    manager = get_manager()
    
    # 注册东财实时行情数据源（优先级 0）
    manager.register(
        "stock_details",
        DataSource(
            name="eastmoney_spot",
            fetch_func=fetch_stock_details_from_spot,
            priority=0,
            retry_count=3,
            retry_delay=1.0,
        )
    )


def save_stock_info(stocks: List[Dict], details: Dict[str, Dict] = None):
    """
    将股票信息写入数据库。

    如果 details 不为空，则补充市值等信息。

    注意：数据库表结构字段为：
    - code, name, market, board, industry, concepts, main_business
    - total_market_cap_yi, circulating_cap_yi, pe_ratio, pb_ratio
    - roe, gross_margin, net_profit_yi, revenue_yi, profit_yoy, revenue_yoy
    - updated_at
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        updated_count = 0
        inserted_count = 0

        for i, stock in enumerate(stocks):
            code = stock["code"]
            detail = details.get(code, {}) if details else {}

            # 根据 exchange 字段设置 market 字段
            exchange = stock.get("exchange", "")
            market = ""
            if exchange == "SH":
                market = "sh"
            elif exchange == "SZ":
                market = "sz"
            elif exchange == "BJ":
                market = "bj"

            # 检查是否已存在
            existing = cursor.execute(
                "SELECT code FROM stock_info WHERE code = ?", (code,)
            ).fetchone()

            if existing:
                # 更新（只更新数据库中存在的字段）
                cursor.execute(
                    """UPDATE stock_info SET 
                       name = ?, market = ?, industry = ?,
                       total_market_cap_yi = ?, pe_ratio = ?, pb_ratio = ?, updated_at = ?
                       WHERE code = ?""",
                    (
                        stock.get("name"),
                        market,
                        stock.get("industry"),
                        detail.get("total_market_cap_yi"),
                        detail.get("pe_ratio"),
                        detail.get("pb_ratio"),
                        now,
                        code,
                    ),
                )
                updated_count += 1
            else:
                # 插入（只插入数据库中存在的字段）
                cursor.execute(
                    """INSERT INTO stock_info 
                       (code, name, market, industry, 
                        total_market_cap_yi, pe_ratio, pb_ratio, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        code,
                        stock.get("name"),
                        market,
                        stock.get("industry"),
                        detail.get("total_market_cap_yi"),
                        detail.get("pe_ratio"),
                        detail.get("pb_ratio"),
                        now,
                    ),
                )
                inserted_count += 1

            # 每 500 条提交一次，避免一次性提交太多数据
            if (i + 1) % 500 == 0:
                conn.commit()
                log_debug(f"已提交 {i + 1}/{len(stocks)} 条记录")

        conn.commit()
        log_info(f"已写入 {len(stocks)} 只股票信息 (更新: {updated_count}, 新增: {inserted_count})")
    except Exception as e:
        log_error(f"写入股票信息失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def sync_stock_info(skip_details: bool = False):
    """
    同步股票基础信息（支持多数据源自动降级）

    Args:
        skip_details: 是否跳过详情获取（加快同步速度）
    """
    log_info("开始同步股票基础信息...")

    # 1. 注册并获取股票列表（支持多数据源自动降级）
    register_stock_list_datasources()
    manager = get_manager()
    
    try:
        stocks = manager.fetch("stock_list")
    except Exception as e:
        log_error(f"获取股票列表失败: {e}")
        return
    
    if not stocks:
        log_error("获取股票列表为空")
        return

    # 2. 获取股票详情（可选，支持多数据源）
    details = {}
    if not skip_details:
        try:
            register_stock_details_datasources()
            codes = [s["code"] for s in stocks]
            details = manager.fetch("stock_details", codes)
        except Exception as e:
            log_error(f"获取股票详情失败: {e}")
            # 详情获取失败不影响基础信息同步

    # 3. 写入数据库
    save_stock_info(stocks, details)

    log_info("股票基础信息同步完成")


def main():
    parser = argparse.ArgumentParser(description="同步股票基础信息")
    parser.add_argument("--skip-details", action="store_true", help="跳过详情获取")

    args = parser.parse_args()
    sync_stock_info(skip_details=args.skip_details)


if __name__ == "__main__":
    main()
