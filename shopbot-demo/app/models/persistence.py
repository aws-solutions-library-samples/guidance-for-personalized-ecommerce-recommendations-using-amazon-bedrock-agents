"""持久化存储实现"""
import json
import asyncio
import aiosqlite
from pathlib import Path
from typing import Optional
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


# 全局 checkpointer 实例（延迟初始化）
_checkpointer_instance = None
_checkpointer_lock = asyncio.Lock()


async def create_checkpointer() -> AsyncSqliteSaver:
    """
    创建持久化的 Checkpointer（异步 SQLite）

    功能：
    - 存储会话级别的 State 快照
    - 自动创建 data/shopbot.db
    - 支持事务，数据安全
    - 异步操作，适用于 FastAPI
    - 使用单例模式避免重复创建连接

    Returns:
        AsyncSqliteSaver: 异步 SQLite 持久化 Checkpointer
    """
    global _checkpointer_instance

    # 双重检查锁定（DCL）
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    async with _checkpointer_lock:
        # 再次检查（可能在等待锁时已被其他协程创建）
        if _checkpointer_instance is not None:
            return _checkpointer_instance

        # 创建数据库文件路径
        db_path = Path("data/shopbot.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建异步 SQLite 连接
        conn = await aiosqlite.connect(str(db_path))

        # 创建 AsyncSqliteSaver 实例
        checkpointer = AsyncSqliteSaver(conn)

        # 初始化表结构
        await checkpointer.setup()

        _checkpointer_instance = checkpointer
        return checkpointer


class FileStore:
    """
    基于文件的 Store 实现（JSON 存储）
    
    功能：
    - 存储跨会话的长期数据
    - 用户偏好、会话摘要等
    - 文件路径：data/store/
    """
    
    def __init__(self, base_path: str = "data/store"):
        """
        初始化 FileStore
        
        Args:
            base_path: 基础路径，默认 "data/store"
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, namespace: tuple) -> Path:
        """
        根据 namespace 生成文件路径
        
        Args:
            namespace: 命名空间元组，如 ("user_preferences", "user_001")
            
        Returns:
            Path: 文件路径，如 data/store/user_preferences/user_001/data.json
        """
        return self.base_path / "/".join(namespace) / "data.json"
    
    async def aput(self, namespace: tuple, key: str, value: dict) -> None:
        """
        保存数据
        
        Args:
            namespace: 命名空间元组
            key: 数据键
            value: 数据值（字典）
        """
        file_path = self._get_file_path(namespace)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 读取现有数据
        data = {}
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        # 更新数据
        data[key] = value
        
        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def aget(self, namespace: tuple, key: str) -> Optional[dict]:
        """
        获取数据
        
        Args:
            namespace: 命名空间元组
            key: 数据键
            
        Returns:
            Optional[dict]: 数据值，不存在则返回 None
        """
        file_path = self._get_file_path(namespace)
        if not file_path.exists():
            return None
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return data.get(key)
    
    async def asearch(self, namespace_prefix: tuple) -> list[dict]:
        """
        搜索数据
        
        Args:
            namespace_prefix: 命名空间前缀
            
        Returns:
            list[dict]: 匹配的数据列表
        """
        results = []
        search_path = self.base_path / "/".join(namespace_prefix)
        
        if not search_path.exists():
            return results
        
        # 递归查找所有 data.json 文件
        for json_file in search_path.rglob("data.json"):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for key, value in data.items():
                results.append({
                    "namespace": namespace_prefix,
                    "key": key,
                    "value": value
                })
        
        return results
