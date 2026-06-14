"""
admin 训练任务管理
==================

接口（全部接 require_admin）：
- POST /api/admin/training/start      启动训练（subprocess.Popen train.py）
- GET  /api/admin/training            任务列表（分页）
- GET  /api/admin/training/{id}       任务详情（含 log_tail 50 行、best_val_acc）
- POST /api/admin/training/{id}/stop  终止训练

设计要点：
- 用 subprocess.Popen 起 train.py；为本地不真训练，默认 dry-run
- daemon 线程读 stdout/stderr -> 写 data/logs/training/{id}.log
- watcher 线程每秒 poll returncode，进程退出后改 status=completed/failed
- best_val_acc 从 log 行 `↳ 保存最佳检查点 -> ... val_acc=0.95` 解析
- 进程在 Popen._proc 字典里，便于 stop 终止
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.base import DATA_DIR, get_db
from backend.db.models import TrainingJob, User
from backend.security.deps import require_admin

log = logging.getLogger(__name__)
router = APIRouter()

# ==================== 路径 ====================
LOG_DIR = Path(DATA_DIR) / "logs" / "training"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parent.parent.parent
TRAIN_SCRIPT = ROOT / "src" / "train.py"

# ==================== 进程跟踪 ====================
# job_id -> Popen（用于 stop）
_PROCS: dict[int, subprocess.Popen] = {}
_PROCS_LOCK = threading.Lock()
# job_id -> log file handle（避免 stop 时还要追踪；用 _PROCS_LOCK 保护也行，这里简化）
_LOG_HANDLES: dict[int, Any] = {}

# ==================== 解析 log 中的 val_acc ====================
_VAL_ACC_RE = re.compile(r"val_acc=(\d+\.\d+)")


def _parse_best_val_acc(log_path: Path) -> Optional[float]:
    """从 log 中找最后一行的 val_acc=0.xx，返回最大或最后出现的。

    训练循环中每行形如：
        epoch   3/50  train_loss=0.1234  ...  val_acc=0.9500
    """
    if not log_path.is_file():
        return None
    best: Optional[float] = None
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _VAL_ACC_RE.search(line)
                if m:
                    v = float(m.group(1))
                    if best is None or v > best:
                        best = v
    except OSError as e:
        log.warning("read log %s failed: %s", log_path, e)
    return best


# ==================== 后台线程：watcher ====================
def _watcher_thread(job_id: int, proc: subprocess.Popen, log_path: Path) -> None:
    """每秒 poll returncode；进程退出后更新 status / finished_at / best_val_acc。"""
    from backend.db.base import SessionLocal

    db = SessionLocal()
    try:
        # 等 1 秒拿首次心跳（让 status 变 running）
        time.sleep(1.0)
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if job is None:
            log.error("[training] watcher: job %s 不存在", job_id)
            return
        if job.status == "queued":
            job.status = "running"
            job.started_at = datetime.utcnow()
            db.commit()

        # poll
        while proc.poll() is None:
            time.sleep(1.0)

        rc = proc.returncode
        job.finished_at = datetime.utcnow()
        # 解析 log
        job.best_val_acc = _parse_best_val_acc(log_path)
        if job.status == "stopped":
            log.info("[training] job %s 已 stop（returncode=%s）", job_id, rc)
        elif rc == 0:
            job.status = "completed"
            log.info("[training] job %s 训练完成（rc=0, best_val_acc=%s）",
                     job_id, job.best_val_acc)
        else:
            job.status = "failed"
            job.error = f"returncode={rc}"
            log.warning("[training] job %s 训练失败 rc=%s", job_id, rc)
        db.commit()
    except Exception as e:
        log.exception("watcher thread failed: %s", e)
    finally:
        with _PROCS_LOCK:
            _PROCS.pop(job_id, None)
            fh = _LOG_HANDLES.pop(job_id, None)
        if fh is not None:
            try:
                fh.close()
            except OSError:
                pass
        db.close()


# ==================== Schemas ====================
class StartTrainingIn(BaseModel):
    stage: int = Field(2, ge=1, le=3)
    epochs: int = Field(1, ge=1, le=1000)
    batch_size: int = Field(8, ge=1, le=256)
    lr: float = Field(1e-4, gt=0)
    resume_from: Optional[str] = None
    data_root: str = "data/eurosat"
    dry_run: bool = True  # 默认 dry-run，不真跑训练


class TrainingOut(BaseModel):
    id: int
    stage: int
    epochs: int
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    best_val_acc: Optional[float] = None
    error: Optional[str] = None
    created_at: datetime
    last_checkpoint_path: Optional[str] = None

    class Config:
        from_attributes = True


class TrainingDetailOut(TrainingOut):
    log_tail: list[str] = []
    config: dict[str, Any] = {}


class TrainingListOut(BaseModel):
    items: list[TrainingOut]
    total: int
    page: int
    page_size: int


# ==================== 路由 ====================
@router.post("/training/start", response_model=TrainingOut, status_code=202)
def start_training(
    payload: StartTrainingIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TrainingOut:
    """启动训练任务（默认 dry-run，subprocess 启 train.py）。"""
    if not TRAIN_SCRIPT.is_file():
        raise HTTPException(status_code=500, detail=f"train.py not found: {TRAIN_SCRIPT}")

    # 写 DB（status=queued）
    job = TrainingJob(
        user_id=current_user.id,
        stage=f"stage{payload.stage}",
        epochs=payload.epochs,
        status="queued",
        metrics_json=json.dumps(payload.dict(), ensure_ascii=False),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 构造命令行
    cmd = [
        sys.executable,
        str(TRAIN_SCRIPT),
        "--data-root", payload.data_root,
        "--stage", str(payload.stage),
        "--epochs", str(payload.epochs),
        "--batch-size", str(payload.batch_size),
        "--lr", str(payload.lr),
    ]
    if payload.resume_from:
        cmd += ["--resume-from", payload.resume_from]
    if payload.dry_run:
        cmd += ["--dry-run"]

    # 启动 subprocess
    # 重要：Windows 上 Popen.PIPE + bufsize=1 在不及时消费 stdout 时会死锁
    # → 用文件重定向，subprocess 自己写 log，避开 PIPE buffer 问题
    log_path = LOG_DIR / f"{job.id}.log"
    try:
        log_fh = open(log_path, "wb")
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
        )
    except Exception as e:
        job.status = "failed"
        job.error = f"failed to start: {e}"
        db.commit()
        raise HTTPException(status_code=500, detail=f"start training failed: {e}")

    with _PROCS_LOCK:
        _PROCS[job.id] = proc
        _LOG_HANDLES[job.id] = log_fh

    # 启动后台 watcher（不启 reader 线程——subprocess 自己写 log）
    threading.Thread(
        target=_watcher_thread, args=(job.id, proc, log_path), daemon=True, name=f"train-watch-{job.id}",
    ).start()

    log.info("[training] job %s 已启动, cmd=%s", job.id, " ".join(cmd))
    return TrainingOut(
        id=job.id, stage=payload.stage, epochs=payload.epochs,
        status=job.status, started_at=job.started_at, finished_at=job.finished_at,
        best_val_acc=job.best_val_acc, error=job.error,
        created_at=job.created_at, last_checkpoint_path=job.last_checkpoint_path,
    )


@router.get("/training", response_model=TrainingListOut)
def list_training(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TrainingListOut:
    """训练任务列表（分页）。"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20
    q = db.query(TrainingJob)
    total = q.count()
    rows = (
        q.order_by(TrainingJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TrainingListOut(
        items=[
            TrainingOut(
                id=r.id, stage=int(r.stage.replace("stage", "")) if r.stage and r.stage.startswith("stage") else 2,
                epochs=r.epochs, status=r.status, started_at=r.started_at, finished_at=r.finished_at,
                best_val_acc=r.best_val_acc, error=r.error,
                created_at=r.created_at, last_checkpoint_path=r.last_checkpoint_path,
            )
            for r in rows
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/training/{job_id}", response_model=TrainingDetailOut)
def get_training(
    job_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TrainingDetailOut:
    """训练任务详情 + log tail。"""
    r = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Training job not found")

    # 读 log tail（最后 50 行）
    log_tail: list[str] = []
    log_path = LOG_DIR / f"{r.id}.log"
    if log_path.is_file():
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            log_tail = [ln.rstrip("\n") for ln in lines[-50:]]
        except OSError as e:
            log.warning("read log %s failed: %s", log_path, e)

    # 解析 config
    try:
        config = json.loads(r.metrics_json or "{}")
    except (TypeError, ValueError):
        config = {}

    return TrainingDetailOut(
        id=r.id,
        stage=int(r.stage.replace("stage", "")) if r.stage and r.stage.startswith("stage") else 2,
        epochs=r.epochs, status=r.status, started_at=r.started_at, finished_at=r.finished_at,
        best_val_acc=r.best_val_acc, error=r.error,
        created_at=r.created_at, last_checkpoint_path=r.last_checkpoint_path,
        log_tail=log_tail, config=config,
    )


@router.post("/training/{job_id}/stop", response_model=TrainingOut)
def stop_training(
    job_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TrainingOut:
    """终止训练任务：subprocess.terminate()，status 转 stopped。"""
    r = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    if r.status in ("completed", "failed", "stopped"):
        raise HTTPException(status_code=409, detail=f"Job already {r.status}")

    with _PROCS_LOCK:
        proc = _PROCS.get(job_id)
    if proc is None or proc.poll() is not None:
        # 进程已退
        raise HTTPException(status_code=409, detail="process not running")

    try:
        proc.terminate()
    except Exception as e:
        log.warning("terminate job %s failed: %s", job_id, e)
    r.status = "stopped"
    db.commit()
    log.info("[training] job %s stop 信号已发", job_id)

    return TrainingOut(
        id=r.id,
        stage=int(r.stage.replace("stage", "")) if r.stage and r.stage.startswith("stage") else 2,
        epochs=r.epochs, status=r.status, started_at=r.started_at, finished_at=r.finished_at,
        best_val_acc=r.best_val_acc, error=r.error,
        created_at=r.created_at, last_checkpoint_path=r.last_checkpoint_path,
    )
