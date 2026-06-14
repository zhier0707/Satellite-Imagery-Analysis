"""
admin 用户管理
==============
- GET    /api/admin/users           列表
- PATCH  /api/admin/users/{id}      修改 role
- DELETE /api/admin/users/{id}      软删（is_active=false）
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import User
from backend.security.deps import require_admin

log = logging.getLogger(__name__)
router = APIRouter()


# ==================== Schemas ====================
class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserPatchIn(BaseModel):
    role: Optional[str] = Field(None, pattern="^(user|admin)$")
    is_active: Optional[bool] = None


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


# ==================== 路由 ====================
@router.get("/users", response_model=UserListOut)
def list_users(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserListOut:
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20
    q = db.query(User)
    total = q.count()
    rows = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return UserListOut(
        items=[UserOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: int,
    payload: UserPatchIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    u = db.query(User).filter(User.id == user_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    # 不允许 admin 把自己降级为 user（避免把自己锁出）
    if u.id == current_user.id and payload.role == "user":
        raise HTTPException(status_code=400, detail="cannot demote yourself")
    if payload.role is not None:
        u.role = payload.role
    if payload.is_active is not None:
        u.is_active = payload.is_active
    db.commit()
    db.refresh(u)
    log.info("[admin] user %s role=%s is_active=%s", u.id, u.role, u.is_active)
    return UserOut.model_validate(u)


@router.delete("/users/{user_id}", response_model=UserOut)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    """软删：is_active=false。"""
    u = db.query(User).filter(User.id == user_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == current_user.id:
        raise HTTPException(status_code=400, detail="cannot delete yourself")
    u.is_active = False
    db.commit()
    db.refresh(u)
    log.info("[admin] user %s 已软删（is_active=False）", u.id)
    return UserOut.model_validate(u)
