
"""
统一配置管理模块

提供统一的配置读取接口，支持：
1. 从 config.yaml 读取配置
2. 环境变量覆盖（优先级更高）
3. 默认值处理
"""

import os
import re
from typing import Any, Dict, Optional

import yaml


class ConfigManager:
    """配置管理器"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._loaded:
            self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        # 查找配置文件路径
        config_paths = [
            # 项目根目录
            os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.yaml"),
            # 当前工作目录
            os.path.join(os.getcwd(), "config", "config.yaml"),
            # 绝对路径
            "/Users/dfq/.openclaw/workspace-hanli/skills/a-stock-analysis/config/config.yaml",
        ]
        
        config_path = None
        for path in config_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if config_path:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
                self._loaded = True
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                self._config = {}
        else:
            print("未找到配置文件，使用默认配置")
            self._config = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的嵌套键
        
        Args:
            key: 配置键，如 "dingtalk.webhook" 或 "database.type"
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        # 检查环境变量（支持 TUSHARE_TOKEN 等）
        env_key = key.upper().replace(".", "_")
        env_value = os.environ.get(env_key)
        if env_value:
            return env_value
        
        # 解析嵌套键
        keys = key.split(".")
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            
            # 处理 ${ENV_VAR} 格式的环境变量引用
            if isinstance(value, str):
                value = self._resolve_env_vars(value)
            
            return value
        except (KeyError, TypeError):
            return default
    
    def _resolve_env_vars(self, value: str) -> str:
        """解析字符串中的环境变量引用"""
        pattern = r'\$\{([^}]+)\}'
        
        def replace_env_var(match):
            env_var = match.group(1)
            return os.environ.get(env_var, match.group(0))
        
        return re.sub(pattern, replace_env_var, value)
    
    def get_dingtalk_config(self) -> Dict[str, Any]:
        """获取钉钉配置"""
        return self._config.get("dingtalk", {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self._config.get("database", {})
    
    def get_tushare_token(self) -> Optional[str]:
        """
        获取 Tushare Token
        
        优先级：
        1. 环境变量 TUSHARE_TOKEN
        2. 配置文件 data_source.tushare.token
        3. 返回 None
        """
        # 环境变量优先级最高
        token = os.environ.get("TUSHARE_TOKEN")
        if token:
            return token
        
        # 从配置文件获取
        tushare_config = self._config.get("data_source", {}).get("tushare", {})
        token = tushare_config.get("token")
        
        # 解析环境变量引用
        if isinstance(token, str) and token.startswith("${"):
            token = self._resolve_env_vars(token)
            # 如果解析后还是原样，说明环境变量不存在
            if token.startswith("${"):
                return None
        
        return token
    
    def reload(self):
        """重新加载配置"""
        self._loaded = False
        self._load_config()


# 全局配置管理器实例
config = ConfigManager()


def get_config(key: str, default: Any = None) -> Any:
    """
    获取配置值的便捷函数
    
    Args:
        key: 配置键，支持点号分隔
        default: 默认值
        
    Returns:
        配置值
    """
    return config.get(key, default)


def get_tushare_token() -> Optional[str]:
    """获取 Tushare Token 的便捷函数"""
    return config.get_tushare_token()


def get_dingtalk_webhook() -> Optional[str]:
    """获取钉钉 Webhook 的便捷函数"""
    return config.get("dingtalk.webhook")
