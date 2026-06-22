"""
``/api/stats`` 窗口接口空数据测试
==================================

验证 ``backend/api/stats.py`` 的 ``GET /api/stats`` 端点
在「完全没有分类记录」时返回 200 + 完整 10 类分布（全 0），
且不抛错。

设计要点
--------
- 该端点基于内存 deque ``_RECORDS``（不依赖 DB / 鉴权）
- 修复目标：空记录时 counts 字典应自动补全为 ``{cls: 0 for cls in EUROSAT_CLASSES}``
  （与 dashboard 端点的 ``_empty_dashboard`` 行为一致）
- 旧实现下空 records 时返回 ``counts={}`` → 测试会失败 → 暴露 bug

运行：
    cd e:\\truth-视觉实践
    python -m pytest tests/test_stats_window.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# PowerShell 默认 GBK
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.stats import _RECORDS, router as stats_router  # noqa: E402
from backend.classes import EUROSAT_CLASSES  # noqa: E402
from backend.db.base import Base, SessionLocal, engine  # noqa: E402
from backend.db.models import ClassifyRecord, User  # noqa: E402
from backend.security.deps import get_current_user  # noqa: E402
from backend.security.password import hash_password  # noqa: E402


# ==================== 测试应用 ====================
app = FastAPI()
app.include_router(stats_router, prefix="/api", tags=["stats"])


# ==================== Fixtures ====================
@pytest.fixture(autouse=True)
def _setup_clean_state():
    """每次测试前清空内存 records + 清理 DB 中的 classify_records。

    autouse=True → 本文件内所有测试自动得到一个空起点。
    """
    # 1. 内存 deque 清空（/api/stats 的真实数据源）
    _RECORDS.clear()

    # 2. DB 中 ClassifyRecord 清空（避免上一轮测试残留干扰）
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(ClassifyRecord).delete()
        db.commit()
    finally:
        db.close()

    yield

    # 测试后再次清空
    _RECORDS.clear()
    db = SessionLocal()
    try:
        db.query(ClassifyRecord).delete()
        db.commit()
    finally:
        db.close()


# ==================== Test 1: 空 records → 200 + 完整 10 类分布 ====================
def test_stats_with_no_records() -> None:
    """无任何分类记录时，GET /api/stats 应返回 200 + counts 含全部 10 个类别（值=0）。"""
    client = TestClient(app)
    r = client.get("/api/stats")
    assert r.status_code == 200, (
        f"空 records 应 200，实际 {r.status_code}: {r.text[:200]}"
    )
    body = r.json()

    # 顶层字段完整性
    assert "counts" in body, f"响应缺 counts 字段: {body}"
    assert "total" in body, f"响应缺 total 字段: {body}"
    assert "window_hours" in body, f"响应缺 window_hours 字段: {body}"
    assert body["total"] == 0, f"无记录时 total 应为 0，实际 {body['total']}"

    # counts 字典应含全部 10 个类别（全 0）
    counts = body["counts"]
    assert isinstance(counts, dict), f"counts 应为 dict，实际 {type(counts)}"
    missing = set(EUROSAT_CLASSES) - set(counts.keys())
    assert not missing, f"counts 缺类别: {missing}（应含全部 10 类，即使全 0）"

    # 每个类别值应为 0
    for cls in EUROSAT_CLASSES:
        assert counts.get(cls) == 0, (
            f"counts[{cls!r}] 应为 0，实际 {counts.get(cls)}"
        )
    print(f"\n  ✓ 空 records → 200, counts 10 类齐全（全 0）, total={body['total']}")
    print(f"    counts={counts}")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    """允许 ``python tests/test_stats_window.py`` 直接跑。"""
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())
