"""
大盘指数历史数据回补脚本

支持一次性回补所有指数的全部历史数据
数据源：腾讯财经（一次性获取全部历史数据）
返回字段：date / open / close / high / low / amount（成交额，元）
"""

import argparse
from datetime import datetime
from typing import Dict, List

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error

# 指数代码映射
INDEX_CODES = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000300": "沪深 300",
    "000016": "上证 50",
}

def fetch_index_amount_from_eastmoney(symbol: str) -> Dict[str, float]:
    """
    从东方财富获取指数全部历史成交额数据
    
    Args:
        symbol: 指数代码（如 000001）
        
    Returns:
        {日期：成交额 (亿元)} 字典
    """
    log_info(f"正在从东方财富获取 {symbol} 成交额数据...")
    
    try:
        # 东方财富接口需要指定日期范围，使用较大范围获取全部历史数据
        df = ak.index_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date="19900101",
            end_date="20991231",
        )
        
        if df is None or df.empty:
            log_error(f"{symbol} 东方财富数据为空")
            return {}
        
        # 转换为 {日期：成交额 (亿元)} 字典
        amount_dict = {}
        for _, row in df.iterrows():
            date_str = str(row["日期"])
            amount_raw = float(row["成交额"]) if "成交额" in row else 0.0
            # 东方财富的成交额单位是元，转换成亿元
            amount_yi = amount_raw / 100000000
            amount_dict[date_str] = amount_yi
        
        log_info(f"成功获取 {len(amount_dict)} 条成交额数据")
        return amount_dict
        
    except Exception as e:
        log_error(f"获取 {symbol} 成交额数据失败：{e}")
        return {}

def fetch_all_index_history(symbol: str) -> List[Dict]:
    """
    从腾讯财经获取指数全部历史数据（收盘价、成交额）
    
    腾讯接口的 amount 字段是成交额（元）
    
    Args:
        symbol: 指数代码（如 000001）
        
    Returns:
        历史数据列表
    """
    # 腾讯接口需要添加市场前缀
    tx_symbol = f"sh{symbol}" if symbol.startswith("0") else f"sz{symbol}"
    
    log_info(f"正在获取 {tx_symbol} 历史数据...")
    
    try:
        # 获取全部历史数据（腾讯）
        df = ak.stock_zh_index_daily_tx(symbol=tx_symbol)
        
        if df is None or df.empty:
            log_error(f"{tx_symbol} 数据为空")
            return []
        
        log_info(f"成功获取 {len(df)} 条历史数据")
        
        # 转换为字典列表
        records = []
        for _, row in df.iterrows():
            date_str = str(row["date"])
            
            open_price = float(row["open"]) if "open" in row else 0.0
            close = float(row["close"]) if "close" in row else 0.0
            high = float(row["high"]) if "high" in row else 0.0
            low = float(row["low"]) if "low" in row else 0.0
            # 腾讯接口的 amount 字段是成交量（手），除以 1 亿换算为亿手存入 amount_yi
            amount_raw = float(row["amount"]) if "amount" in row else 0.0
            amount_yi = amount_raw / 100000000  # 手 → 亿手
            
            record = {
                "date": date_str,
                "code": symbol,
                "name": INDEX_CODES.get(symbol, ""),
                "open": open_price,
                "close": close,
                "high": high,
                "low": low,
                "change_pct": 0.0,  # 腾讯接口没有涨跌幅，后续计算
                "amount_yi": round(amount_yi, 2),
            }
            records.append(record)
        
        # 计算涨跌幅
        for i in range(1, len(records)):
            prev_close = records[i-1]["close"]
            curr_close = records[i]["close"]
            if prev_close > 0:
                records[i]["change_pct"] = round((curr_close - prev_close) / prev_close * 100, 2)
        
        return records
        
    except Exception as e:
        log_error(f"获取 {tx_symbol} 历史数据失败：{e}")
        return []

def save_index_records(records: List[Dict]):
    """
    保存指数数据到数据库
    
    Args:
        records: 数据记录列表
    """
    if not records:
        return
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        insert_count = 0
        for record in records:
            cursor.execute(
                """
                INSERT OR REPLACE INTO index_daily
                (date, code, name, open, close, high, low, change_pct, amount_yi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["date"],
                    record["code"],
                    record["name"],
                    record.get("open"),
                    record["close"],
                    record.get("high"),
                    record.get("low"),
                    record["change_pct"],
                    record["amount_yi"],
                ),
            )
            insert_count += 1
        
        conn.commit()
        log_info(f"成功写入 {insert_count} 条记录")
        
    except Exception as e:
        log_error(f"保存数据失败：{e}")
        conn.rollback()
    finally:
        conn.close()

def backfill_all_indices():
    """
    回补所有指数的全部历史数据
    """
    log_info("=" * 60)
    log_info("开始回补大盘指数历史数据")
    log_info("=" * 60)
    
    total_records = 0
    
    for code, name in INDEX_CODES.items():
        log_info(f"\n正在回补：{name} ({code})")
        
        # 获取历史数据
        records = fetch_all_index_history(code)
        
        if records:
            # 保存到数据库
            save_index_records(records)
            total_records += len(records)
            log_info(f"✓ {name} 回补完成：{len(records)} 条")
        else:
            log_error(f"✗ {name} 回补失败：未获取到数据")
    
    log_info("\n" + "=" * 60)
    log_info(f"大盘指数历史数据回补完成")
    log_info(f"总计写入：{total_records} 条记录")
    log_info("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="回补大盘指数历史数据")
    parser.add_argument("--all", action="store_true", help="回补所有指数")
    parser.add_argument("--code", type=str, help="指定指数代码（如 000001）")
    
    args = parser.parse_args()
    
    if args.all or args.code:
        if args.code:
            # 回补指定指数
            if args.code not in INDEX_CODES:
                log_error(f"未知的指数代码：{args.code}")
                return
            
            log_info(f"回补单个指数：{INDEX_CODES[args.code]} ({args.code})")
            records = fetch_all_index_history(args.code)
            if records:
                save_index_records(records)
        else:
            # 回补所有指数
            backfill_all_indices()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
