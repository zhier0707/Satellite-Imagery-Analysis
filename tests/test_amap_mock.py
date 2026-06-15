"""
Mock fixture 文件 - 存在性 + 合法性测试
======================================

验证 `backend/data/lbs_mock/` 下的 6 个 JSON：
- 文件存在
- 是合法 JSON
- 顶层 key 符合预期（模拟 AMap 业务返回）

运行：
    python -m pytest tests/test_amap_mock.py -v
"""
from __future__ import annotations

import json
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

from backend.services.amap_client import MOCK_DIR  # noqa: E402


# ==================== 期望的 fixture 清单 ====================
EXPECTED_FIXTURES = {
    "geocode.json": {
        "required_top_keys": {"status", "info", "infocode", "count", "geocodes"},
        "min_count": 5,
        "min_geocodes": 5,
    },
    "regeocode.json": {
        "required_top_keys": {"status", "info", "infocode", "regeocode"},
        "min_regeocode_components": {"country", "province", "city"},
    },
    "place_text.json": {
        "required_top_keys": {"status", "info", "infocode", "count", "pois"},
        "min_count": 5,
        "min_pois": 5,
    },
    "place_around.json": {
        "required_top_keys": {"status", "info", "infocode", "count", "pois"},
        "min_count": 3,
        "min_pois": 3,
    },
    "static_map.json": {
        "required_top_keys": {"url", "zoom", "size"},
    },
    "share.json": {
        "required_top_keys": {"url", "qrcode_base64"},
    },
}


# ==================== Tests ====================
def test_mock_dir_exists() -> None:
    """fixture 目录存在。"""
    assert MOCK_DIR.is_dir(), f"Mock 目录不存在: {MOCK_DIR}"
    print(f"\n  ✓ mock 目录存在: {MOCK_DIR}")


@pytest.mark.parametrize("filename", list(EXPECTED_FIXTURES.keys()))
def test_fixture_file_exists(filename: str) -> None:
    """每个 fixture 文件存在。"""
    path = MOCK_DIR / filename
    assert path.is_file(), f"Fixture 缺失: {path}"
    size = path.stat().st_size
    assert size > 0, f"Fixture 为空: {path}"
    print(f"  ✓ {filename} 存在, {size} bytes")


@pytest.mark.parametrize("filename", list(EXPECTED_FIXTURES.keys()))
def test_fixture_is_valid_json(filename: str) -> None:
    """每个 fixture 是合法 JSON。"""
    path = MOCK_DIR / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        pytest.fail(f"{filename} 不是合法 JSON: {e}")
    assert isinstance(data, dict), f"{filename} 顶层应为 dict"
    print(f"  ✓ {filename} 合法 JSON, 顶层 keys={list(data.keys())[:5]}")


@pytest.mark.parametrize("filename,expected", list(EXPECTED_FIXTURES.items()))
def test_fixture_top_level_keys(filename: str, expected: dict) -> None:
    """校验 fixture 顶层 key 符合预期。"""
    data = json.loads((MOCK_DIR / filename).read_text(encoding="utf-8"))
    required = expected["required_top_keys"]
    missing = required - set(data.keys())
    assert not missing, f"{filename} 缺失 keys: {missing}"
    print(f"  ✓ {filename} 含全部 {len(required)} 个 expected keys")


def test_geocode_has_enough_samples() -> None:
    """geocode.json 至少 5 条地址示例（spec 要求 10，宽松到 5）。"""
    data = json.loads((MOCK_DIR / "geocode.json").read_text(encoding="utf-8"))
    geocodes = data.get("geocodes", [])
    assert len(geocodes) >= 5, f"geocode 数量不足: {len(geocodes)}"
    # 每条至少有 location 字段
    for g in geocodes:
        assert "location" in g
        assert "formatted_address" in g
    print(f"  ✓ geocode.json 含 {len(geocodes)} 条地址")


def test_place_text_has_enough_samples() -> None:
    """place_text.json 至少 5 条 POI。"""
    data = json.loads((MOCK_DIR / "place_text.json").read_text(encoding="utf-8"))
    pois = data.get("pois", [])
    assert len(pois) >= 5, f"POI 数量不足: {len(pois)}"
    for p in pois:
        assert "name" in p and "location" in p
    print(f"  ✓ place_text.json 含 {len(pois)} 条 POI")


def test_place_around_has_enough_samples() -> None:
    """place_around.json 至少 3 条周边。"""
    data = json.loads((MOCK_DIR / "place_around.json").read_text(encoding="utf-8"))
    pois = data.get("pois", [])
    assert len(pois) >= 3, f"周边 POI 数量不足: {len(pois)}"
    for p in pois:
        assert "distance" in p
    print(f"  ✓ place_around.json 含 {len(pois)} 条周边")


def test_share_qrcode_is_valid_base64() -> None:
    """share.json 的 qrcode_base64 是合法 base64 PNG。"""
    import base64
    data = json.loads((MOCK_DIR / "share.json").read_text(encoding="utf-8"))
    qr = data["qrcode_base64"]
    decoded = base64.b64decode(qr)
    assert decoded.startswith(b"\x89PNG"), f"qrcode_base64 非 PNG 格式: {decoded[:8]}"
    print(f"  ✓ share.json qrcode 是合法 PNG, {len(decoded)} bytes")


def test_regeocode_has_address_components() -> None:
    """regeocode.json 至少含 country/province/city 三件套。"""
    data = json.loads((MOCK_DIR / "regeocode.json").read_text(encoding="utf-8"))
    addr = data["regeocode"]["addressComponent"]
    for k in ("country", "province", "city"):
        assert k in addr, f"regeocode 缺 {k}"
        assert addr[k], f"regeocode {k} 为空"
    print(f"  ✓ regeocode.json 含 country/province/city")


def test_static_map_has_url() -> None:
    """static_map.json 含 url 字段。"""
    data = json.loads((MOCK_DIR / "static_map.json").read_text(encoding="utf-8"))
    assert data["url"], "static_map url 为空"
    assert isinstance(data["zoom"], int)
    print(f"  ✓ static_map.json url 合法, zoom={data['zoom']}")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())
