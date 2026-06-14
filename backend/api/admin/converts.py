"""
admin ONNX 转换任务
==================

POST /api/admin/converts/start
- 启动 `scripts/convert_to_onnx.py`（subprocess）
- 写 training_jobs 复用（kind="convert"），不另开表
- log 写到 data/logs/training/convert-{id}.log
"""
from __future__ import annotations

import json
import logging
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

LOG_DIR = Path(DATA_DIR) / "logs" / "training"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONVERT_SCRIPT = ROOT / "scripts" / "convert_to_onnx.py"

# 进程跟踪
_PROCS: dict[int, subprocess.Popen] = {}
_PROCS_LOCK = threading.Lock()


def _reader(proc: subprocess.Popen, log_path: Path) -> None:
    try:
        with open(log_path, "ab", buffering=0) as f:
            for line in iter(proc.stdout.readline, b""):
                f.write(line)
                f.flush()
            if proc.stderr:
                for line in iter(proc.stderr.readline, b""):
                    f.write(b"[stderr] " + line)
                    f.flush()
    except Exception as e:
        log.exception("convert reader failed: %s", e)


def _watcher(job_id: int, proc: subprocess.Popen) -> None:
    from backend.db.base import SessionLocal
    db = SessionLocal()
    try:
        time.sleep(0.5)
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if job is None:
            return
        if job.status == "queued":
            job.status = "running"
            job.started_at = datetime.utcnow()
            db.commit()
        while proc.poll() is None:
            time.sleep(1.0)
        rc = proc.returncode
        job.finished_at = datetime.utcnow()
        job.status = "completed" if rc == 0 else "failed"
        if rc != 0:
            job.error = f"returncode={rc}"
        db.commit()
        log.info("[convert] job %s 完成 rc=%s", job_id, rc)
    except Exception as e:
        log.exception("convert watcher failed: %s", e)
    finally:
        with _PROCS_LOCK:
            _PROCS.pop(job_id, None)
        db.close()


# ==================== Schemas ====================
class StartConvertIn(BaseModel):
    weights: str = Field(..., description=".pt 权重路径")
    output: str = "models/web_model/best.onnx"
    image_size: int = 384
    opset: int = 13


class ConvertOut(BaseModel):
    id: int
    status: str
    output: str
    created_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== 路由 ====================
@router.post("/converts/start", response_model=ConvertOut, status_code=202)
def start_convert(
    payload: StartConvertIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ConvertOut:
    if not CONVERT_SCRIPT.is_file():
        raise HTTPException(
            status_code=500,
            detail=f"convert_to_onnx.py not found: {CONVERT_SCRIPT}（Phase 4 实现）",
        )

    job = TrainingJob(
        user_id=current_user.id,
        stage="convert",
        epochs=0,
        status="queued",
        metrics_json=json.dumps(payload.dict(), ensure_ascii=False),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    cmd = [
        sys.executable, str(CONVERT_SCRIPT),
        "--weights", payload.weights,
        "--output", payload.output,
        "--image-size", str(payload.image_size),
        "--opset", str(payload.opset),
    ]
    log_path = LOG_DIR / f"convert-{job.id}.log"
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT), bufsize=1,
        )
    except Exception as e:
        job.status = "failed"
        job.error = f"failed to start: {e}"
        db.commit()
        raise HTTPException(status_code=500, detail=f"start convert failed: {e}")

    with _PROCS_LOCK:
        _PROCS[job.id] = proc

    threading.Thread(target=_reader, args=(proc, log_path), daemon=True).start()
    threading.Thread(target=_watcher, args=(job.id, proc), daemon=True).start()

    log.info("[convert] job %s 启动: %s", job.id, " ".join(cmd))
    return ConvertOut(
        id=job.id, status=job.status, output=payload.output,
        created_at=job.created_at, finished_at=job.finished_at, error=job.error,
    )
