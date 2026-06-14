"""
统计接口
========

GET /api/stats
- 返回近 7 天分类计数（内存维护，不接数据库）

POST /api/stats/record
- 记录一次分类结果（来自 /api/classify 后的客户端回调）
"""
from __future__ import annotations

import time
from collections import Counter, deque
from typing import Deque

from fastapi import APIRouter, Body
from pydantic import BaseModel

router = APIRouter()

# 内存环形缓冲：最近 7 天 × 每秒 1 条 ≈ 604800 条
_RECORDS: Deque[dict] = deque(maxlen=604800)
_START_TS = time.time()


class RecordItem(BaseModel):
    label: str
    score: float
    ts: float | None = None


@router.get("/stats")
def get_stats() -> dict:
    """返回过去 7 天的累计分类计数与时间窗。"""
    now = time.time()
    window_s = 7 * 24 * 3600
    recent = [r for r in _RECORDS if now - r["ts"] < window_s]
    counter = Counter(r["label"] for r in recent)
    return {
        "window_hours": 7 * 24,
        "total": len(recent),
        "counts": dict(counter),
        "server_uptime_s": int(now - _START_TS),
    }


@router.post("/stats/record")
def add_record(item: RecordItem) -> dict:
    """记录一次分类结果。"""
    _RECORDS.append({"label": item.label, "score": item.score, "ts": item.ts or time.time()})
    return {"ok": True, "total": len(_RECORDS)}
