"""
分类推理接口
=============

POST /api/classify
- 接受 multipart 上传一张图
- 返回 Top-5 类别与置信度
- 模型未加载时返回 mock 结果
- 登录用户成功推理后，落库到 `classify_records`（含 user_id）

POST /api/heatmap
- 接受 multipart 上传一张图 + target_class
- 返回 base64 编码 PNG（Grad-CAM 叠加图）
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from backend.classes import EUROSAT_CLASSES
from backend.db.base import DATA_DIR, get_db
from backend.db.models import ClassifyRecord, User
from backend.security.deps import get_current_user

log = logging.getLogger(__name__)
router = APIRouter()

# 模型全局缓存（启动时尝试加载一次）
_MODEL = None
_DEVICE = "cpu"
_MODEL_LOADED = False


def load_model(weights_path: Optional[str] = None) -> None:
    """惰性加载真实模型。失败时回退到 mock。"""
    global _MODEL, _MODEL_LOADED
    if _MODEL_LOADED:
        return
    try:
        import timm
        import torch

        ckpt_path = weights_path or os.environ.get(
            "MODEL_WEIGHTS", "models/checkpoints/best.pt"
        )
        if not Path(ckpt_path).is_file():
            log.info("model weights not found, fallback to mock")
            return
        model = timm.create_model("tf_efficientnetv2_m", pretrained=False, num_classes=10)
        state = torch.load(ckpt_path, map_location="cpu")
        state = state.get("model", state)
        model.load_state_dict(state, strict=False)
        model.eval()
        _MODEL = model
        _MODEL_LOADED = True
        log.info("model loaded from %s", ckpt_path)
    except Exception as e:
        log.warning("failed to load model: %s, fallback to mock", e)


def _preprocess(img: Image.Image) -> "torch.Tensor":
    """把 PIL 图像转成模型输入张量。"""
    import torch
    from torchvision import transforms

    tf = transforms.Compose([
        transforms.Resize((384, 384)),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    return tf(img).unsqueeze(0)


def _mock_topk(k: int = 5) -> list[dict]:
    """未加载模型时的伪预测：随机但稳定的 Top-K。"""
    rng = random.Random(42)
    scores = [rng.random() for _ in EUROSAT_CLASSES]
    s = sum(scores)
    scores = [v / s for v in scores]
    pairs = sorted(zip(EUROSAT_CLASSES, scores), key=lambda x: -x[1])[:k]
    return [{"label": name, "score": float(round(s, 4))} for name, s in pairs]


# ==================== 工具：保存上传图 ====================
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")


def _save_upload_to_disk(contents: bytes) -> str:
    """把上传字节写到 data/uploads/<uuid>.jpg，返回相对路径 uploads/<uuid>.jpg。"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid4().hex}.jpg"
    abspath = os.path.join(UPLOAD_DIR, filename)
    with open(abspath, "wb") as f:
        f.write(contents)
    return f"uploads/{filename}"


# ==================== 纯函数：PIL 图像 -> 分类结果 ====================
def classify_pil(img: Image.Image) -> dict:
    """对一张 PIL 图做推理，返回 {"top1": {...}, "top5": [...], "mock": bool}。

    纯函数：不写库、不落盘；变化检测接口（/api/change）也复用此函数。
    模型未加载或推理异常时回退到 mock_topk。
    """
    if _MODEL is not None:
        try:
            import torch
            with torch.no_grad():
                x = _preprocess(img).to(_DEVICE)
                logits = _MODEL(x)
                probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
            top5_idx = probs.argsort()[::-1][:5]
            top5 = [
                {"label": EUROSAT_CLASSES[i], "score": float(round(float(probs[i]), 4))}
                for i in top5_idx
            ]
            return {"top1": top5[0], "top5": top5, "mock": False}
        except Exception as e:
            log.exception("inference failed, fallback to mock: %s", e)

    # 模型未加载或推理失败 -> mock
    top5 = _mock_topk(5)
    return {"top1": top5[0], "top5": top5, "mock": True}


# ==================== 分类接口 ====================
@router.post("/classify")
async def classify(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分类接口：接受上传图像，返回 Top-5（登录用户，自动落库）。"""
    t0 = time.time()
    try:
        contents = await image.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image: {e}")

    result = classify_pil(img)
    top5 = result["top5"]
    mock_used = result["mock"]

    # ============== 落库（写盘 + DB） ==============
    try:
        rel_path = _save_upload_to_disk(contents)
        duration_ms = int((time.time() - t0) * 1000)
        record = ClassifyRecord(
            user_id=current_user.id,
            image_path=rel_path,
            top1_label=top5[0]["label"],
            top1_score=float(top5[0]["score"]),
            top5_json=json.dumps(top5, ensure_ascii=False),
            duration_ms=duration_ms,
        )
        db.add(record)
        db.commit()
    except Exception as e:
        # 落库失败不应阻断分类响应（推理结果已可用）
        log.exception("failed to persist classify record: %s", e)
        db.rollback()

    return {"top1": top5[0], "top5": top5, "mock": mock_used}


# ==================== Grad-CAM 接口 ====================
@router.post("/heatmap")
async def heatmap(image: UploadFile = File(...), target_class: int = Form(0)):
    """Grad-CAM 热力图接口。"""
    try:
        contents = await image.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        img_np = np.array(img)[:, :, ::-1]  # RGB -> BGR
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image: {e}")

    if _MODEL is None:
        # mock：返回与原图同尺寸的伪热力图（全黑）
        h, w = img_np.shape[:2]
        mock = np.zeros((h, w, 3), dtype=np.uint8)
        _, buf = __import__("cv2").imencode(".png", mock)
        return {"png_base64": base64.b64encode(buf.tobytes()).decode(), "mock": True}

    try:
        import cv2
        import torch
        from src.gradcam import generate_gradcam, overlay_heatmap, get_target_layer  # noqa: E501
    except ImportError:
        raise HTTPException(status_code=501, detail="Grad-CAM not available in this env")

    try:
        x = _preprocess(img)
        target_layer = get_target_layer(_MODEL)
        cam = generate_gradcam(_MODEL, x, target_layer=target_layer, target_class=target_class)
        overlay = overlay_heatmap(img_np, cam, alpha=0.4)
        _, buf = cv2.imencode(".png", overlay)
        return {"png_base64": base64.b64encode(buf.tobytes()).decode(), "mock": False}
    except Exception as e:
        log.exception("gradcam failed: %s", e)
        raise HTTPException(status_code=500, detail=f"gradcam error: {e}")
