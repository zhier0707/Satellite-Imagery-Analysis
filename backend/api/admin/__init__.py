"""
admin 路由聚合
==============

把 training / users / records / converts 4 个子路由集中暴露。
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.admin import converts, records, training, users

router = APIRouter()
router.include_router(training.router, tags=["admin-training"])
router.include_router(users.router, tags=["admin-users"])
router.include_router(records.router, tags=["admin-records"])
router.include_router(converts.router, tags=["admin-converts"])
