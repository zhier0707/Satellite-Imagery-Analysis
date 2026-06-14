"""
鉴权依赖
========

- `get_current_user`：从 Authorization 头解析 Bearer token，校验签名/过期/黑名单，返回 User 对象
- `require_admin`：在 get_current_user 之上再校验 role=admin
- `oauth2_scheme`：FastAPI OpenAPI 文档用，tokenUrl 指向 /api/auth/login
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import User
from backend.security.jwt import decode_token, is_blacklisted

# tokenUrl 供 Swagger UI "Authorize" 按钮使用；与实际登录端点保持一致
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1]


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer token → 校验 → 查表 → 返回 User。失败抛 401。"""
    token = _extract_bearer(authorization)
    payload = decode_token(token)

    jti = payload.get("jti")
    if jti and is_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is disabled")
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """在 get_current_user 之上校验角色。失败抛 403。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user
