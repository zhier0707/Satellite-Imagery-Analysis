"""
Auth 相关请求/响应模型
======================
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ==================== 入参 ====================
class RegisterIn(BaseModel):
    """注册请求体。"""

    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginIn(BaseModel):
    """登录请求体。"""

    username: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshIn(BaseModel):
    """刷新 access_token 请求体。"""

    refresh_token: str


# ==================== 出参 ====================
class UserOut(BaseModel):
    """当前用户摘要。"""

    id: int
    username: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True  # 支持 ORM 实例 → schema 转换


class TokenOut(BaseModel):
    """双 token 返回。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
