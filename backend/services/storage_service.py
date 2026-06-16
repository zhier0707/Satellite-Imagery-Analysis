"""
存储服务
========

负责上传文件的本地存储路径管理。
将原本散落在 API 路由中的「写盘」逻辑抽离为可注入的服务，
便于复用、测试与替换实现。
"""
from __future__ import annotations

import logging
import os
from typing import Optional
from uuid import uuid4

from backend.db.base import DATA_DIR

log = logging.getLogger(__name__)


class StorageService:
    """存储服务，提供上传文件的本地落盘能力。"""

    def __init__(self, upload_dir: Optional[str] = None) -> None:
        """初始化存储服务。

        Args:
            upload_dir: 上传目录；为 None 时使用默认 ``<DATA_DIR>/uploads``。
        """
        self.upload_dir = upload_dir or os.path.join(DATA_DIR, "uploads")
        os.makedirs(self.upload_dir, exist_ok=True)
        log.debug("StorageService ready, upload_dir=%s", self.upload_dir)

    def save_upload_file(self, contents: bytes, suffix: str = ".jpg") -> str:
        """把上传的字节写到本地，返回 ``uploads/<uuid>.<suffix>`` 相对路径。"""
        filename = f"{uuid4().hex}{suffix}"
        abspath = os.path.join(self.upload_dir, filename)
        with open(abspath, "wb") as f:
            f.write(contents)
        return f"uploads/{filename}"
