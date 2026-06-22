"""
周边搜索 mock 距离重算（haversine）测试
======================================

覆盖 Phase D.2 的修复：
- `backend/services/amap_client.py` 的 `_haversine_m` + `_regenerate_place_around_distances`
  按真实经纬度重算 mock fixture 的 distance 字段
- `backend/data/lbs_mock/place_around.json` 扩充到 10 条 POI
- 响应头 `X-LBS-Mock-Reason: fixture_distances_regenerated`

测试要点：
1. **haversine 基础** - 已知两点的距离（天安门 → 故宫粗估 1700m）
2. **mock 距离重算** - distance 是非空数字字符串（米），且范围合理
3. **fixture 数量** - 返回 10 条 POI（不是旧版 5 条）
4. **X-LBS-Mock-Reason 响应头** - 在 lbs 路由 mock 模式下应存在
5. **fixture 隔离** - 多次调用不污染原始 fixture dict

运行：
    cd e:\truth-视觉实践
    python -m pytest tests/test_place_around_mock.py -v
"""
from __future__ import annotations

import asyncio
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

from backend.services import amap_client as amap_module  # noqa: E402
from backend.services.amap_client import (  # noqa: E402
    MOCK_DIR,
    AMapClient,
    _haversine_m,
    _regenerate_place_around_distances,
)


# ==================== Fixtures ====================
@pytest.fixture(autouse=True)
def _reset_amap_singleton():
    """每个测试前后清空单例，避免 key 状态污染。"""
    amap_module._singleton = None
    yield
    amap_module._singleton = None


@pytest.fixture
def mock_client(monkeypatch) -> AMapClient:
    """未配置 Key 的客户端。"""
    monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)
    return AMapClient()


# ==================== Test 1: haversine 基础 ====================
def test_haversine_basic() -> None:
    """天安门到故宫，距离粗估 1500-2000 米。

    天安门 (116.397, 39.909)
    故宫 (116.397, 39.924)
    距离 ≈ 15*111000 = 1665 米
    """
    d = _haversine_m(116.397, 39.909, 116.397, 39.924)
    assert 1500 < d < 2000, f"距离应 1500-2000m，实际 {d:.1f}"
    print(f"\n  ✓ haversine 天安门→故宫 = {d:.1f} m")


def test_haversine_zero_distance() -> None:
    """同一点距离 = 0。"""
    d = _haversine_m(116.40, 39.91, 116.40, 39.91)
    assert d < 0.001, f"同一点距离应 ≈ 0，实际 {d}"
    print(f"\n  ✓ haversine 同点 = {d:.6f} m")


def test_haversine_known_distance() -> None:
    """1 度纬度 ≈ 111 km（赤道附近精确，高纬度略大）。"""
    # 沿同一经线移动 1 度纬度
    d = _haversine_m(116.40, 39.91, 116.40, 40.91)
    expected = 111_000.0  # 1 度纬度 ≈ 111km
    # 允许 ±1% 误差
    assert abs(d - expected) / expected < 0.01, (
        f"1 度纬度应≈{expected}m，实际 {d:.1f}m"
    )
    print(f"\n  ✓ haversine 1°纬度 = {d:.1f} m (expected≈{expected})")


# ==================== Test 2: fixture 数量 = 10 条 ====================
def test_fixture_place_around_has_10_pois() -> None:
    """place_around.json 应有 10 条 POI（不是旧版 5 条）。"""
    data = json.loads((MOCK_DIR / "place_around.json").read_text(encoding="utf-8"))
    assert "pois" in data
    assert len(data["pois"]) == 10, f"POI 应 10 条，实际 {len(data['pois'])}"
    print(f"\n  ✓ place_around.json 含 10 条 POI")


# ==================== Test 3: mock 距离重算（单元）====================
def test_regenerate_distances_unit() -> None:
    """_regenerate_place_around_distances 单元函数：distance 变成整数字符串。"""
    fixture = {
        "status": "1",
        "count": "2",
        "pois": [
            {"id": "A", "name": "A", "location": "116.40,39.91", "distance": ""},
            {"id": "B", "name": "B", "location": "116.41,39.92", "distance": ""},
        ],
    }
    out = _regenerate_place_around_distances(fixture, 116.40, 39.91)
    assert len(out["pois"]) == 2
    # distance 应是非空整数字符串
    for p in out["pois"]:
        assert p["distance"] != "", f"distance 应被填充: {p}"
        assert p["distance"].isdigit()
    # 第一条是自己，距离应 ≈ 0
    poi_a = next(p for p in out["pois"] if p["id"] == "A")
    assert int(poi_a["distance"]) < 5, (
        f"POI A 与中心同点距离应≈0，实际 {poi_a['distance']}"
    )
    # 元信息标记
    assert out.get("_mock_meta", {}).get("reason") == "fixture_distances_regenerated"
    print(f"\n  ✓ 重算单元函数 OK: A={poi_a['distance']}m, "
          f"meta={out['_mock_meta']['reason']}")


# ==================== Test 4: 重算不污染原 fixture ====================
def test_regenerate_does_not_mutate_fixture() -> None:
    """多次调用后，原 fixture dict 保持不变。"""
    original = json.loads((MOCK_DIR / "place_around.json").read_text(encoding="utf-8"))
    # 备份原始 distance 字段
    orig_distances = [p.get("distance", "") for p in original["pois"]]
    # 第一次重算
    out1 = _regenerate_place_around_distances(original, 116.40, 39.91)
    # 第二次重算（不同中心）
    out2 = _regenerate_place_around_distances(original, 116.50, 39.95)
    # 原 fixture 距离应未变
    cur_distances = [p.get("distance", "") for p in original["pois"]]
    assert cur_distances == orig_distances, (
        f"原 fixture 被污染: {cur_distances} vs {orig_distances}"
    )
    # 两次重算的 distance 应不同（中心变了）
    d1 = [int(p["distance"]) for p in out1["pois"]]
    d2 = [int(p["distance"]) for p in out2["pois"]]
    assert d1 != d2, f"两次重算结果应不同: {d1} vs {d2}"
    print(f"\n  ✓ 原 fixture 未污染, 两次重算结果不同")


# ==================== Test 5: 集成 - mock 模式 distance 重算 ====================
def test_place_around_mock_distance_regenerated(mock_client: AMapClient) -> None:
    """集成：mock 模式下 distance 按真实经纬度重算。"""
    data, source = asyncio.run(
        mock_client.place_around(lng=116.40, lat=39.91, radius=1000, types="050000")
    )
    assert source == "mock", f"source 应为 mock，实际 {source}"
    assert "pois" in data
    assert len(data["pois"]) == 10, f"POI 应 10 条，实际 {len(data['pois'])}"
    for poi in data["pois"]:
        assert poi.get("distance", "") != "", (
            f"POI distance 应被重算: {poi.get('name')}"
        )
        # 距离是字符串数字
        assert poi["distance"].isdigit(), (
            f"distance 非数字: {poi['distance']}"
        )
        d = int(poi["distance"])
        assert 0 <= d <= 50_000, f"POI 距离越界: {d}"
    # _mock_meta 标记存在
    assert data.get("_mock_meta", {}).get("reason") == "fixture_distances_regenerated"
    print(f"\n  ✓ mock 模式: 10 条 POI, distance 全部重算, "
          f"meta={data['_mock_meta']['reason']}")


# ==================== Test 6: 集成 - 路由层 X-LBS-Mock-Reason 头 ====================
def test_lbs_route_sets_x_lbs_mock_reason(monkeypatch) -> None:
    """路由层：mock 模式应设置 X-LBS-Mock-Reason: fixture_distances_regenerated。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.lbs import router as lbs_router
    from backend.main import amap_error_handler
    from backend.security.deps import get_current_user
    from backend.db.models import User
    from backend.db.base import SessionLocal
    from backend.security.jwt import create_access_token

    # 强制 mock（无 Key）
    monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)
    amap_module._singleton = None

    # 准备一个测试 user 拿 token
    Base = __import__("backend.db.base", fromlist=["Base"]).Base
    Base.metadata.create_all(
        bind=__import__("backend.db.base", fromlist=["engine"]).engine
    )
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "lbs_tester_around").first()
        if u is None:
            u = User(
                username="lbs_tester_around",
                email="lbs_around@test.local",
                password_hash=__import__("backend.security.password",
                                         fromlist=["hash_password"]).hash_password("u123"),
                role="user",
                is_active=True,
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        token = create_access_token(sub=u.id, role=u.role)
    finally:
        db.close()

    app = FastAPI()
    app.include_router(lbs_router, prefix="/api/lbs", tags=["lbs"])
    app.add_exception_handler(
        __import__("backend.services.amap_client",
                   fromlist=["AMapError"]).AMapError,
        amap_error_handler,
    )

    client = TestClient(app)
    r = client.get(
        "/api/lbs/place/around",
        params={"lng": 116.40, "lat": 39.91, "radius": 1000, "types": "050000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"应 200，实际 {r.status_code}: {r.text[:200]}"
    assert r.headers.get("X-LBS-Source") == "mock"
    assert r.headers.get("X-LBS-Mock-Reason") == "fixture_distances_regenerated", (
        f"X-LBS-Mock-Reason 应为 fixture_distances_regenerated, "
        f"实际 {r.headers.get('X-LBS-Mock-Reason')}"
    )
    print(f"\n  ✓ 路由头 X-LBS-Mock-Reason = {r.headers.get('X-LBS-Mock-Reason')}")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    """允许 `python tests/test_place_around_mock.py` 直接跑。"""
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())
