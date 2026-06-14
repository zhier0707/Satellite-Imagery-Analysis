"""
数据库引擎与会话工厂
====================

- SQLite 文件路径：`./data/app.db`（相对进程工作目录）
- 单线程 check_same_thread=False 以兼容 FastAPI 的线程池
- 通过 `get_db()` 依赖为每个请求提供独立 Session
"""
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# ==================== 路径与目录 ====================
DATA_DIR = os.environ.get("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "app.db")
SQLALCHEMY_DATABASE_URL = os.environ.get(
    "SQLALCHEMY_DATABASE_URL", f"sqlite:///{DB_PATH}"
)

# ==================== 引擎与 Session 工厂 ====================
# SQLite 需要显式关闭多线程检查；其他数据库可忽略
connect_args: dict = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine: Engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# 统一基类，所有 ORM 模型继承此
Base = declarative_base()


# ==================== FastAPI 依赖 ====================
def get_db() -> Generator[Session, None, None]:
    """每个请求一个 Session，请求结束自动 close。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
