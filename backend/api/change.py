"""
时相变化检测接口
================

POST /api/change
- 接受两张图像（A / B），分别走 ModelService.predict 流水线
- 算出 label 变化列表（top1_changed / label_lost / label_gained）
- 落库到 `change_jobs`
- 返回结构化结果 + 自然语言 summary

设计要点：
- `compute_changes()` 和 `make_summary()` 都是纯函数，方便单元测试
- 复用 backend.services.model_service.ModelService.predict——不重复实现推理逻辑
- 同步落库：变化检测本身是即时的（不像报表），不需要异步任务
"""
from __future__ import annotations

import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import ChangeJob, User
from backend.security.deps import get_current_user
from backend.services.model_manager import ModelManager
from backend.services.model_service import ModelService
from backend.services.storage_service import StorageService

log = logging.getLogger(__name__)
router = APIRouter()


# ==================== 依赖注入 ====================
def get_model_service() -> ModelService:
    return ModelService(ModelManager())


def get_storage_service() -> StorageService:
    return StorageService()


# ==================== 纯函数：变化检测算法 ====================
def compute_changes(top5_a: list[dict], top5_b: list[dict]) -> list[dict]:
    """对比两图的 Top-5，生成变化列表。

    返回三种类型：
    - top1_changed：top1 标签不同
    - label_lost：A 的 top1 不再出现在 B 的 top5 中
    - label_gained：B 的 top1 是 A 的 top5 中从未出现的新标签

    每条形如：{"type": "top1_changed", "from": "Forest", "to": "Highway", "score_a": 0.91, "score_b": 0.73}
    """
    if not top5_a or not top5_b:
        return []
    labels_a = [x["label"] for x in top5_a]
    labels_b = [x["label"] for x in top5_b]
    top1_a = top5_a[0]
    top1_b = top5_b[0]
    set_a, set_b = set(labels_a), set(labels_b)
    score_a_map = {x["label"]: x["score"] for x in top5_a}
    score_b_map = {x["label"]: x["score"] for x in top5_b}

    changes: list[dict] = []
    if top1_a["label"] != top1_b["label"]:
        changes.append({
            "type": "top1_changed",
            "from": top1_a["label"],
            "to": top1_b["label"],
            "score_a": top1_a["score"],
            "score_b": top1_b["score"],
        })
    if top1_a["label"] not in set_b:
        changes.append({
            "type": "label_lost",
            "label": top1_a["label"],
            "score_a": top1_a["score"],
            "score_b": score_b_map.get(top1_a["label"], 0.0),
        })
    if top1_b["label"] not in set_a:
        changes.append({
            "type": "label_gained",
            "label": top1_b["label"],
            "score_a": score_a_map.get(top1_b["label"], 0.0),
            "score_b": top1_b["score"],
        })
    return changes


def make_summary(top1_a: dict, top1_b: dict, changes: list[dict]) -> str:
    """自然语言 summary。"""
    if not changes:
        return (
            f"两图主要类别保持一致：{top1_a['label']} -> {top1_b['label']}。"
            f"Top-5 集合未发生显著变化。"
        )
    parts = [f"时相 A 主类别: {top1_a['label']}（{top1_a['score']:.2%}）；"]
    parts.append(f"时相 B 主类别: {top1_b['label']}（{top1_b['score']:.2%}）。")
    for ch in changes:
        if ch["type"] == "top1_changed":
            parts.append(f"主要类别从「{ch['from']}」变为「{ch['to']}」。")
        elif ch["type"] == "label_lost":
            parts.append(f"原主类别「{ch['label']}」在 B 期前 5 中消失。")
        elif ch["type"] == "label_gained":
            parts.append(f"新主类别「{ch['label']}」在 A 期前 5 中未出现。")
    return "".join(parts)


# ==================== 响应模型 ====================
class ChangeOut(BaseModel):
    id: int
    top1_a: dict
    top1_b: dict
    top5_a: list[dict]
    top5_b: list[dict]
    changes: list[dict]
    summary: str
    mock: bool


# ==================== 路由 ====================
@router.post("/change", response_model=ChangeOut)
async def detect_change(
    image_a: UploadFile = File(...),
    image_b: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    model_service: ModelService = Depends(get_model_service),
    storage_service: StorageService = Depends(get_storage_service),
) -> ChangeOut:
    """时相变化检测：A/B 两图 -> Top-5 对比 + 变化列表 + summary。"""
    try:
        contents_a = await image_a.read()
        contents_b = await image_b.read()
        img_a = Image.open(io.BytesIO(contents_a)).convert("RGB")
        img_b = Image.open(io.BytesIO(contents_b)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image: {e}")

    # 推理（不写库，落库在最后由 change_jobs 统一写）
    res_a = model_service.predict(img_a)
    res_b = model_service.predict(img_b)

    top5_a, top5_b = res_a["top5"], res_b["top5"]
    top1_a, top1_b = top5_a[0], top5_b[0]
    changes = compute_changes(top5_a, top5_b)
    summary = make_summary(top1_a, top1_b, changes)

    # 落盘 + 落库
    try:
        rel_a = storage_service.save_upload_file(contents_a)
        rel_b = storage_service.save_upload_file(contents_b)
        job = ChangeJob(
            user_id=current_user.id,
            image_a_path=rel_a,
            image_b_path=rel_b,
            top1_a=top1_a["label"],
            top1_b=top1_b["label"],
            changes_json=json.dumps(changes, ensure_ascii=False),
            status="completed",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
    except Exception as e:
        log.exception("failed to persist change job: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"persist failed: {e}")

    return ChangeOut(
        id=job.id,
        top1_a=top1_a,
        top1_b=top1_b,
        top5_a=top5_a,
        top5_b=top5_b,
        changes=changes,
        summary=summary,
        mock=(res_a["mock"] or res_b["mock"]),
    )
