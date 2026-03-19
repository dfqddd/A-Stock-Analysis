"""数据库模块"""

from .cache import DB_PATH, get_connection, init_db

__all__ = ["DB_PATH", "get_connection", "init_db"]
