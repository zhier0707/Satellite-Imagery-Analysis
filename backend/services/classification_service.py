"""
分类业务服务
============

将「分类推理 + 图像落盘 + 落库」整体业务从 API 路由中抽离。
原 ``backend.api.classify.classify`` 路由内的全部副作用操作迁移至此，
并保留原行为：
- 推理失败/落库失败均不阻断分类响应；
- 返回结构保持一致 ``{"top1", "top5", "mock"}``。
"""
from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image
    from sqlalchemy.orm import Session


log = logging.getLogger(__name__)


class ClassificationService:
    """分类业务服务：组合 ModelService + StorageService + DB 落库。"""

    def __init__(self, model_service: Any, storage_service: Any) -> None:
        self._model_service = model_service
        self._storage_service = storage_service

    def classify_image(
        self,
        img: "Image.Image",
        contents: bytes,
        user_id: int,
        db: "Session",
    ) -> dict:
        """执行分类 + 持久化（含异常隔离）。"""
        t0 = time.time()
        result = self._model_service.predict(img)
        top5 = result["top5"]
        mock_used = result["mock"]

        # ============== 落库（写盘 + DB） ==============
        try:
            rel_path = self._storage_service.save_upload_file(contents)
            duration_ms = int((time.time() - t0) * 1000)

            # 延后导入，避免在仅用 mock 的环境里强制依赖 SQLAlchemy 类型
            from backend.db.models import ClassifyRecord

            record = ClassifyRecord(
                user_id=user_id,
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
