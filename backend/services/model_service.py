"""
模型服务
========

封装图像预处理与推理逻辑，并通过 ModelManager 获取线程安全的模型实例。
原 ``backend.api.classify.classify_pil`` 的业务逻辑迁移至此，
保持外部行为一致：返回 ``{"top1": ..., "top5": [...], "mock": bool}``。
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

from backend.classes import EUROSAT_CLASSES

if TYPE_CHECKING:
    import torch
    from PIL import Image


log = logging.getLogger(__name__)


class ModelService:
    """模型服务：负责单张图像的分类推理（真实模型 / mock 回退）。"""

    def __init__(self, model_manager: "Any") -> None:
        """初始化模型服务。

        Args:
            model_manager: 实现 ``ModelManager`` 协议的对象；
                便于测试时注入 mock。
        """
        self._model_manager = model_manager

    def preprocess_image(self, img: "Image.Image") -> "torch.Tensor":
        """PIL 图像 -> 模型输入张量。

        与原 ``_preprocess`` 行为一致：Resize(384,384) -> ToTensor -> Normalize。
        """
        import torchvision.transforms as transforms

        tf = transforms.Compose([
            transforms.Resize((384, 384)),
            transforms.ToTensor(),
            transforms.Normalize(
                (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
            ),
        ])
        return tf(img).unsqueeze(0)

    def predict(self, img: "Image.Image") -> dict:
        """对一张 PIL 图做推理，返回 ``{"top1", "top5", "mock"}``。

        - 模型未加载或推理异常时回退到 mock_topk。
        - 保持与原 ``classify_pil`` 完全一致的输出结构。
        """
        model = self._model_manager.get_model()
        if model is not None:
            try:
                import torch

                with torch.no_grad():
                    device = self._model_manager.get_device()
                    x = self.preprocess_image(img).to(device)
                    logits = model(x)
                    probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
                top5_idx = probs.argsort()[::-1][:5]
                top5 = [
                    {
                        "label": EUROSAT_CLASSES[i],
                        "score": float(round(float(probs[i]), 4)),
                    }
                    for i in top5_idx
                ]
                return {"top1": top5[0], "top5": top5, "mock": False}
            except Exception as e:
                log.exception("inference failed, fallback to mock: %s", e)

        # 模型未加载或推理失败 -> mock
        top5 = self._mock_topk(5)
        return {"top1": top5[0], "top5": top5, "mock": True}

    @staticmethod
    def _mock_topk(k: int = 5) -> list[dict]:
        """稳定随机的 Top-K，用于无模型时的占位结果。"""
        rng = random.Random(42)
        scores = [rng.random() for _ in EUROSAT_CLASSES]
        s = sum(scores)
        scores = [v / s for v in scores]
        pairs = sorted(zip(EUROSAT_CLASSES, scores), key=lambda x: -x[1])[:k]
        return [{"label": name, "score": float(round(sc, 4))} for name, sc in pairs]

    @property
    def is_model_loaded(self) -> bool:
        """便捷读取：当前模型是否已加载。"""
        return bool(self._model_manager.is_model_loaded())
