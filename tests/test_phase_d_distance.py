"""Phase D.2 行为测试 - haversine + 距离重算
不依赖 FastAPI app 启动;直接调工具函数
"""
import json
import math
import sys
from pathlib import Path

# 路径准备
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.amap_client import (
    _haversine_m,
    _parse_lng_lat,
    _regenerate_place_around_distances,
)


def test_haversine_tiananmen_to_wangfujing() -> None:
    """天安门 → 王府井:大约 1.3 ~ 1.6 km"""
    d = _haversine_m(116.397428, 39.90923, 116.412136, 39.916906)
    assert 1300 < d < 1700, f"distance {d:.1f} not in expected range"
    print(f"[OK] haversine tiananmen -> wangfujing: {d:.1f} m")


def test_haversine_same_point_is_zero() -> None:
    d = _haversine_m(116.0, 39.0, 116.0, 39.0)
    assert d < 1e-6, f"distance {d} should be 0"
    print(f"[OK] haversine same point: {d} m")


def test_haversine_known_distance() -> None:
    """赤道 1 度经度 ≈ 111.32 km"""
    d = _haversine_m(0, 0, 1, 0)
    assert 111000 < d < 111700, f"distance {d:.1f} m not close to 111.32 km"
    print(f"[OK] haversine equator 1 deg: {d:.1f} m (expect ~111320)")


def test_parse_lng_lat_valid() -> None:
    loc = _parse_lng_lat("116.412136,39.916906")
    assert loc is not None
    assert abs(loc[0] - 116.412136) < 1e-6
    assert abs(loc[1] - 39.916906) < 1e-6
    print(f"[OK] parse '116.412136,39.916906' -> {loc}")


def test_parse_lng_lat_invalid() -> None:
    assert _parse_lng_lat("not_a_coord") is None
    assert _parse_lng_lat("") is None
    assert _parse_lng_lat(None) is None
    print(f"[OK] parse invalid -> None")


def test_regenerate_distances_from_fixture() -> None:
    """加载 10 条 POI fixture,按中心点 (116.397428, 39.90923) 重算 distance"""
    path = ROOT / "backend" / "data" / "lbs_mock" / "place_around.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["pois"]) == 10, f"fixture has {len(data['pois'])} POIs, expect 10"

    enriched = _regenerate_place_around_distances(data, 116.397428, 39.90923)
    assert enriched["count"] == "10"
    # mock_meta 标记
    assert enriched["_mock_meta"]["reason"] == "fixture_distances_regenerated"
    assert enriched["_mock_meta"]["distance_formula"] == "haversine"
    # 距离应是非负整数
    for p in enriched["pois"]:
        d = p["distance"]
        assert d != ""
        n = int(d)
        assert n >= 0
    # 已按距离升序排
    distances = [int(p["distance"]) for p in enriched["pois"]]
    assert distances == sorted(distances), f"not sorted: {distances}"
    print(f"[OK] regen 10 POIs; distances={distances[:3]}...; sorted=True")


if __name__ == "__main__":
    test_haversine_tiananmen_to_wangfujing()
    test_haversine_same_point_is_zero()
    test_haversine_known_distance()
    test_parse_lng_lat_valid()
    test_parse_lng_lat_invalid()
    test_regenerate_distances_from_fixture()
    print("\nALL TESTS PASSED")
