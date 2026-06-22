"""
统计接口
========

GET /api/stats
- 返回近 7 天分类计数（内存维护，不接数据库）

POST /api/stats/record
- 记录一次分类结果（来自 /api/classify 后的客户端回调）

GET /api/stats/dashboard
- 大屏聚合数据（Phase B.2 新增）
- admin 看到全平台；user 仅看自己
- 30 秒进程内缓存（按 scope 维度）
- 失败时优雅降级到空数据
"""
from __future__ import annotations

import logging
import time
from collections import Counter, deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Tuple

from fastapi import APIRouter, Body, Depends, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.classes import EUROSAT_CLASSES
from backend.db.base import get_db
from backend.db.models import ClassifyRecord, User
from backend.schemas.stats import (
    DashboardStats,
    Kpi,
    LocationPoint,
    TimeSeriesPoint,
)
from backend.security.deps import get_current_user

log = logging.getLogger(__name__)
router = APIRouter()

# 内存环形缓冲：最近 7 天 × 每秒 1 条 ≈ 604800 条
_RECORDS: Deque[dict] = deque(maxlen=604800)
_START_TS = time.time()


# ==================== 兼容旧端点 ====================
class RecordItem(BaseModel):
    label: str
    score: float
    ts: float | None = None


@router.get("/stats")
def get_stats() -> dict:
    """返回过去 7 天的累计分类计数与时间窗。

    空 records 时 counts 自动补齐为 10 个 EuroSAT 类别全 0,
    与 ``/api/stats/dashboard`` 的 `_empty_dashboard` 行为对齐,
    让前端 StatsView 不会因为「空数据」误判为接口失败。
    """
    now = time.time()
    window_s = 7 * 24 * 3600
    recent = [r for r in _RECORDS if now - r["ts"] < window_s]
    counter = Counter(r["label"] for r in recent)
    # 兜底：10 个 EuroSAT 类别全 0(防空数据时前端误判)
    full_counts: Dict[str, int] = {label: 0 for label in EUROSAT_CLASSES}
    for label, cnt in counter.items():
        full_counts[label] = int(cnt)
    return {
        "window_hours": 7 * 24,
        "total": len(recent),
        "counts": full_counts,
        "server_uptime_s": int(now - _START_TS),
    }


@router.post("/stats/record")
def add_record(item: RecordItem) -> dict:
    """记录一次分类结果。"""
    _RECORDS.append({"label": item.label, "score": item.score, "ts": item.ts or time.time()})
    return {"ok": True, "total": len(_RECORDS)}


# ==================== Phase B.2: 大屏聚合数据 ====================
# 缓存配置：30 秒窗口
_DASHBOARD_TTL_S = 30
# 缓存 key 约定：
#   - admin 角色：所有 admin 共享一份（"全平台"语义相同）
#   - user 角色：按 user_id 隔离
DashboardCacheKey = Tuple[str, int]  # (role, scope_id)


def _cache_key(current_user: User) -> DashboardCacheKey:
    """根据角色生成缓存 key。admin 共用，user 各自一份。"""
    if current_user.role == "admin":
        return ("admin", 0)
    return ("user", current_user.id)


# 进程内缓存：(payload, expires_at)
_DASHBOARD_CACHE: Dict[DashboardCacheKey, Tuple[dict, float]] = {}


def _empty_dashboard() -> dict:
    """失败 fallback 与「空数据」统一返回。"""
    today = datetime.utcnow().date()
    return {
        "kpi": {
            "total_records": 0,
            "today_new": 0,
            "active_users": 0,
            "accuracy_avg": 0.0,
        },
        "classification_distribution": {label: 0 for label in EUROSAT_CLASSES},
        "time_series": [
            {"date": (today - timedelta(days=29 - i)).strftime("%Y-%m-%d"), "count": 0}
            for i in range(30)
        ],
        "top_locations": [],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _build_dashboard(db: Session, current_user: User) -> dict:
    """计算并组装大屏数据。失败时返回空数据。"""
    is_admin = current_user.role == "admin"
    # ==================== 基线查询：构造 scope 过滤 ====================
    base_q = db.query(ClassifyRecord)
    if not is_admin:
        base_q = base_q.filter(ClassifyRecord.user_id == current_user.id)

    # ==================== KPI ====================
    total_records = base_q.count() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = (
        base_q.filter(ClassifyRecord.created_at >= today_start).count() or 0
    )

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    active_users = (
        base_q.filter(ClassifyRecord.created_at >= seven_days_ago)
        .with_entities(func.count(func.distinct(ClassifyRecord.user_id)))
        .scalar()
        or 0
    )

    avg_raw = base_q.with_entities(func.avg(ClassifyRecord.top1_score)).scalar()
    accuracy_avg = round(float(avg_raw), 4) if avg_raw is not None else 0.0

    kpi = Kpi(
        total_records=int(total_records),
        today_new=int(today_new),
        active_users=int(active_users),
        accuracy_avg=accuracy_avg,
    )

    # ==================== 分类分布（10 个固定 label，缺则补 0）====================
    dist_rows = (
        base_q.with_entities(
            ClassifyRecord.top1_label, func.count(ClassifyRecord.id)
        )
        .group_by(ClassifyRecord.top1_label)
        .all()
    )
    raw_dist: Dict[str, int] = {label: 0 for label in EUROSAT_CLASSES}
    for label, cnt in dist_rows:
        if label in raw_dist:
            raw_dist[label] = int(cnt)
        else:
            # 兜底：未来若出现未登记的 label，也保留
            raw_dist[label] = int(cnt)

    # ==================== 时间序列：最近 30 天（升序），无数据日补 0 ====================
    # 一次 group by 取所有数据，再用 Python 补 0
    ts_rows = (
        base_q.filter(ClassifyRecord.created_at >= datetime.utcnow() - timedelta(days=30))
        .with_entities(
            func.date(ClassifyRecord.created_at).label("d"),
            func.count(ClassifyRecord.id),
        )
        .group_by("d")
        .all()
    )
    raw_count_by_date: Dict[str, int] = {
        (d.isoformat() if hasattr(d, "isoformat") else str(d)): int(cnt)
        for d, cnt in ts_rows
    }
    today = datetime.utcnow().date()
    time_series: List[TimeSeriesPoint] = []
    for i in range(30):
        d = today - timedelta(days=29 - i)
        key = d.strftime("%Y-%m-%d")
        time_series.append(
            TimeSeriesPoint(date=key, count=raw_count_by_date.get(key, 0))
        )

    # ==================== Top-50 分类点（无经纬度降级版）====================
    # 当前表无 lng/lat，按 spec 降级方案只返回 id/label/score
    top_rows = (
        base_q.order_by(ClassifyRecord.top1_score.desc())
        .limit(50)
        .with_entities(
            ClassifyRecord.id,
            ClassifyRecord.top1_label,
            ClassifyRecord.top1_score,
        )
        .all()
    )
    top_locations: List[LocationPoint] = [
        LocationPoint(id=int(rid), label=str(label), score=float(score))
        for rid, label, score in top_rows
    ]

    # ==================== 组装响应 ====================
    payload = DashboardStats(
        kpi=kpi,
        classification_distribution=raw_dist,
        time_series=time_series,
        top_locations=top_locations,
        generated_at=datetime.utcnow(),
    )
    # 转 dict 以便 Pydantic v2 序列化包含 datetime
    return payload.model_dump(mode="json")


@router.get("/stats/dashboard")
def get_dashboard(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """大屏聚合数据。

    - admin：全平台统计
    - user：仅自己的数据
    - 30 秒进程内缓存
    - 失败 fallback 到空数据 + 200
    """
    key = _cache_key(current_user)
    now_ts = time.time()
    cached = _DASHBOARD_CACHE.get(key)
    if cached is not None:
        payload, expires_at = cached
        if expires_at > now_ts:
            response.headers["X-Cache"] = "HIT"
            response.headers["X-Cache-TTL"] = str(int(expires_at - now_ts))
            return payload

    # 缓存未命中或已过期 → 重新计算
    try:
        payload = _build_dashboard(db, current_user)
    except Exception as e:
        # 优雅降级：日志告警 + 返回空数据，绝不把 5xx 暴露给大屏
        log.exception("[dashboard] build failed, fallback to empty: %s", e)
        payload = _empty_dashboard()

    _DASHBOARD_CACHE[key] = (payload, now_ts + _DASHBOARD_TTL_S)
    response.headers["X-Cache"] = "MISS"
    response.headers["X-Cache-TTL"] = str(_DASHBOARD_TTL_S)
    return payload
