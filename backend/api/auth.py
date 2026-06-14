"""
Auth 接口
=========

- POST /api/auth/register  注册
- POST /api/auth/login     登录
- POST /api/auth/refresh   刷新 access_token
- POST /api/auth/logout    把当前 access token 写黑名单
- GET  /api/auth/me        返回当前用户
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import User
from backend.schemas.auth import (
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserOut,
)
from backend.security.jwt import (
    add_to_blacklist,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_blacklisted,
)
from backend.security.password import hash_password, verify_password
from backend.security.deps import get_current_user

log = logging.getLogger(__name__)
router = APIRouter()


# ==================== 工具 ====================
def _build_token_pair(user: User) -> dict:
    """用 user 信息签发 access + refresh。"""
    access = create_access_token(sub=user.id, role=user.role)
    refresh = create_refresh_token(sub=user.id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
    }


# ==================== 注册 ====================
@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    """注册。首个用户自动获得 admin 角色。"""
    # 唯一性校验
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="username already exists")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="email already exists")

    # 首个注册者 = admin，其余 = user
    is_first = db.query(User).count() == 0
    role = "admin" if is_first else "user"

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("registered user id=%s username=%s role=%s", user.id, user.username, role)
    return TokenOut(**_build_token_pair(user))


# ==================== 登录 ====================
@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    """登录。返回双 token。"""
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is disabled")
    return TokenOut(**_build_token_pair(user))


# ==================== 刷新 ====================
@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> TokenOut:
    """用 refresh_token 换新的双 token。"""
    data = decode_token(payload.refresh_token)
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    jti = data.get("jti")
    if jti and is_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    try:
        user_id = int(data["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return TokenOut(**_build_token_pair(user))


# ==================== 登出 ====================
@router.post("/logout")
def logout(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> dict:
    """把当前 Authorization 头的 access token 写黑名单。"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = parts[1]

    payload = decode_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or exp is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    add_to_blacklist(db, jti, exp)
    return {"ok": True}


# ==================== 当前用户信息 ====================
@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
