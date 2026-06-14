"""Quick smoke test for the scaffold — verifies import paths, data dir, and FastAPI route table."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 1. 依赖可导入
import fastapi  # noqa: F401
import uvicorn  # noqa: F401
import timm  # noqa: F401
import torch  # noqa: F401
import cv2  # noqa: F401
from PIL import Image  # noqa: F401

print("OK  python deps importable")

# 2. 数据集
eurosat = ROOT / "data" / "eurosat"
classes = sorted([p.name for p in eurosat.iterdir() if p.is_dir()])
expected = [
    "AnnualCrop", "Forest", "HerbaceousVegetation", "Highway", "Industrial",
    "Pasture", "PermanentCrop", "Residential", "River", "SeaLake",
]
assert classes == expected, f"classes mismatch: {classes}"
print(f"OK  data/eurosat has all 10 classes")

# 3. 自家模块
import src.data.dataset as ds
import src.train  # noqa: F401
import src.gradcam  # noqa: F401
import backend.main as backend_main
import backend.classes as backend_classes
print("OK  src/ + backend/ imports clean")

# 4. 路由
app = backend_main.app
paths = sorted({r.path for r in app.routes if hasattr(r, "path")})
print(f"OK  registered routes: {paths}")
assert "/api/classify" in paths
assert "/api/heatmap" in paths
assert "/api/stats" in paths
print("ALL SMOKE TESTS PASSED")
