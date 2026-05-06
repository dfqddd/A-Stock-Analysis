"""
Tushare 个股日K线数据同步模块

使用 Tushare Pro 接口批量获取所有股票日K数据
优势：一次请求获取 5000+ 只股票数据，无需逐只请求
"""

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import tushare as ts

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error
from a_stock.db.repository import StockDailyRepository
from a_stock.utils.config import get_tushare_token


class TushareStockDailySync:
    """Tushare 股票日K数据同步器"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化 Tushare 同步器
        
        Args:
            token: Tushare Pro token，如果不传则尝试从环境变量获取
        """
        if token:
            self.pro = ts.pro_api(token)
        else:
            self.pro = ts.pro_api()
        
        log_debug("Tushare 同步器初始化完成")
    
    def fetch_daily_data(self, trade_date: str) -> List[Dict]:
        """
        批量获取某交易日的所有股票日K数据
        
        Args:
            trade_date: 交易日期 (YYYY-MM-DD 或 YYYYMMDD)
            
        Returns:
            日K数据列表，每只股票的日K数据
        """
        # 统一日期格式为 YYYYMMDD
        date_str = trade_date.replace('-', '')
        
        try:
            log_info(f"从 Tushare 获取 {trade_date} 的日K数据...")
            
            # 调用 Tushare Pro 的 daily 接口，一次获取所有股票
            df = self.pro.daily(trade_date=date_str)
            
            if df is None or df.empty:
                log_error(f"Tushare 返回空数据: {trade_date}")
                return []
            
            log_info(f"Tushare 返回 {len(df)} 条数据")
            
            # 转换字段名以匹配我们的数据库 schema
            records = self._convert_to_records(df)
            
            return records
            
        except Exception as e:
            log_error(f"Tushare 获取数据失败: {e}")
            raise
    
    def _convert_to_records(self, df: pd.DataFrame) -> List[Dict]:
        """
        将 Tushare 数据转换为我们的标准格式
        
        Args:
            df: Tushare 返回的 DataFrame
            
        Returns:
            标准格式的记录列表
        """
        records = []
        
        # 从数据库获取股票名称映射
        stock_names = self._get_stock_names()
        
        for _, row in df.iterrows():
            # Tushare 的 ts_code 格式为 000001.SZ，需要转换为 000001
            ts_code = str(row.get('ts_code', ''))
            code = ts_code.split('.')[0] if '.' in ts_code else ts_code
            
            # Tushare 日期格式为 YYYYMMDD，转换为 YYYY-MM-DD
            trade_date = str(row.get('trade_date', ''))
            if len(trade_date) == 8:
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
            else:
                formatted_date = trade_date
            
            # 从 stock_info 获取股票名称
            name = stock_names.get(code, '')
            
            record = {
                'code': code,
                'name': name,  # 从 stock_info 表获取
                'date': formatted_date,
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': float(row.get('vol', 0)) * 100,  # Tushare 单位是手，转换为股
                'amount': float(row.get('amount', 0)) * 1000,  # Tushare 单位是千元，转换为元
                'change_pct': float(row.get('pct_chg', 0)),  # 涨跌幅百分比
                'turnover_rate': 0.0,  # Tushare daily 接口没有换手率，需要另外获取
            }
            records.append(record)
        
        return records
    
    def _get_stock_names(self) -> Dict[str, str]:
        """
        从数据库获取股票名称映射
        
        Returns:
            股票代码到名称的映射字典
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT code, name FROM stock_info")
            names = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            log_debug(f"从 stock_info 获取了 {len(names)} 只股票名称")
            return names
        except Exception as e:
            log_error(f"获取股票名称失败: {e}")
            return {}
    
    def sync_stock_daily(self, date: str = None) -> Dict[str, int]:
        """
        同步指定日期的所有股票日K数据
        
        Args:
            date: 指定日期 (YYYY-MM-DD)，不传则使用今天
            
        Returns:
            同步结果统计
        """
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        
        log_info(f"开始 Tushare 批量同步日K数据: {target_date}")
        
        # 获取数据
        records = self.fetch_daily_data(target_date)
        
        if not records:
            log_error("没有获取到数据")
            return {'total': 0, 'success': 0, 'failed': 0}
        
        # 保存到数据库
        repository = StockDailyRepository()
        
        try:
            # 批量保存
            repository.save_batch(records)
            log_info(f"成功保存 {len(records)} 条记录")
            
            return {
                'total': len(records),
                'success': len(records),
                'failed': 0
            }
            
        except Exception as e:
            log_error(f"保存数据失败: {e}")
            return {
                'total': len(records),
                'success': 0,
                'failed': len(records)
            }


def sync_stock_daily_tushare(date: str = None, token: Optional[str] = None) -> Dict[str, int]:
    """
    使用 Tushare 同步股票日K数据的便捷函数
    
    Args:
        date: 指定日期 (YYYY-MM-DD)
        token: Tushare Pro token，不传则从配置读取
        
    Returns:
        同步结果统计
    """
    # 从配置读取 token（支持环境变量和配置文件）
    if token is None:
        token = get_tushare_token()
        if not token:
            raise ValueError(
                "未找到 Tushare Token，请通过以下方式配置：\n"
                "1. 设置环境变量: export TUSHARE_TOKEN='your_token'\n"
                "2. 在 config/config.yaml 中配置 data_source.tushare.token"
            )
    
    syncer = TushareStockDailySync(token=token)
    return syncer.sync_stock_daily(date)


if __name__ == "__main__":
    # 测试
    import argparse
    
    parser = argparse.ArgumentParser(description="使用 Tushare 同步股票日K数据")
    parser.add_argument("--date", help="指定日期 (YYYY-MM-DD)")
    parser.add_argument("--token", help="Tushare Pro token")
    
    args = parser.parse_args()
    
    result = sync_stock_daily_tushare(date=args.date, token=args.token)
    print(f"同步结果: {result}")
