"""
报表导出 - 任务管理
====================

接口：
- POST /api/reports/export        立即返回 202 + job_id，后台异步生成
- GET  /api/reports               我的导出任务列表（分页）
- GET  /api/reports/{id}          单个任务详情
- GET  /api/reports/{id}/download status=completed 时返回 FileResponse

设计：
- 全局 ThreadPoolExecutor（max_workers=2），避免并发报表拖垮内存
- export_jobs 已有字段：id / user_id / kind / params_json / output_path / status / created_at
- params_json 存 time_range / class_filter 这样的入参，便于下载时还原
- 生成回调里通过 `REPORT_BUILDERS` 字典查生成器（Stage D 时注册 PDF/Excel/CSV）
- 失败时 status=failed + 错误信息 print 到 log

注意：本文件不依赖 reportlab / openpyxl，这些由 Stage D 在生成器里 import。
"""
from __future__ import annotations

import json
import logging
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.base import DATA_DIR, get_db
from backend.db.models import ExportJob, User
from backend.security.deps import get_current_user

log = logging.getLogger(__name__)
router = APIRouter()

# ==================== 路径 ====================
REPORTS_DIR = Path(DATA_DIR) / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 线程池 ====================
# max_workers=2：PDF/Excel 生成会吃内存，并发两个已经是合理上限
_EXECUTOR: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="report")

# ==================== 生成器注册表（Stage D 注入） ====================
# 值: (builder, ext)  - builder 签名 (db, user, params, output_path) -> None
REPORT_BUILDERS: dict[str, tuple[Callable[..., None], str]] = {}


def register_builder(kind: str, ext: str) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """装饰器：注册报表生成器。Stage D 用法：

        @register_builder("pdf", "pdf")
        def build_pdf(db, user, params, output_path): ...
    """
    def deco(fn: Callable[..., None]) -> Callable[..., None]:
        REPORT_BUILDERS[kind] = (fn, ext)
        return fn
    return deco


# ==================== Schemas ====================
class ExportIn(BaseModel):
    kind: str = Field(..., pattern="^(pdf|excel|csv)$")
    time_range: Optional[list[str]] = None  # [from_iso, to_iso]
    class_filter: Optional[list[str]] = None
    extra: Optional[dict[str, Any]] = None


class ExportOut(BaseModel):
    id: int
    kind: str
    status: str
    output_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExportListOut(BaseModel):
    items: list[ExportOut]
    total: int
    page: int
    page_size: int


# ==================== 后台任务 ====================
def _run_export(job_id: int) -> None:
    """在线程池中跑生成器；写 output_path / status。"""
    from backend.db.base import SessionLocal  # 局部 import 避免循环

    db = SessionLocal()
    try:
        job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if job is None:
            log.error("[report] job %s 不存在", job_id)
            return
        params = json.loads(job.params_json or "{}")
        entry = REPORT_BUILDERS.get(job.kind)
        if entry is None:
            log.error("[report] job %s kind=%s 无可用生成器（Stage D 未注册？）", job_id, job.kind)
            job.status = "failed"
            db.commit()
            return
        builder, ext = entry

        # 输出路径：data/reports/<user_id>/<job_id>.<ext>
        out_dir = REPORTS_DIR / str(job.user_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{job_id}.{ext}"

        job.status = "running"
        db.commit()

        try:
            builder(db, db.query(User).filter(User.id == job.user_id).first(), params, out_path)
            job.output_path = str(out_path.relative_to(REPORTS_DIR.parent))
            job.status = "completed"
            log.info("[report] job %s  -> %s  完成", job_id, out_path)
        except Exception as e:
            log.exception("[report] job %s 生成失败: %s\n%s", job_id, e, traceback.format_exc())
            job.status = "failed"

        db.commit()
    finally:
        db.close()


# ==================== 路由 ====================
@router.post("/reports/export", response_model=ExportOut, status_code=202)
def create_export(
    payload: ExportIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportOut:
    """创建导出任务：落库（status=queued）-> 提交线程池 -> 立即返回 202。"""
    job = ExportJob(
        user_id=current_user.id,
        kind=payload.kind,
        params_json=json.dumps({
            "time_range": payload.time_range,
            "class_filter": payload.class_filter,
            "extra": payload.extra or {},
        }, ensure_ascii=False),
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 提交到线程池（不 await）
    fut: Future = _EXECUTOR.submit(_run_export, job.id)
    fut.add_done_callback(lambda f: f.exception() and log.error("[report] future 异常: %s", f.exception()))

    return ExportOut(
        id=job.id, kind=job.kind, status=job.status,
        output_path=job.output_path, created_at=job.created_at,
    )


@router.get("/reports", response_model=ExportListOut)
def list_reports(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportListOut:
    """我的导出任务列表（分页）。"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    q = db.query(ExportJob).filter(ExportJob.user_id == current_user.id)
    total = q.count()
    rows = (
        q.order_by(ExportJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ExportListOut(
        items=[
            ExportOut(
                id=r.id, kind=r.kind, status=r.status,
                output_path=r.output_path, created_at=r.created_at,
            )
            for r in rows
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/reports/{report_id}", response_model=ExportOut)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportOut:
    """单个任务详情。"""
    r: Optional[ExportJob] = (
        db.query(ExportJob)
        .filter(ExportJob.id == report_id, ExportJob.user_id == current_user.id)
        .first()
    )
    if r is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return ExportOut(
        id=r.id, kind=r.kind, status=r.status,
        output_path=r.output_path, created_at=r.created_at,
    )


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下载完成的报表。status 必须 completed 且 output_path 存在。"""
    r: Optional[ExportJob] = (
        db.query(ExportJob)
        .filter(ExportJob.id == report_id, ExportJob.user_id == current_user.id)
        .first()
    )
    if r is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if r.status != "completed":
        raise HTTPException(status_code=409, detail=f"Report status is {r.status}, not completed")
    if not r.output_path:
        raise HTTPException(status_code=500, detail="output_path missing on completed job")

    # output_path 是相对 DATA_DIR 父目录存的（避开 Windows 绝对路径中文问题）
    abs_path = Path(DATA_DIR) / r.output_path
    if not abs_path.is_file():
        log.error("[report] job %s output_path 文件不存在: %s", report_id, abs_path)
        raise HTTPException(status_code=410, detail="output file gone")

    media_type = {
        "pdf": "application/pdf",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
    }.get(r.kind, "application/octet-stream")
    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=abs_path.name,
    )
