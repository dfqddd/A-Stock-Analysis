"""
实时数据获取模块

从多个第三方平台获取实时市场数据，用于补充 AKShare 数据的不足。
支持的数据源：
- 新浪财经
- 东方财富
- 同花顺（通过 Tushare）
"""

import json
import re
from datetime import datetime
from typing import Dict, Optional

import requests

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error


def fetch_sina_limit_up_data() -> Dict:
    """
    从新浪财经获取涨停数据
    
    Returns:
        {
            "limit_up_count": 涨停数,
            "broken_count": 炸板数,
            "seal_rate": 封板率,
            "source": "sina"
        }
    """
    try:
        # 新浪财经没有直接提供涨停炸板数据的公开 API
        # 尝试通过 stock_zh_a_spot_em 获取实时行情数据计算
        import akshare as ak
        
        # 获取全市场实时行情
        df = ak.stock_zh_a_spot_em()
        
        if df is not None and not df.empty:
            # 计算涨停数（涨跌幅 >= 9.9%）
            limit_up_count = len(df[df["涨跌幅"] >= 9.9])
            
            # 新浪财经不提供炸板数据，返回空让其他数据源处理
            log_debug("新浪财经不提供炸板数据，返回基础涨停数据")
            return {
                "limit_up_count": limit_up_count,
                "broken_count": 0,  # 无法获取
                "seal_rate": 0,     # 无法计算
                "source": "sina"
            }
        
        return {}
    except Exception as e:
        log_error(f"获取新浪财经涨停数据失败: {e}")
        return {}


def fetch_eastmoney_limit_up_data(date: str = None) -> Dict:
    """
    从东方财富获取涨停数据
    
    使用东方财富的 API 获取准确的涨停、炸板数据
    
    Args:
        date: 日期，格式 YYYY-MM-DD
        
    Returns:
        {
            "limit_up_count": 涨停数,
            "broken_count": 炸板数, 
            "seal_rate": 封板率,
            "source": "eastmoney"
        }
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        # 东方财富涨停数据接口
        # 参考 AKShare 的实现，使用相同的 API 端点但获取更多信息
        url = "http://push2ex.eastmoney.com/getTopicZTPool"
        
        # 尝试获取涨停数据
        import akshare as ak
        
        # 获取涨停池数据
        api_date = target_date.replace("-", "")
        df_zt = ak.stock_zt_pool_em(date=api_date)
        
        if df_zt is not None and not df_zt.empty:
            limit_up_count = len(df_zt)
            
            # 尝试获取炸板数据
            # 东方财富有专门的炸板数据接口
            try:
                df_broken = ak.stock_zt_pool_zbgc_em(date=api_date)
                broken_count = len(df_broken) if df_broken is not None else 0
            except:
                broken_count = 0
            
            # 计算封板率
            total_once_limit_up = limit_up_count + broken_count
            seal_rate = round(limit_up_count / total_once_limit_up * 100, 1) if total_once_limit_up > 0 else 100.0
            
            return {
                "limit_up_count": limit_up_count,
                "broken_count": broken_count,
                "seal_rate": seal_rate,
                "total_once_limit_up": total_once_limit_up,
                "source": "eastmoney",
                "date": target_date
            }
        
        return {}
        
    except Exception as e:
        log_error(f"获取东方财富涨停数据失败: {e}")
        return {}


def fetch_tushare_limit_up_data(date: str = None) -> Dict:
    """
    从 Tushare 获取涨停数据（需要 Pro 权限）
    
    Args:
        date: 日期，格式 YYYY-MM-DD
        
    Returns:
        {
            "limit_up_count": 涨停数,
            "broken_count": 炸板数,
            "seal_rate": 封板率,
            "source": "tushare"
        }
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        import tushare as ts
        
        # 需要设置 Tushare Token
        # ts.set_token('your_token_here')
        pro = ts.pro_api()
        
        # 获取涨跌停数据
        df = pro.limit_list_d(trade_date=target_date.replace("-", ""))
        
        if df is not None and not df.empty:
            limit_up_count = len(df[df['limit'] == 'U'])  # 涨停
            broken_count = len(df[df['limit'] == 'Z'])    # 炸板
            
            total_once_limit_up = limit_up_count + broken_count
            seal_rate = round(limit_up_count / total_once_limit_up * 100, 1) if total_once_limit_up > 0 else 100.0
            
            return {
                "limit_up_count": limit_up_count,
                "broken_count": broken_count,
                "seal_rate": seal_rate,
                "source": "tushare",
                "date": target_date
            }
        
        return {}
        
    except Exception as e:
        log_debug(f"Tushare 获取涨停数据失败（可能需要 Pro 权限）: {e}")
        return {}


def get_realtime_seal_rate(date: str = None) -> Dict:
    """
    获取实时封板率数据（多数据源聚合）
    
    优先从多个数据源获取数据，返回最可靠的结果
    
    Args:
        date: 日期，格式 YYYY-MM-DD
        
    Returns:
        {
            "limit_up_count": 涨停数,
            "broken_count": 炸板数,
            "seal_rate": 封板率,
            "source": 数据来源,
            "date": 日期
        }
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    # 尝试多个数据源
    sources = [
        ("eastmoney", fetch_eastmoney_limit_up_data),
        ("tushare", fetch_tushare_limit_up_data),
        ("sina", fetch_sina_limit_up_data),
    ]
    
    for source_name, fetch_func in sources:
        try:
            data = fetch_func(target_date)
            if data and data.get("seal_rate", 0) > 0:
                log_info(f"从 {source_name} 获取到封板率数据: {data['seal_rate']}%")
                return data
        except Exception as e:
            log_debug(f"{source_name} 数据源获取失败: {e}")
            continue
    
    # 所有数据源都失败，返回空数据
    log_error("所有实时数据源都无法获取封板率数据")
    return {}


def update_sentiment_with_realtime_data(date: str = None) -> bool:
    """
    使用实时数据更新 sentiment 表
    
    Args:
        date: 日期，格式 YYYY-MM-DD
        
    Returns:
        是否更新成功
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    # 获取实时数据
    realtime_data = get_realtime_seal_rate(target_date)
    
    if not realtime_data:
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 更新 sentiment 表
        cursor.execute(
            """
            UPDATE sentiment 
            SET seal_rate = ?,
                broken_count = ?,
                limit_up_total = ?
            WHERE date = ?
            """,
            (
                realtime_data.get("seal_rate", 0),
                realtime_data.get("broken_count", 0),
                realtime_data.get("total_once_limit_up", 0),
                target_date
            )
        )
        
        conn.commit()
        conn.close()
        
        log_info(f"已使用实时数据更新 {target_date} 的封板率: {realtime_data['seal_rate']}%")
        return True
        
    except Exception as e:
        log_error(f"更新 sentiment 表失败: {e}")
        return False


if __name__ == "__main__":
    # 测试
    data = get_realtime_seal_rate()
    print(json.dumps(data, ensure_ascii=False, indent=2))
