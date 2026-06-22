"""
热力图 target_class 范围校验测试
===============================

覆盖 Phase D.1.3 的修复：
- `backend/api/classify.py` 的 `/api/heatmap` 端点校验 `target_class` 必须在 0..9
- 超出范围 → 400 + 明确 detail

测试策略
--------
- 越界值（-1 / 10 / 100）：校验在第一行就抛 400，**不**进入模型路径，无需 cv2/opencv
- 合法值（0..9）：校验通过后进入「mock 全黑 PNG」分支，需要 cv2
  → 通过 `unittest.mock` 注入 fake cv2，避免依赖真实 opencv-python

运行：
    cd e:\truth-视觉实践
    python -m pytest tests/test_heatmap_target_class.py -v
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest import mock

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

from backend.api.classify import router as classify_router  # noqa: E402
from backend.db.base import Base, SessionLocal, engine  # noqa: E402
from backend.db.models import User  # noqa: E402
from backend.security.deps import get_current_user  # noqa: E402
from backend.security.jwt import create_access_token  # noqa: E402
from backend.security.password import hash_password  # noqa: E402


# ==================== 测试应用 ====================
app = FastAPI()
app.include_router(classify_router, prefix="/api", tags=["classify"])


# ==================== 1x1 PNG fixture（最小合法 PNG）====================
# 用 PIL 生成一个 64×64 RGB 图像，存为 PNG 字节流
# 注意：手写 PNG header 容易写出错位字节（CRC / length），直接 PIL 最稳
def _make_png_bytes() -> bytes:
    """生成一个 64x64 RGB 图像的 PNG 字节流（用 PIL）。"""
    from PIL import Image
    img = Image.new("RGB", (64, 64), (100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MINIMAL_PNG_BYTES = _make_png_bytes()


# ==================== 伪 cv2 模块 ====================
# mock 模式（模型未加载）会调 `cv2.imencode('.png', mock_array)`，
# 当前测试环境可能没装 opencv-python。用 MagicMock 注入一个能跑就行。
#
# 注意：backend.api.classify 用的是 `buf.tobytes()`，因此 fake buf 必须
# 提供 tobytes() 方法（io.BytesIO 没有，但 numpy.ndarray 有）。
class _FakeBuf:
    """最小 cv2.imencode 输出替身：buf.tobytes() 即可被 base64 编码。"""

    def tobytes(self) -> bytes:
        # 32 字节填充：base64 编码后大约 44 字符，足以让路由认为有数据
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class _FakeCv2:
    """最小 cv2 替身：imencode 返回可被 base64 编码的「带 tobytes() 的对象」。"""

    @staticmethod
    def imencode(_ext: str, _arr) -> tuple[bool, _FakeBuf]:
        return True, _FakeBuf()


# ==================== Fixtures ====================
@pytest.fixture(autouse=True)
def _setup_test_user():
    """准备一个测试用户，并设置 dependency override。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "heat_tester").first()
        if u is None:
            u = User(
                username="heat_tester",
                email="heat_tester@test.local",
                password_hash=hash_password("heat123"),
                role="user",
                is_active=True,
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        current = u
    finally:
        db.close()

    def _override() -> User:
        return current

    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _post_heatmap(target_class: int):
    """简化 helper：POST /api/heatmap 带 target_class + 注入 fake cv2。

    注意：`target_class` 是 Form 字段（不是 Query），必须通过 `data=` 发送。
    如果用 query string，fastapi 会忽略，越界值无法触发 400。
    """
    client = TestClient(app)
    with mock.patch.dict(sys.modules, {"cv2": _FakeCv2()}):
        return client.post(
            "/api/heatmap",
            data={"target_class": str(target_class)},
            files={"image": ("test.png", MINIMAL_PNG_BYTES, "image/png")},
        )


# ==================== Test 1: target_class=0 通过（mock 模式应 200）====================
def test_target_class_0_ok_mock_mode() -> None:
    """target_class=0 → 不应 400（应 200 + mock PNG）。"""
    r = _post_heatmap(0)
    # 校验必须不报 400；模型未加载时 mock 模式返回 200 + png_base64
    assert r.status_code != 400, (
        f"target_class=0 不应 400，实际 {r.status_code}: {r.text[:200]}"
    )
    print(f"\n  ✓ target_class=0 → {r.status_code}")


# ==================== Test 2: target_class=9 通过（边界）====================
def test_target_class_9_ok() -> None:
    """target_class=9（最大合法值）→ 不应 400。"""
    r = _post_heatmap(9)
    assert r.status_code != 400, (
        f"target_class=9 不应 400，实际 {r.status_code}: {r.text[:200]}"
    )
    print(f"\n  ✓ target_class=9（边界）→ {r.status_code}")


# ==================== Test 3: target_class=10 → 400 ====================
def test_target_class_10_rejected() -> None:
    """target_class=10 越界 → 400 + detail 包含范围信息。"""
    r = _post_heatmap(10)
    assert r.status_code == 400, (
        f"target_class=10 应 400，实际 {r.status_code}: {r.text[:200]}"
    )
    body = r.json()
    detail = body.get("detail", "")
    assert "target_class" in str(detail).lower() or "0..9" in str(detail), (
        f"detail 应说明 target_class 范围，实际: {detail}"
    )
    print(f"\n  ✓ target_class=10 → 400, detail={detail}")


# ==================== Test 4: target_class=-1 → 400 ====================
def test_target_class_negative_rejected() -> None:
    """target_class=-1 越界 → 400。"""
    r = _post_heatmap(-1)
    assert r.status_code == 400, (
        f"target_class=-1 应 400，实际 {r.status_code}"
    )
    print(f"\n  ✓ target_class=-1 → 400")


# ==================== Test 5: target_class=100 → 400 ====================
def test_target_class_huge_rejected() -> None:
    """target_class=100 远超界 → 400。"""
    r = _post_heatmap(100)
    assert r.status_code == 400
    print(f"\n  ✓ target_class=100 → 400")


# ==================== Test 6: 全部 10 个合法值循环 ====================
@pytest.mark.parametrize("target_class", list(range(10)))
def test_all_valid_target_classes_accepted(target_class: int) -> None:
    """0..9 全部合法值都不应 400。"""
    r = _post_heatmap(target_class)
    assert r.status_code != 400, (
        f"target_class={target_class} 不应 400，实际 {r.status_code}: {r.text[:200]}"
    )
    print(f"\n  ✓ target_class={target_class} → {r.status_code}")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    """允许 `python tests/test_heatmap_target_class.py` 直接跑。"""
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())

