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

本文件已重构为「纯 API 层」：
- 不再持有任何模型/业务全局状态；
- 通过 FastAPI Depends 注入 ModelService / ClassificationService；
- 模型生命周期由 backend.services.model_manager 统一管理（线程安全）。
"""
from __future__ import annotations

import base64
import io
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

# ==================== numpy 顶部导入（防 anyio portal 跨线程重导入）====================
# Windows 上 numpy 的 native extension 不允许在子线程中重导入（cannot load module
# more than once per process）。把 import numpy 提到模块顶部，让它在 pytest / 进程
# 启动时一次性加载到 sys.modules，子线程 endpoint 调用复用即可。
try:
    import numpy as np  # noqa: F401
except ImportError:  # 极端环境无 numpy 时降级为 None，endpoint 内再用 __import__ 兜底
    np = None  # type: ignore[assignment]

# ==================== cv2 顶部导入（Grad-CAM 与 mock 热力图均依赖）====================
# opencv-python / opencv-python-headless 任意一个即可；都没有时 mock 分支降级到 PIL
try:
    import cv2  # noqa: F401
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    CV2_AVAILABLE = False

from backend.db.base import get_db
from backend.db.models import User
from backend.security.deps import get_current_user
from backend.services.classification_service import ClassificationService
from backend.services.model_manager import ModelManager
from backend.services.model_service import ModelService
from backend.services.storage_service import StorageService

log = logging.getLogger(__name__)
router = APIRouter()


# ==================== 依赖注入（按请求组装服务） ====================

def get_model_manager() -> ModelManager:
    """获取全局唯一的 ModelManager 单例。"""
    return ModelManager()


def get_model_service(
    model_manager: ModelManager = Depends(get_model_manager),
) -> ModelService:
    return ModelService(model_manager)


def get_storage_service() -> StorageService:
    return StorageService()


def get_classification_service(
    model_service: ModelService = Depends(get_model_service),
    storage_service: StorageService = Depends(get_storage_service),
) -> ClassificationService:
    return ClassificationService(model_service, storage_service)


# ==================== 兼容旧 import 路径 ====================
# 旧代码（含 main.py / tests）会 ``from backend.api.classify import load_model``，
# 这里直接 re-export 线程安全的 ModelManager 加载函数，保证零回归。
from backend.services.model_manager import load_model  # noqa: E402,F401


# ==================== 分类接口 ====================

@router.post("/classify")
async def classify(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    classification_service: ClassificationService = Depends(get_classification_service),
):
    """分类接口：接受上传图像，返回 Top-5（登录用户，自动落库）。"""
    try:
        contents = await image.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image: {e}")

    return classification_service.classify_image(
        img=img,
        contents=contents,
        user_id=current_user.id,
        db=db,
    )


# ==================== Grad-CAM 接口 ====================

@router.post("/heatmap")
async def heatmap(
    image: UploadFile = File(...),
    target_class: int = Form(0),
    model_service: ModelService = Depends(get_model_service),
):
    """Grad-CAM 热力图接口。"""
    # 目标类别范围校验：EuroSAT 10 类 → 索引 0..9
    if not (0 <= target_class < 10):
        raise HTTPException(
            status_code=400,
            detail="target_class must be in 0..9",
        )
    try:
        contents = await image.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image: {e}")

    # 模型未加载 OR cv2 不可用 -> mock 热力图（保持与原行为一致）
    if not model_service.is_model_loaded or not CV2_AVAILABLE:
        # 直接用模块顶部已加载的 np，避免 anyio portal 子线程重导入
        # （Windows native extension 不能「load module more than once per process」）
        if np is None:
            import numpy as np_local  # 兜底：极少数无 numpy 环境
            _np = np_local
        else:
            _np = np

        h, w = _np.array(img).shape[:2]
        if CV2_AVAILABLE:
            # 有 cv2：沿用 numpy + cv2.imencode 旧路径
            mock = _np.zeros((h, w, 3), dtype="uint8")
            _, buf = cv2.imencode(".png", mock)
            png_bytes = buf.tobytes()
        else:
            # cv2 不可用：PIL 生成深灰图 (40,40,40) 并编码为 PNG，避免 ImportError 500
            mock_img = Image.new("RGB", (h, w), (40, 40, 40))
            buf = io.BytesIO()
            mock_img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
        return {
            "png_base64": base64.b64encode(png_bytes).decode(),
            "mock": True,
        }

    try:
        from src.gradcam import generate_gradcam, get_target_layer, overlay_heatmap
    except ImportError:
        raise HTTPException(status_code=501, detail="Grad-CAM not available in this env")

    try:
        img_np = np.array(img)[:, :, ::-1]  # RGB -> BGR
        x = model_service.preprocess_image(img)
        # ModelService 未直接暴露 model_manager，这里通过 get_model_manager 重新拉取
        model = ModelManager().get_model()
        target_layer = get_target_layer(model)
        cam = generate_gradcam(
            model, x, target_layer=target_layer, target_class=target_class
        )
        overlay = overlay_heatmap(img_np, cam, alpha=0.4)
        _, buf = cv2.imencode(".png", overlay)
        return {
            "png_base64": base64.b64encode(buf.tobytes()).decode(),
            "mock": False,
        }
    except Exception as e:
        log.exception("gradcam failed: %s", e)
        raise HTTPException(status_code=500, detail=f"gradcam error: {e}")
