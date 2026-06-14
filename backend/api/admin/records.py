"""
admin 全量记录查询
==================

GET /api/admin/records?user_id=&page=&page_size=
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.records import RecordItem, RecordListOut  # 复用
from backend.db.base import get_db
from backend.db.models import ClassifyRecord, User
from backend.security.deps import require_admin

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/records", response_model=RecordListOut)
def list_all_records(
    user_id: int | None = Query(None, description="按 user_id 过滤"),
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RecordListOut:
    """admin 看全量记录（可按 user_id 过滤）。"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 20
    q = db.query(ClassifyRecord)
    if user_id is not None:
        q = q.filter(ClassifyRecord.user_id == user_id)
    total = q.count()
    rows = (
        q.order_by(ClassifyRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return RecordListOut(
        items=[RecordItem.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )
