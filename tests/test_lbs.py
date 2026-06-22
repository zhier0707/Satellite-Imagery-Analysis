"""
高德 LBS 路由 - 单元 + 集成测试
==============================

覆盖 3 类场景：
1. Mock 模式（未配置 AMAP_WEBSERVICE_KEY）→ 6 个端点全部走 fixture + X-LBS-Source: mock
2. 真实模式（配置 Key + httpx MockTransport）→ 解析 AMap 业务返回 + X-LBS-Source: live
3. 鉴权：未登录 401 / 普通 user 调 /share 403 / admin 调 /share 200

运行：
    python -m pytest tests/test_lbs.py tests/test_amap_mock.py -v
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# PowerShell 默认 GBK，先 reconfigure 让 ✓ 符号能打印
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import pytest  # noqa: E402

from backend.services import amap_client as amap_module  # noqa: E402
from backend.services.amap_client import (  # noqa: E402
    AMapClient,
    AMapError,
    MOCK_DIR,
    get_amap_client,
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


@pytest.fixture
def live_client(monkeypatch) -> AMapClient:
    """配置了 Key 的客户端。"""
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "fake_test_key_12345678")
    return AMapClient()


# ==================== Scenario 1: Mock 模式 ====================
class TestMockMode:
    """未配置 AMAP_WEBSERVICE_KEY → 6 个端点全部走 fixture。"""

    @pytest.mark.asyncio
    async def test_geocode_returns_fixture(self, mock_client: AMapClient) -> None:
        data, source = await mock_client.geocode("故宫")
        assert source == "mock", f"source 应为 mock，实际 {source}"
        assert data["status"] == "1"
        assert data["count"] == "10"
        assert len(data["geocodes"]) == 10
        # 校验地址含中文
        assert "故宫" in data["geocodes"][0]["formatted_address"]
        print(f"\n  ✓ mock geocode: {data['geocodes'][0]['formatted_address']}")

    @pytest.mark.asyncio
    async def test_regeocode_returns_fixture(self, mock_client: AMapClient) -> None:
        data, source = await mock_client.regeocode(116.397, 39.918)
        assert source == "mock"
        assert "addressComponent" in data["regeocode"]
        assert "北京市" in data["regeocode"]["formatted_address"]
        print(f"\n  ✓ mock regeocode: {data['regeocode']['formatted_address']}")

    @pytest.mark.asyncio
    async def test_place_text_returns_fixture(self, mock_client: AMapClient) -> None:
        data, source = await mock_client.place_text("西湖", city="杭州")
        assert source == "mock"
        assert len(data["pois"]) == 10
        names = [p["name"] for p in data["pois"]]
        assert "西湖" in names
        print(f"\n  ✓ mock place_text: 命中 {len(data['pois'])} 条 POI")

    @pytest.mark.asyncio
    async def test_place_around_returns_fixture(self, mock_client: AMapClient) -> None:
        """周边搜索 fixture 应 ≥ 5 条 POI（fix-critical-bugs Phase A.4 扩展到 10 条）。"""
        data, source = await mock_client.place_around(116.397, 39.909, radius=1000)
        assert source == "mock"
        assert len(data["pois"]) >= 5, f"fixture POI 应 ≥ 5 条，实际 {len(data['pois'])}"
        # 校验 distance 字段为字符串数字
        for p in data["pois"]:
            assert p["distance"].isdigit()
        # 校验 _mock_meta 标记（Phase A.4 新增：fixture_distances_regenerated）
        assert data.get("_mock_meta", {}).get("reason") == "fixture_distances_regenerated"
        print(f"\n  ✓ mock place_around: {len(data['pois'])} 条周边 (含 _mock_meta)")

    @pytest.mark.asyncio
    async def test_static_map_returns_fixture(self, mock_client: AMapClient) -> None:
        data, source = await mock_client.static_map(116.397, 39.909, zoom=14, size="400*400")
        assert source == "mock"
        assert "url" in data
        assert "amap.mock" in data["url"]
        print(f"\n  ✓ mock static_map: url={data['url'][:50]}...")

    @pytest.mark.asyncio
    async def test_share_returns_fixture(self, mock_client: AMapClient) -> None:
        data, source = await mock_client.share_map(title="我的卫星地图")
        assert source == "mock"
        assert "url" in data
        assert "qrcode_base64" in data
        # qrcode_base64 应是合法 base64（1x1 透明 PNG 解码后长度为固定 67 字节或可被 base64 解码）
        import base64
        decoded = base64.b64decode(data["qrcode_base64"])
        assert decoded.startswith(b"\x89PNG"), f"非 PNG 头: {decoded[:8]}"
        print(f"\n  ✓ mock share: qrcode PNG {len(decoded)} bytes")

    @pytest.mark.asyncio
    async def test_invalid_params(self, mock_client: AMapClient) -> None:
        """参数校验：空地址 / 越界坐标。"""
        with pytest.raises(AMapError) as exc_info:
            await mock_client.geocode("")
        assert exc_info.value.status == 400
        assert exc_info.value.code == "INVALID_PARAM"

        with pytest.raises(AMapError) as exc_info:
            await mock_client.regeocode(200, 0)  # lng 越界
        assert exc_info.value.status == 400
        print("\n  ✓ 参数校验: 空地址/越界坐标 → 400")


# ==================== Scenario 2: 真实模式（httpx MockTransport）====================
class TestLiveMode:
    """配置 AMAP_WEBSERVICE_KEY + httpx MockTransport 模拟 AMap 响应。"""

    @pytest.mark.asyncio
    async def test_geocode_live_parses_response(self, live_client: AMapClient) -> None:
        """真实模式：geocode 走真实 URL + 解析 status=1。"""

        def _mock_transport_handler(request: httpx.Request) -> httpx.Response:
            # 校验 URL 与 query params
            assert str(request.url).startswith("https://restapi.amap.com/v3/geocode/geo")
            assert "key=fake_test_key_12345678" in str(request.url)
            assert "address=test" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "count": "1",
                    "geocodes": [
                        {
                            "formatted_address": "北京市东城区故宫博物院",
                            "location": "116.397026,39.918058",
                        }
                    ],
                },
            )

        live_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_mock_transport_handler),
            timeout=3.0,
        )
        data, source = await live_client.geocode("test")
        assert source == "live"
        assert data["geocodes"][0]["formatted_address"] == "北京市东城区故宫博物院"
        await live_client._client.aclose()
        print(f"\n  ✓ live geocode: source={source}, addr={data['geocodes'][0]['formatted_address']}")

    @pytest.mark.asyncio
    async def test_live_business_error_falls_back_to_mock(self, live_client: AMapClient) -> None:
        """真实模式：业务层 status=0 → 降级到 mock（fix-critical-bugs Phase A.4 新行为）。

        新行为契约：
        - 未配 Key：直接走 mock
        - 配 Key + live 成功：返回 (data, "live")
        - 配 Key + live 失败：返回 (mock_data, "mock")，data._mock_meta 含 fallback 信息
        """

        def _handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "status": "0", "info": "INVALID_USER_KEY", "infocode": "10001",
            })

        live_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_handler), timeout=3.0,
        )
        data, source = await live_client.geocode("test")
        assert source == "mock", f"live 失败应降级到 mock，实际 {source}"
        meta = data.get("_mock_meta", {})
        assert meta.get("fallback_from") == "live_error"
        assert meta.get("fallback_error_code") == "10001"
        await live_client._client.aclose()
        print(f"\n  ✓ live 业务错误降级: source={source}, fallback_code={meta.get('fallback_error_code')}")

    @pytest.mark.asyncio
    async def test_live_network_error_falls_back_to_mock(self, live_client: AMapClient) -> None:
        """真实模式：网络异常 → 降级到 mock。"""

        def _handler(_request: httpx.Request) -> httpx.Response:
            # ConnectError 是 HTTPError 子类，会走 AMAP_NETWORK_ERROR 路径
            raise httpx.ConnectError("simulated connection refused")

        live_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_handler), timeout=3.0,
        )
        data, source = await live_client.geocode("test")
        assert source == "mock", f"网络异常应降级到 mock，实际 {source}"
        meta = data.get("_mock_meta", {})
        assert meta.get("fallback_error_code") == "AMAP_NETWORK_ERROR"
        await live_client._client.aclose()
        print(f"\n  ✓ live 网络异常降级: source={source}, fallback_code={meta.get('fallback_error_code')}")

    @pytest.mark.asyncio
    async def test_live_timeout_falls_back_to_mock(self, live_client: AMapClient) -> None:
        """真实模式：连接超时 → 降级到 mock（语义：用户感知的 API 永远可用）。"""

        def _handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("simulated timeout")

        live_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_handler), timeout=3.0,
        )
        data, source = await live_client.geocode("test")
        assert source == "mock", f"超时应降级到 mock，实际 {source}"
        meta = data.get("_mock_meta", {})
        assert meta.get("fallback_error_code") == "AMAP_TIMEOUT"
        await live_client._client.aclose()
        print(f"\n  ✓ live 超时降级: source={source}, fallback_code={meta.get('fallback_error_code')}")


# ==================== Scenario 3: 鉴权（用 FastAPI TestClient）====================
class TestAuth:
    """未登录 401 / 普通 user 调 /share 403 / admin 调 /share 200。"""

    def _make_test_app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.api.lbs import router as lbs_router
        from backend.main import amap_error_handler
        from fastapi import Request
        from fastapi.responses import JSONResponse

        app = FastAPI()
        app.include_router(lbs_router, prefix="/api/lbs", tags=["lbs"])
        app.add_exception_handler(AMapError, amap_error_handler)
        return app, TestClient(app)

    def test_unauthenticated_returns_401(self) -> None:
        """未带 Authorization → 401。"""
        _, client = self._make_test_app()
        # 注意：FastAPI TestClient 不触发 startup 事件，所以单例 client 是空 key（mock 模式）
        r = client.get("/api/lbs/geocode", params={"address": "test"})
        assert r.status_code == 401, f"应 401，实际 {r.status_code}: {r.text}"
        print(f"\n  ✓ 未鉴权 /geocode: {r.status_code}")

    def test_user_cannot_call_share(self, monkeypatch) -> None:
        """普通 user 调 /share → 403。"""
        # 准备一个 in-memory 测试用户
        from backend.db.base import Base, engine, SessionLocal
        from backend.db.models import User
        from backend.security.password import hash_password
        from backend.security.jwt import create_access_token

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.username == "lbs_tester_user").first()
            if u is None:
                u = User(
                    username="lbs_tester_user",
                    email="lbs_user@test.local",
                    password_hash=hash_password("user123"),
                    role="user",
                    is_active=True,
                )
                db.add(u)
                db.commit()
                db.refresh(u)
            user_token = create_access_token(sub=u.id, role=u.role)
        finally:
            db.close()

        # 用 monkeypatch 强制 client 走 mock（确保不需要真实高德）
        monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)
        amap_module._singleton = None

        _, client = self._make_test_app()
        r = client.post(
            "/api/lbs/share",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"title": "test", "markers": []},
        )
        assert r.status_code == 403, f"应 403，实际 {r.status_code}: {r.text}"
        print(f"\n  ✓ 普通 user 调 /share: {r.status_code}")

    def test_admin_can_call_share(self, monkeypatch) -> None:
        """admin 调 /share → 200 + X-LBS-Source: mock + 合法 body。"""
        from backend.db.base import Base, engine, SessionLocal
        from backend.db.models import User
        from backend.security.password import hash_password
        from backend.security.jwt import create_access_token

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.username == "lbs_tester_admin").first()
            if u is None:
                u = User(
                    username="lbs_tester_admin",
                    email="lbs_admin@test.local",
                    password_hash=hash_password("admin123"),
                    role="admin",
                    is_active=True,
                )
                db.add(u)
                db.commit()
                db.refresh(u)
            admin_token = create_access_token(sub=u.id, role=u.role)
        finally:
            db.close()

        monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)
        amap_module._singleton = None

        _, client = self._make_test_app()
        r = client.post(
            "/api/lbs/share",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "我的卫星地图", "markers": [{"lng": 116.4, "lat": 39.9}]},
        )
        assert r.status_code == 200, f"应 200，实际 {r.status_code}: {r.text}"
        assert r.headers.get("X-LBS-Source") == "mock", f"X-LBS-Source header 缺失或非 mock: {r.headers}"
        body = r.json()
        assert "url" in body and "qrcode_base64" in body
        print(f"\n  ✓ admin 调 /share: 200, X-LBS-Source={r.headers.get('X-LBS-Source')}, url={body['url'][:40]}...")

    def test_user_can_call_geocode_mock(self, monkeypatch) -> None:
        """普通 user 调 /geocode → 200 + X-LBS-Source: mock。"""
        from backend.db.base import Base, engine, SessionLocal
        from backend.db.models import User
        from backend.security.password import hash_password
        from backend.security.jwt import create_access_token

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.username == "lbs_tester_user_geo").first()
            if u is None:
                u = User(
                    username="lbs_tester_user_geo",
                    email="lbs_user_geo@test.local",
                    password_hash=hash_password("user123"),
                    role="user",
                    is_active=True,
                )
                db.add(u)
                db.commit()
                db.refresh(u)
            user_token = create_access_token(sub=u.id, role=u.role)
        finally:
            db.close()

        monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)
        amap_module._singleton = None

        _, client = self._make_test_app()
        r = client.get(
            "/api/lbs/geocode",
            params={"address": "北京"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert r.status_code == 200, f"应 200，实际 {r.status_code}: {r.text}"
        assert r.headers.get("X-LBS-Source") == "mock"
        body = r.json()
        assert body["status"] == "1"
        assert len(body["geocodes"]) >= 5
        print(f"\n  ✓ user 调 /geocode: 200, {len(body['geocodes'])} 条 mock 数据")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    """允许 `python tests/test_lbs.py` 直接跑（兼容旧测试风格）。"""
    import subprocess
    rc = subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
