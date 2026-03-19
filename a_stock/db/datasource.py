"""
数据源管理器 (DataSource Manager)

实现多数据源降级机制，支持：
- 多数据源优先级配置
- 自动降级和重试
- 失败记录和恢复
- 数据源健康状态监控
"""

from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Any
from enum import Enum
import time

from a_stock.db.cache import log_debug, log_info, log_error


class DataSourceStatus(Enum):
    """数据源状态"""
    HEALTHY = "healthy"           # 健康
    DEGRADED = "degraded"         # 降级（偶尔失败）
    UNHEALTHY = "unhealthy"       # 不健康（频繁失败）
    DISABLED = "disabled"         # 禁用


class DataSource:
    """数据源定义"""
    
    def __init__(
        self,
        name: str,
        fetch_func: Callable,
        priority: int = 0,
        enabled: bool = True,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        """
        初始化数据源
        
        Args:
            name: 数据源名称
            fetch_func: 数据获取函数
            priority: 优先级（数字越小优先级越高）
            enabled: 是否启用
            retry_count: 重试次数
            retry_delay: 重试延迟（秒）
            timeout: 超时时间（秒）
        """
        self.name = name
        self.fetch_func = fetch_func
        self.priority = priority
        self.enabled = enabled
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.timeout = timeout
        
        # 统计信息
        self.success_count = 0
        self.failure_count = 0
        self.last_success_time: Optional[datetime] = None
        self.last_failure_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total
    
    @property
    def status(self) -> DataSourceStatus:
        """数据源状态"""
        if not self.enabled:
            return DataSourceStatus.DISABLED
        
        # 最近 10 次请求中失败次数超过 7 次，标记为不健康
        recent_requests = min(self.success_count + self.failure_count, 10)
        if recent_requests >= 10 and self.failure_count / recent_requests > 0.7:
            return DataSourceStatus.UNHEALTHY
        
        # 成功率低于 80%，标记为降级
        if self.success_rate < 0.8:
            return DataSourceStatus.DEGRADED
        
        return DataSourceStatus.HEALTHY
    
    def record_success(self):
        """记录成功"""
        self.success_count += 1
        self.last_success_time = datetime.now()
    
    def record_failure(self, error: str):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.last_error = error


class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self):
        """初始化数据源管理器"""
        self.sources: Dict[str, List[DataSource]] = {}
    
    def register(self, data_type: str, source: DataSource):
        """
        注册数据源
        
        Args:
            data_type: 数据类型（如 "stock_daily", "stock_info"）
            source: 数据源对象
        """
        if data_type not in self.sources:
            self.sources[data_type] = []
        
        self.sources[data_type].append(source)
        # 按优先级排序
        self.sources[data_type].sort(key=lambda s: s.priority)
        
        log_debug(f"已注册数据源: {data_type}/{source.name} (优先级: {source.priority})")
    
    def fetch(
        self,
        data_type: str,
        *args,
        **kwargs
    ) -> Any:
        """
        从数据源获取数据（自动降级）
        
        Args:
            data_type: 数据类型
            *args: 传递给 fetch_func 的位置参数
            **kwargs: 传递给 fetch_func 的关键字参数
            
        Returns:
            获取的数据
            
        Raises:
            Exception: 所有数据源都失败时抛出最后一个错误
        """
        if data_type not in self.sources:
            raise ValueError(f"未找到数据类型: {data_type}")
        
        sources = self.sources[data_type]
        last_error = None
        
        for source in sources:
            if not source.enabled or source.status == DataSourceStatus.DISABLED:
                continue
            
            log_debug(f"尝试从数据源 {source.name} 获取 {data_type} 数据...")
            
            # 重试机制
            for attempt in range(source.retry_count):
                try:
                    data = source.fetch_func(*args, **kwargs)
                    source.record_success()
                    log_debug(f"从 {source.name} 获取 {data_type} 数据成功")
                    return data
                except Exception as e:
                    error_msg = str(e)
                    log_debug(f"从 {source.name} 获取 {data_type} 数据失败 (尝试 {attempt + 1}/{source.retry_count}): {error_msg}")
                    
                    if attempt < source.retry_count - 1:
                        time.sleep(source.retry_delay)
                    else:
                        source.record_failure(error_msg)
                        last_error = e
        
        # 所有数据源都失败
        error_msg = f"所有数据源都无法获取 {data_type} 数据"
        if last_error:
            error_msg += f"，最后错误: {last_error}"
        raise Exception(error_msg)
    
    def get_source_status(self, data_type: str) -> Dict[str, DataSourceStatus]:
        """
        获取指定数据类型的所有数据源状态
        
        Args:
            data_type: 数据类型
            
        Returns:
            {source_name: status}
        """
        if data_type not in self.sources:
            return {}
        
        return {
            source.name: source.status
            for source in self.sources[data_type]
        }
    
    def disable_source(self, data_type: str, source_name: str):
        """
        禁用指定数据源
        
        Args:
            data_type: 数据类型
            source_name: 数据源名称
        """
        if data_type not in self.sources:
            return
        
        for source in self.sources[data_type]:
            if source.name == source_name:
                source.enabled = False
                log_info(f"已禁用数据源: {data_type}/{source_name}")
                break
    
    def enable_source(self, data_type: str, source_name: str):
        """
        启用指定数据源
        
        Args:
            data_type: 数据类型
            source_name: 数据源名称
        """
        if data_type not in self.sources:
            return
        
        for source in self.sources[data_type]:
            if source.name == source_name:
                source.enabled = True
                source.failure_count = 0  # 重置失败计数
                log_info(f"已启用数据源: {data_type}/{source_name}")
                break
    
    def get_statistics(self, data_type: str = None) -> Dict:
        """
        获取数据源统计信息
        
        Args:
            data_type: 数据类型（可选，不传则返回所有）
            
        Returns:
            统计信息字典
        """
        if data_type:
            types = [data_type]
        else:
            types = list(self.sources.keys())
        
        stats = {}
        for dtype in types:
            if dtype not in self.sources:
                continue
            
            stats[dtype] = []
            for source in self.sources[dtype]:
                stats[dtype].append({
                    "name": source.name,
                    "priority": source.priority,
                    "status": source.status.value,
                    "enabled": source.enabled,
                    "success_count": source.success_count,
                    "failure_count": source.failure_count,
                    "success_rate": f"{source.success_rate:.2%}",
                    "last_success": source.last_success_time.isoformat() if source.last_success_time else None,
                    "last_failure": source.last_failure_time.isoformat() if source.last_failure_time else None,
                    "last_error": source.last_error,
                })
        
        return stats


# 全局数据源管理器实例
_manager: Optional[DataSourceManager] = None


def get_manager() -> DataSourceManager:
    """获取全局数据源管理器实例"""
    global _manager
    if _manager is None:
        _manager = DataSourceManager()
    return _manager


# 导出
__all__ = [
    "DataSource",
    "DataSourceManager",
    "DataSourceStatus",
    "get_manager",
]
