"""
热力图 mock fallback 测试
=========================

验证 backend/api/classify.py 的修复目标：
- ``cv2`` 不可用时（mock 注入）→ 端点应能**回退到 PIL/纯 Python 路径**生成 mock PNG
- 始终返回 ``png_base64`` 非空 + ``mock: true``（模型未加载场景）
- ``target_class`` 边界值（0、9）不应触发 400

设计要点
--------
- 不启 uvicorn；用 FastAPI ``TestClient`` + ``dependency_overrides`` 注入假 user
- 用 ``mock.patch.dict(sys.modules, {"cv2": ...})`` 控制 cv2 是否可用
- 模型未加载 = 默认场景（``MODEL_WEIGHTS`` 不指向真实权重）
- 1×1 最小 PNG 用 PIL 生成（避免手写 header 出错）

运行：
    cd e:\\truth-视觉实践
    python -m pytest tests/test_heatmap_mock_fallback.py -v
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from unittest import mock

# PowerShell 默认 GBK，先 reconfigure 让 ✓ 符号能打印
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

from backend.api import classify as classify_mod  # noqa: E402
from backend.api.classify import router as classify_router  # noqa: E402
from backend.db.base import Base, SessionLocal, engine  # noqa: E402
from backend.db.models import User  # noqa: E402
from backend.security.deps import get_current_user  # noqa: E402
from backend.security.password import hash_password  # noqa: E402


# ==================== 测试应用 ====================
app = FastAPI()
app.include_router(classify_router, prefix="/api", tags=["classify"])


# ==================== 1×1 PNG fixture ====================
def _make_png_bytes() -> bytes:
    """生成一个 64×64 RGB 图像的 PNG 字节流（用 PIL）。"""
    from PIL import Image
    img = Image.new("RGB", (64, 64), (100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MINIMAL_PNG_BYTES = _make_png_bytes()


# ==================== 伪 cv2 模块（正常情况）====================
class _FakeBuf:
    """最小 cv2.imencode 输出替身：buf.tobytes() 即可被 base64 编码。"""

    def tobytes(self) -> bytes:
        # 32 字节填充：base64 编码后大约 44 字符
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class _FakeCv2:
    """正常 cv2 替身：imencode 返回可被 base64 编码的「带 tobytes() 的对象」。"""

    @staticmethod
    def imencode(_ext: str, _arr) -> tuple[bool, _FakeBuf]:
        return True, _FakeBuf()


# ==================== 伪 cv2 模块（异常情况：模拟 cv2 不可用）====================
class _BrokenCv2:
    """模拟 cv2 不可用：``imencode`` 抛 ImportError。

    用 ``mock.patch.dict(sys.modules, {"cv2": _BrokenCv2()})`` 注入后，
    端点内的 ``__import__("cv2").imencode(...)`` 会失败，
    期望修复后的端点能自动 fallback 到 PIL 路径。
    """

    @staticmethod
    def imencode(*_args, **_kwargs):
        raise ImportError("simulated cv2 unavailable")


# ==================== Fixtures ====================
@pytest.fixture(autouse=True)
def _setup_test_user():
    """准备一个测试用户，并设置 dependency override。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "mock_fallback_tester").first()
        if u is None:
            u = User(
                username="mock_fallback_tester",
                email="mock_fallback@test.local",
                password_hash=hash_password("mock123"),
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


# ==================== Helper ====================
def _post_heatmap_with_cv2(target_class: int, cv2_module):
    """POST /api/heatmap，注入指定的 cv2 模块（None 表示注入不可用版本）。"""
    client = TestClient(app)
    with mock.patch.dict(sys.modules, {"cv2": cv2_module}):
        return client.post(
            "/api/heatmap",
            data={"target_class": str(target_class)},
            files={"image": ("test.png", MINIMAL_PNG_BYTES, "image/png")},
        )


def _post_heatmap_with_cv2_unavailable(target_class: int):
    """POST /api/heatmap，强制走 ``CV2_AVAILABLE=False`` 分支（PIL fallback）。

    修复目标：``backend.api.classify.CV2_AVAILABLE = False`` 时
    端点用 PIL 兜底生成 PNG。
    """
    client = TestClient(app)
    with mock.patch.object(classify_mod, "CV2_AVAILABLE", False), \
         mock.patch.dict(sys.modules, {"cv2": _BrokenCv2()}):
        return client.post(
            "/api/heatmap",
            data={"target_class": str(target_class)},
            files={"image": ("test.png", MINIMAL_PNG_BYTES, "image/png")},
        )


# ==================== Test 1: cv2 不可用时仍应返回 mock PNG ====================
def test_heatmap_returns_png_without_cv2() -> None:
    """模拟 cv2 不可用 + 模型未加载 → 端点应能 fallback 并返回 200 + mock=True。

    修复目标：``CV2_AVAILABLE=False`` 时端点用 PIL 兜底生成 PNG。
    """
    r = _post_heatmap_with_cv2_unavailable(target_class=0)

    # 期望：200 + png_base64 非空 + mock=True
    assert r.status_code == 200, (
        f"cv2 不可用时端点应 200，实际 {r.status_code}: {r.text[:300]}"
    )
    body = r.json()
    assert "png_base64" in body, f"响应缺 png_base64: {body}"
    assert isinstance(body["png_base64"], str), "png_base64 应为字符串"
    assert len(body["png_base64"]) > 0, "png_base64 不应为空"

    # 验证 base64 可解码且确实是 PNG（首 8 字节是 PNG header）
    try:
        decoded = base64.b64decode(body["png_base64"])
        assert len(decoded) > 0, "base64 解码后字节数应 > 0"
        # PNG magic: 89 50 4E 47 0D 0A 1A 0A
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n", (
            f"PIL fallback 生成的 PNG header 不对: {decoded[:8]!r}"
        )
    except Exception as e:
        raise AssertionError(f"png_base64 不是合法 base64: {e}")

    assert body.get("mock") is True, f"应 mock=True，实际 {body.get('mock')}"
    print(f"\n  ✓ cv2 不可用时 fallback 成功: status=200, png_base64 长度={len(body['png_base64'])}, "
          f"已验证 PNG header")


# ==================== Test 2: cv2 可用时 mock 模式正常返回 ====================
def test_heatmap_with_real_cv2() -> None:
    """cv2 可用 + 模型未加载 → 应走 cv2 mock 分支，200 + png_base64 非空 + mock=True。"""
    r = _post_heatmap_with_cv2(target_class=0, cv2_module=_FakeCv2())

    assert r.status_code == 200, (
        f"cv2 可用 + mock 模式应 200，实际 {r.status_code}: {r.text[:300]}"
    )
    body = r.json()
    assert "png_base64" in body, f"响应缺 png_base64: {body}"
    assert len(body["png_base64"]) > 0, "png_base64 不应为空"
    assert body.get("mock") is True, f"应 mock=True，实际 {body.get('mock')}"

    # base64 必能解码
    decoded = base64.b64decode(body["png_base64"])
    assert len(decoded) > 0
    print(f"\n  ✓ cv2 可用 + mock 模式: status=200, png_base64 长度={len(body['png_base64'])}, "
          f"mock={body['mock']}")


# ==================== Test 3: target_class 边界值 0 和 9 都不应 400 ====================
def test_heatmap_target_class_boundary() -> None:
    """target_class=0（最小）和 target_class=9（最大）都不应触发 400。

    模型未加载 + cv2 mock 时，端点应在第一行范围校验后走到 mock 路径。
    """
    for tc in (0, 9):
        r = _post_heatmap_with_cv2(target_class=tc, cv2_module=_FakeCv2())
        assert r.status_code != 400, (
            f"target_class={tc} 不应 400，实际 {r.status_code}: {r.text[:300]}"
        )
        assert r.status_code == 200, (
            f"target_class={tc} 应 200，实际 {r.status_code}: {r.text[:300]}"
        )
        body = r.json()
        assert body.get("mock") is True, f"target_class={tc} 应 mock=True"
        assert len(body.get("png_base64", "")) > 0, (
            f"target_class={tc} png_base64 不应为空"
        )
        print(f"\n  ✓ target_class={tc} (边界) → status=200, mock={body['mock']}, "
              f"png_base64 长度={len(body['png_base64'])}")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    """允许 ``python tests/test_heatmap_mock_fallback.py`` 直接跑。"""
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())
