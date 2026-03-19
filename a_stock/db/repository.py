"""
统一数据访问层 (Repository Layer)

封装所有数据库表的 CRUD 操作，提供统一的数据访问接口。
支持批量插入、更新、查询等操作，避免代码重复。
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
import sqlite3

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_error


class BaseRepository:
    """基础 Repository 类，提供通用的数据库操作方法"""
    
    def __init__(self, table_name: str, primary_keys: List[str]):
        """
        初始化 Repository
        
        Args:
            table_name: 表名
            primary_keys: 主键字段列表
        """
        self.table_name = table_name
        self.primary_keys = primary_keys
    
    def save(self, record: Dict, conflict_resolution: str = "REPLACE"):
        """
        保存单条记录（插入或更新）
        
        Args:
            record: 记录字典
            conflict_resolution: 冲突解决策略 (REPLACE, IGNORE, ABORT)
        """
        if not record:
            return
        
        conn = get_connection()
        try:
            cursor = conn.cursor()
            columns = list(record.keys())
            placeholders = ", ".join(["?" for _ in columns])
            column_names = ", ".join(columns)
            
            sql = f"""
                INSERT OR {conflict_resolution} INTO {self.table_name}
                ({column_names})
                VALUES ({placeholders})
            """
            
            cursor.execute(sql, [record.get(col) for col in columns])
            conn.commit()
            log_debug(f"已保存 1 条记录到 {self.table_name}")
        except Exception as e:
            log_error(f"保存记录到 {self.table_name} 失败: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def save_batch(self, records: List[Dict], conflict_resolution: str = "REPLACE"):
        """
        批量保存记录（插入或更新）
        
        Args:
            records: 记录列表
            conflict_resolution: 冲突解决策略 (REPLACE, IGNORE, ABORT)
        """
        if not records:
            return
        
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            # 获取所有列名（使用第一条记录的键）
            columns = list(records[0].keys())
            placeholders = ", ".join(["?" for _ in columns])
            column_names = ", ".join(columns)
            
            sql = f"""
                INSERT OR {conflict_resolution} INTO {self.table_name}
                ({column_names})
                VALUES ({placeholders})
            """
            
            # 批量执行
            for record in records:
                values = [record.get(col) for col in columns]
                cursor.execute(sql, values)
            
            conn.commit()
            log_debug(f"已保存 {len(records)} 条记录到 {self.table_name}")
        except Exception as e:
            log_error(f"批量保存记录到 {self.table_name} 失败: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def find_by_id(self, **kwargs) -> Optional[Dict]:
        """
        根据主键查询单条记录
        
        Args:
            **kwargs: 主键字段值
            
        Returns:
            记录字典或 None
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            conditions = " AND ".join([f"{key} = ?" for key in kwargs.keys()])
            sql = f"SELECT * FROM {self.table_name} WHERE {conditions}"
            
            cursor.execute(sql, list(kwargs.values()))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
    
    def find_all(self, limit: int = None, offset: int = None) -> List[Dict]:
        """
        查询所有记录
        
        Args:
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            记录列表
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            sql = f"SELECT * FROM {self.table_name}"
            if limit:
                sql += f" LIMIT {limit}"
            if offset:
                sql += f" OFFSET {offset}"
            
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def delete_by_id(self, **kwargs) -> bool:
        """
        根据主键删除记录
        
        Args:
            **kwargs: 主键字段值
            
        Returns:
            是否删除成功
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            conditions = " AND ".join([f"{key} = ?" for key in kwargs.keys()])
            sql = f"DELETE FROM {self.table_name} WHERE {conditions}"
            
            cursor.execute(sql, list(kwargs.values()))
            conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            log_error(f"删除记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


class StockDailyRepository(BaseRepository):
    """个股日K线数据 Repository"""
    
    def __init__(self):
        super().__init__("stock_daily", ["date", "code"])
    
    def find_by_code(self, code: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        根据股票代码查询日K数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            日K数据列表
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            sql = f"SELECT * FROM {self.table_name} WHERE code = ?"
            params = [code]
            
            if start_date:
                sql += " AND date >= ?"
                params.append(start_date)
            if end_date:
                sql += " AND date <= ?"
                params.append(end_date)
            
            sql += " ORDER BY date DESC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def find_latest_date(self, code: str) -> Optional[str]:
        """
        查询指定股票的最新日期
        
        Args:
            code: 股票代码
            
        Returns:
            最新日期字符串或 None
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT MAX(date) as latest_date FROM {self.table_name} WHERE code = ?",
                (code,)
            )
            row = cursor.fetchone()
            return row["latest_date"] if row else None
        finally:
            conn.close()


class StockInfoRepository(BaseRepository):
    """股票基础信息 Repository"""
    
    def __init__(self):
        super().__init__("stock_info", ["code"])
    
    def find_all_codes(self) -> List[str]:
        """获取所有股票代码"""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT code FROM {self.table_name}")
            rows = cursor.fetchall()
            return [row["code"] for row in rows]
        finally:
            conn.close()
    
    def update_batch(self, stocks: List[Dict], details: Dict[str, Dict] = None):
        """
        批量更新股票信息
        
        Args:
            stocks: 股票列表
            details: 股票详情字典 {code: detail_dict}
        """
        if not stocks:
            return
        
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            for stock in stocks:
                code = stock["code"]
                detail = details.get(code, {}) if details else {}
                
                # 检查是否已存在
                existing = cursor.execute(
                    f"SELECT code FROM {self.table_name} WHERE code = ?", (code,)
                ).fetchone()
                
                if existing:
                    # 更新
                    cursor.execute(
                        f"""UPDATE {self.table_name} SET 
                           name = ?, market = ?, industry = ?,
                           total_market_cap_yi = ?, pe_ratio = ?, pb_ratio = ?, updated_at = ?
                           WHERE code = ?""",
                        (
                            stock.get("name"),
                            stock.get("market"),
                            stock.get("industry"),
                            detail.get("total_market_cap_yi"),
                            detail.get("pe_ratio"),
                            detail.get("pb_ratio"),
                            now,
                            code,
                        ),
                    )
                else:
                    # 插入
                    cursor.execute(
                        f"""INSERT INTO {self.table_name} 
                           (code, name, market, industry, 
                            total_market_cap_yi, pe_ratio, pb_ratio, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            code,
                            stock.get("name"),
                            stock.get("market"),
                            stock.get("industry"),
                            detail.get("total_market_cap_yi"),
                            detail.get("pe_ratio"),
                            detail.get("pb_ratio"),
                            now,
                        ),
                    )
            
            conn.commit()
            log_debug(f"已更新 {len(stocks)} 条股票信息")
        except Exception as e:
            log_error(f"批量更新股票信息失败: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()


class DragonTigerRepository(BaseRepository):
    """龙虎榜数据 Repository"""
    
    def __init__(self):
        super().__init__("dragon_tiger", ["date", "code"])
    
    def find_by_date(self, date: str) -> List[Dict]:
        """
        根据日期查询龙虎榜数据
        
        Args:
            date: 日期字符串
            
        Returns:
            龙虎榜数据列表
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {self.table_name} WHERE date = ? ORDER BY net_buy_value DESC",
                (date,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


class StockHotRankingRepository(BaseRepository):
    """热门股票榜单 Repository"""
    
    def __init__(self):
        super().__init__("stock_hot_ranking", ["date", "code"])
    
    def find_by_date(self, date: str, limit: int = 100) -> List[Dict]:
        """
        根据日期查询热门股票榜单
        
        Args:
            date: 日期字符串
            limit: 限制数量
            
        Returns:
            热门股票榜单列表
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {self.table_name} WHERE date = ? ORDER BY total_rank ASC LIMIT ?",
                (date, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


class StockAbnormalMovementRepository(BaseRepository):
    """个股异动 Repository"""
    
    def __init__(self):
        super().__init__("stock_abnormal_movement", ["id"])
    
    def find_by_date_and_type(self, date: str, movement_type: str = None) -> List[Dict]:
        """
        根据日期和异动类型查询异动数据
        
        Args:
            date: 日期字符串
            movement_type: 异动类型 (price, amplitude, volume)
            
        Returns:
            异动数据列表
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            if movement_type:
                cursor.execute(
                    f"""SELECT * FROM {self.table_name} 
                        WHERE enter_date = ? AND movement_type = ?
                        ORDER BY risk_level DESC, code ASC""",
                    (date, movement_type)
                )
            else:
                cursor.execute(
                    f"""SELECT * FROM {self.table_name} 
                        WHERE enter_date = ?
                        ORDER BY movement_type, risk_level DESC, code ASC""",
                    (date,)
                )
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


# 导出所有 Repository 类
__all__ = [
    "BaseRepository",
    "StockDailyRepository",
    "StockInfoRepository",
    "DragonTigerRepository",
    "StockHotRankingRepository",
    "StockAbnormalMovementRepository",
]
