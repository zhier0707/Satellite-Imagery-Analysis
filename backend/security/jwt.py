"""
JWT 工具与黑名单
================

- 算法：HS256
- SECRET_KEY：优先读环境变量 `JWT_SECRET`，否则首次启动时生成 32 字节随机串持久化到 `data/.jwt_secret`
- token 类型：access（15min）/ refresh（7d），用 payload 的 `type` 字段区分
- 黑名单：写入 `token_blacklist` 表，decode 时先查黑名单

依赖：python-jose[cryptography]==3.3.0
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.db.base import DATA_DIR
from backend.db.models import TokenBlacklist

# ==================== 密钥管理 ====================
ALGORITHM = "HS256"
_ACCESS_TTL_S = 15 * 60           # 15 分钟
_REFRESH_TTL_S = 7 * 24 * 60 * 60  # 7 天

_JWT_SECRET_FILE = Path(DATA_DIR) / ".jwt_secret"


def _load_or_create_secret() -> str:
    """读取或生成 JWT 签名密钥。启动时一次性调用。"""
    env = os.environ.get("JWT_SECRET")
    if env:
        return env
    if _JWT_SECRET_FILE.is_file():
        return _JWT_SECRET_FILE.read_text(encoding="utf-8").strip()
    # 首次启动：生成并落盘
    os.makedirs(DATA_DIR, exist_ok=True)
    secret = secrets.token_urlsafe(32)
    _JWT_SECRET_FILE.write_text(secret, encoding="utf-8")
    try:
        # 限制权限（Windows 最佳努力；失败不影响功能）
        os.chmod(_JWT_SECRET_FILE, 0o600)
    except OSError:
        pass
    return secret


SECRET_KEY: str = _load_or_create_secret()


# ==================== Token 工厂 ====================
def _now_ts() -> int:
    return int(time.time())


def create_access_token(
    sub: str | int,
    role: str,
    extra_claims: Optional[dict] = None,
) -> str:
    """签发访问令牌（TTL 15min）。"""
    payload: dict = {
        "sub": str(sub),
        "role": role,
        "type": "access",
        "jti": uuid4().hex,
        "iat": _now_ts(),
        "exp": _now_ts() + _ACCESS_TTL_S,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(sub: str | int) -> str:
    """签发刷新令牌（TTL 7d）。"""
    payload = {
        "sub": str(sub),
        "type": "refresh",
        "jti": uuid4().hex,
        "iat": _now_ts(),
        "exp": _now_ts() + _REFRESH_TTL_S,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ==================== 校验与解码 ====================
def decode_token(token: str) -> dict:
    """校验 token 的签名/过期/格式。失败抛 401。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if "sub" not in payload or "type" not in payload or "jti" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# ==================== 黑名单 ====================
def add_to_blacklist(db: Session, jti: str, exp: float) -> None:
    """把已签发的 jti 写入黑名单。"""
    # 若已存在则忽略（幂等）
    exists = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
    if exists:
        return
    db.add(TokenBlacklist(jti=jti, exp=float(exp)))
    db.commit()


def is_blacklisted(db: Session, jti: str) -> bool:
    """查 jti 是否已被撤销。"""
    return (
        db.query(TokenBlacklist)
        .filter(TokenBlacklist.jti == jti)
        .first()
        is not None
    )
