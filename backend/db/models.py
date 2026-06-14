"""
ORM 模型定义
============

6 张表：
1. User                - 用户
2. ClassifyRecord      - 单次分类记录
3. ChangeJob           - 时相变化检测任务
4. ExportJob           - 报表导出任务
5. TrainingJob         - 训练任务
6. TokenBlacklist      - JWT 撤销黑名单

约定：
- 时间字段统一用 `created_at` / `finished_at`，类型 DateTime
- 整型主键自增
- `__tablename__` 显式声明，与数据库中实际表名一致
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.db.base import Base


# ==================== 工具：通用时间戳默认值 ====================
def _now() -> datetime:
    return datetime.utcnow()


# ==================== User ====================
class User(Base):
    """平台用户。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_now)

    # 关系
    classify_records = relationship("ClassifyRecord", back_populates="user", cascade="all,delete-orphan")
    change_jobs = relationship("ChangeJob", back_populates="user", cascade="all,delete-orphan")
    export_jobs = relationship("ExportJob", back_populates="user", cascade="all,delete-orphan")
    training_jobs = relationship("TrainingJob", back_populates="user", cascade="all,delete-orphan")

    def __repr__(self) -> str:  # noqa: D401
        return f"<User id={self.id} username={self.username} role={self.role}>"


# ==================== ClassifyRecord ====================
class ClassifyRecord(Base):
    """单次分类推理结果。"""

    __tablename__ = "classify_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    image_path = Column(String(255), nullable=False)
    top1_label = Column(String(64), nullable=False)
    top1_score = Column(Float, nullable=False)
    top5_json = Column(Text, nullable=False)  # JSON 字符串
    duration_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=_now, index=True)

    user = relationship("User", back_populates="classify_records")

    __table_args__ = (
        Index("ix_classify_records_user_created", "user_id", "created_at"),
    )


# ==================== ChangeJob ====================
class ChangeJob(Base):
    """时相变化检测任务。"""

    __tablename__ = "change_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    image_a_path = Column(String(255), nullable=False)
    image_b_path = Column(String(255), nullable=False)
    top1_a = Column(String(64), nullable=False)
    top1_b = Column(String(64), nullable=False)
    changes_json = Column(Text, nullable=False, default="[]")
    status = Column(String(16), nullable=False, default="completed")
    created_at = Column(DateTime, nullable=False, default=_now, index=True)

    user = relationship("User", back_populates="change_jobs")

    __table_args__ = (
        Index("ix_change_jobs_user_created", "user_id", "created_at"),
    )


# ==================== ExportJob ====================
class ExportJob(Base):
    """报表导出任务。"""

    __tablename__ = "export_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(16), nullable=False)  # pdf / excel / csv
    params_json = Column(Text, nullable=False, default="{}")
    output_path = Column(String(512), nullable=True)
    status = Column(String(16), nullable=False, default="queued")  # queued/running/completed/failed
    created_at = Column(DateTime, nullable=False, default=_now, index=True)

    user = relationship("User", back_populates="export_jobs")

    __table_args__ = (
        Index("ix_export_jobs_user_created", "user_id", "created_at"),
    )


# ==================== TrainingJob ====================
class TrainingJob(Base):
    """训练任务。"""

    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stage = Column(String(32), nullable=False, default="full")
    epochs = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="queued")
    last_checkpoint_path = Column(String(512), nullable=True)
    best_val_acc = Column(Float, nullable=True)
    metrics_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now, index=True)

    user = relationship("User", back_populates="training_jobs")

    __table_args__ = (
        Index("ix_training_jobs_user_created", "user_id", "created_at"),
    )


# ==================== TokenBlacklist ====================
class TokenBlacklist(Base):
    """JWT 撤销黑名单。"""

    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    exp = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)
