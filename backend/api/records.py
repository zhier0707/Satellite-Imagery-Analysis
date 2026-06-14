"""
分类记录查询接口
================

- GET  /api/records          分页查询（普通用户只看自己；admin 看全部）
- GET  /api/records/{id}     单条详情（含 top5 反序列化）
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import ClassifyRecord, User
from backend.security.deps import get_current_user

log = logging.getLogger(__name__)
router = APIRouter()


# ==================== 响应模型 ====================
class RecordItem(BaseModel):
    id: int
    top1_label: str
    top1_score: float
    image_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecordListOut(BaseModel):
    items: list[RecordItem]
    total: int
    page: int
    page_size: int


class RecordDetailOut(RecordItem):
    user_id: int
    top5: list[dict]
    duration_ms: int


# ==================== 列表 ====================
@router.get("/records", response_model=RecordListOut)
def list_records(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordListOut:
    """分页查询分类记录。"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 20

    q = db.query(ClassifyRecord)
    if current_user.role != "admin":
        q = q.filter(ClassifyRecord.user_id == current_user.id)
    total = q.count()
    rows = (
        q.order_by(ClassifyRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        RecordItem(
            id=r.id,
            top1_label=r.top1_label,
            top1_score=r.top1_score,
            image_path=r.image_path,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return RecordListOut(items=items, total=total, page=page, page_size=page_size)


# ==================== 详情 ====================
@router.get("/records/{record_id}", response_model=RecordDetailOut)
def get_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordDetailOut:
    """单条记录详情。"""
    r: Optional[ClassifyRecord] = (
        db.query(ClassifyRecord).filter(ClassifyRecord.id == record_id).first()
    )
    if r is None:
        raise HTTPException(status_code=404, detail="Record not found")
    if current_user.role != "admin" and r.user_id != current_user.id:
        # 非本人 + 非 admin → 视作不存在（避免泄漏）
        raise HTTPException(status_code=404, detail="Record not found")

    try:
        top5 = json.loads(r.top5_json) if r.top5_json else []
    except (TypeError, ValueError):
        log.warning("record %s has invalid top5_json, returning []", r.id)
        top5 = []

    return RecordDetailOut(
        id=r.id,
        user_id=r.user_id,
        top1_label=r.top1_label,
        top1_score=r.top1_score,
        image_path=r.image_path,
        top5=top5,
        duration_ms=r.duration_ms,
        created_at=r.created_at,
    )
