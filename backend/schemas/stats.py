"""
大屏聚合数据响应模型
====================

对应 `GET /api/stats/dashboard` 端点的返回结构。
- `Kpi`：4 个核心数字
- `TimeSeriesPoint`：30 天趋势单日数据点
- `LocationPoint`：Top-50 分类点（无经纬度版本）
- `DashboardStats`：完整响应体
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


# ==================== KPI ====================
class Kpi(BaseModel):
    """4 个核心数字。"""

    total_records: int = Field(0, description="总记录数")
    today_new: int = Field(0, description="今日新增")
    active_users: int = Field(0, description="近 7 天活跃用户数")
    accuracy_avg: float = Field(0.0, description="平均 top1 置信度，0-1，4 位小数")


# ==================== 时间序列单点 ====================
class TimeSeriesPoint(BaseModel):
    """30 天趋势中的一天。"""

    date: str = Field(..., description="YYYY-MM-DD")
    count: int = Field(0, ge=0, description="当日新增记录数")


# ==================== 分类点（无经纬度版本）====================
class LocationPoint(BaseModel):
    """Top-50 分类点。

    注意：当前 `classify_records` 表不含 `lng/lat` 字段，
    此处只暴露 `id / label / score` 三元组，与 spec §B.4 的降级方案一致。
    """

    id: int = Field(..., description="classify_records.id")
    label: str = Field(..., description="top1 类别")
    score: float = Field(..., description="top1 置信度，0-1")


# ==================== 顶层响应 ====================
class DashboardStats(BaseModel):
    """大屏聚合数据完整响应。"""

    kpi: Kpi
    classification_distribution: Dict[str, int] = Field(
        ..., description="10 个固定 label -> 计数；缺失 label 补 0"
    )
    time_series: List[TimeSeriesPoint] = Field(
        ..., description="最近 30 天（升序），无数据日 count=0"
    )
    top_locations: List[LocationPoint] = Field(
        ..., description="按 top1_score 降序，最多 50 条"
    )
    generated_at: datetime = Field(..., description="服务端生成时间（UTC）")

    # Pydantic v2：允许从 ORM / dict 直接构造
    model_config = ConfigDict(from_attributes=True)
