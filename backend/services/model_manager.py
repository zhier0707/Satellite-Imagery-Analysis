"""
线程安全的模型管理器
====================

负责模型实例的生命周期管理：
- 启动时按需加载模型权重
- 通过 threading.Lock 保护模型加载/访问的原子性
- 对外暴露 get_model / get_device / is_model_loaded / reload_model 等接口

该模块替代原先 `backend.api.classify` 中以模块级全局变量
（_MODEL / _DEVICE / _MODEL_LOADED）管理模型状态的方式，
解决 FastAPI 多线程/异步并发环境下的竞态条件与状态不一致问题。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock
from typing import Optional

log = logging.getLogger(__name__)


class ModelManager:
    """线程安全的单例模型管理器。

    通过双重检查 + 类级锁保证实例唯一，通过实例级锁保护模型加载/访问，
    避免并发请求之间的竞态条件。
    """

    _instance: Optional["ModelManager"] = None
    _cls_lock: Lock = Lock()

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            with cls._cls_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._model_lock = Lock()
        self._model: Optional["torch.nn.Module"] = None
        self._device: str = "cpu"
        self._model_loaded: bool = False
        self._weights_path: Optional[str] = None
        self._initialized = True
        log.info("ModelManager initialized")

    def load_model(self, weights_path: Optional[str] = None) -> bool:
        """线程安全地加载模型。

        Args:
            weights_path: 模型权重文件路径，None 时从环境变量 MODEL_WEIGHTS 读取。

        Returns:
            是否成功加载模型（False 时上层应回退到 mock 模式）。
        """
        with self._model_lock:
            if self._model_loaded:
                return True

            try:
                import timm
                import torch

                ckpt_path = weights_path or os.environ.get(
                    "MODEL_WEIGHTS", "models/checkpoints/best.pt"
                )
                if not Path(ckpt_path).is_file():
                    log.info(
                        "model weights not found at %s, fallback to mock", ckpt_path
                    )
                    self._weights_path = ckpt_path
                    return False

                log.info("loading model from %s ...", ckpt_path)
                model = timm.create_model(
                    "tf_efficientnetv2_m", pretrained=False, num_classes=10
                )
                state = torch.load(ckpt_path, map_location="cpu")
                state = state.get("model", state)
                model.load_state_dict(state, strict=False)
                model.eval()

                self._model = model
                self._device = "cpu"
                self._model_loaded = True
                self._weights_path = ckpt_path
                log.info("model loaded successfully from %s", ckpt_path)
                return True

            except Exception as e:
                log.warning("failed to load model: %s, fallback to mock", e)
                self._model_loaded = False
                return False

    def get_model(self) -> Optional["torch.nn.Module"]:
        """获取当前已加载的模型实例（线程安全），未加载时返回 None。"""
        with self._model_lock:
            return self._model

    def get_device(self) -> str:
        """获取模型所在设备。"""
        with self._model_lock:
            return self._device

    def is_model_loaded(self) -> bool:
        """判断模型是否已加载。"""
        with self._model_lock:
            return self._model_loaded

    def reload_model(self) -> bool:
        """清空当前状态后重新加载。"""
        with self._model_lock:
            self._model = None
            self._model_loaded = False
            path = self._weights_path
        return self.load_model(path)


# ==================== 模块级便捷函数（兼容旧接口） ====================
def load_model(weights_path: Optional[str] = None) -> bool:
    """进程级便捷函数：复用全局唯一的 ModelManager。

    保留此函数是为了让 main.py 等旧调用方保持兼容：
    from backend.api.classify import load_model
    """
    return ModelManager().load_model(weights_path)
