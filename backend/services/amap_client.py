"""
高德 Web 服务统一客户端
======================

设计要点
--------
- 全部使用异步 HTTP（httpx.AsyncClient），进程级单例复用连接
- 统一超时 3.0 秒：避免单点慢请求拖垮整个 API
- 未配置 `AMAP_WEBSERVICE_KEY` 时，自动回退到 `backend/data/lbs_mock/` 下的 fixture，
  前端无需感知差异，调试 / 离线开发友好
- 任何失败统一抛 `AMapError`，由 `backend.main` 的 exception handler 转为 502

调用方约定
----------
- `from backend.services.amap_client import AMapClient, AMapError`
- `client = AMapClient()` 后调用 `await client.geocode(...)`
- 每个方法返回 `tuple[dict, str]`：`(data, source)`，source 取值 `"live"` 或 `"mock"`
- 失败抛 `AMapError(status, code, message)`，status 默认 502
"""
from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Callable

import httpx

log = logging.getLogger(__name__)

# ==================== 常量 ====================
AMAP_BASE = "https://restapi.amap.com/v3"
DEFAULT_TIMEOUT_S = 3.0
SOURCE_MOCK = "mock"
SOURCE_LIVE = "live"

# fixture 文件名映射：method 内部把 endpoint 转成 fixture key
_FIXTURE_KEYS = {
    "geocode": "geocode",
    "regeocode": "regeocode",
    "place_text": "place_text",
    "place_around": "place_around",
    "static_map": "static_map",
    "share_map": "share",
}

# fixture 目录：backend/data/lbs_mock/
_BACKEND_DIR = Path(__file__).resolve().parent.parent
MOCK_DIR = _BACKEND_DIR / "data" / "lbs_mock"


# ==================== 异常 ====================
class AMapError(Exception):
    """高德调用失败统一异常。

    参数
    ----
    status : int
        HTTP 状态码（默认 502 Bad Gateway）
    code : str
        高德返回的状态码 / 业务错误码（如 "INVALID_USER_KEY"、"NETWORK_TIMEOUT"）
    message : str
        对人可读的错误描述（中文）
    """

    def __init__(self, status: int = 502, code: str = "AMAP_ERROR", message: str = ""):
        self.status = status
        self.code = code
        self.message = message or "高德 Web 服务调用失败"
        super().__init__(f"[{code}] {self.message}")


# ==================== 客户端 ====================
class AMapClient:
    """异步高德 Web 服务客户端（单例）。"""

    def __init__(self) -> None:
        self._key: str = os.environ.get("AMAP_WEBSERVICE_KEY", "").strip()
        self._client: httpx.AsyncClient | None = None

    @property
    def key(self) -> str:
        return self._key

    @property
    def is_configured(self) -> bool:
        return bool(self._key)

    async def _get_client(self) -> httpx.AsyncClient:
        """惰性创建并复用单例。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT_S,
                headers={"User-Agent": "satellite-image-amap/1.0"},
            )
        return self._client

    async def aclose(self) -> None:
        """应用关闭时释放连接（FastAPI lifespan 钩子调用）。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ==================== 内部工具 ====================
    def _load_fixture(self, key: str) -> dict:
        """从 fixture 读取 mock 数据。文件不存在 → 抛 AMapError。"""
        path = MOCK_DIR / f"{key}.json"
        if not path.is_file():
            raise AMapError(
                status=500,
                code="MOCK_FIXTURE_MISSING",
                message=f"Mock 兜底 fixture 缺失: {path.name}",
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise AMapError(
                status=500,
                code="MOCK_FIXTURE_INVALID",
                message=f"Mock fixture 解析失败: {path.name} - {e}",
            )

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        fixture_key: str,
    ) -> tuple[dict, str]:
        """统一请求：未配 Key → mock；配 Key → 真实请求 + 失败转 502。"""
        if not self.is_configured:
            log.debug("AMAP_WEBSERVICE_KEY 未配置，使用 mock fixture: %s", fixture_key)
            return self._load_fixture(fixture_key), SOURCE_MOCK

        url = f"{AMAP_BASE}/{endpoint}"
        params = {**params, "key": self._key, "output": "JSON"}
        try:
            client = await self._get_client()
            resp = await client.get(url, params=params)
        except httpx.TimeoutException as e:
            raise AMapError(
                status=504,
                code="AMAP_TIMEOUT",
                message=f"高德请求超时: {endpoint} - {e}",
            )
        except httpx.HTTPError as e:
            raise AMapError(
                status=502,
                code="AMAP_NETWORK_ERROR",
                message=f"高德网络异常: {endpoint} - {e}",
            )

        if resp.status_code != 200:
            raise AMapError(
                status=502,
                code=f"AMAP_HTTP_{resp.status_code}",
                message=f"高德返回非 200: {resp.status_code}",
            )

        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            raise AMapError(
                status=502,
                code="AMAP_BAD_JSON",
                message=f"高德返回非 JSON: {e}",
            )

        # 高德业务层 status: 1=成功, 0=失败
        if str(data.get("status")) != "1":
            raise AMapError(
                status=502,
                code=str(data.get("infocode", "AMAP_BUSINESS_ERROR")),
                message=str(data.get("info", "高德业务错误")),
            )
        return data, SOURCE_LIVE

    async def _request_with_fallback(
        self,
        endpoint: str,
        params: dict[str, Any],
        fixture_key: str,
        postprocess: Callable[[dict], dict] | None = None,
    ) -> tuple[dict, str]:
        """统一请求（带降级）：已配 Key 时先 live，失败回退到 mock。

        行为
        ----
        - 未配 Key：直接走 mock（不附加 fallback 标记）
        - 配 Key 且 live 成功：返回 (data, "live")
        - 配 Key 且 live 失败（任意 AMapError）：返回 (mock_data, "mock")，
          在 data._mock_meta 上追加 fallback_from / fallback_error_code / fallback_error_message
        """
        if not self.is_configured:
            log.debug("AMAP_WEBSERVICE_KEY 未配置，使用 mock fixture: %s", fixture_key)
            data = self._load_fixture(fixture_key)
            if postprocess is not None:
                data = postprocess(data)
            return data, SOURCE_MOCK

        try:
            return await self._request(endpoint, params, fixture_key)
        except AMapError as e:
            log.warning("AMAP live 失败，降级到 mock [%s]: %s", fixture_key, e)
            data = self._load_fixture(fixture_key)
            if postprocess is not None:
                data = postprocess(data)
            # 标记降级（保留 postprocess 已设置的 _mock_meta 字段，如 distance 公式等）
            meta = dict(data.get("_mock_meta") or {})
            meta["fallback_from"] = "live_error"
            meta["fallback_error_code"] = e.code
            meta["fallback_error_message"] = e.message
            data["_mock_meta"] = meta
            return data, SOURCE_MOCK

    # ==================== 6 个业务方法 ====================
    async def geocode(self, address: str) -> tuple[dict, str]:
        """正向地理编码：地址 → 经纬度。配 Key 但 live 失败时自动降级到 mock。"""
        address = (address or "").strip()
        if not address:
            raise AMapError(status=400, code="INVALID_PARAM", message="address 不能为空")
        return await self._request_with_fallback(
            "geocode/geo",
            {"address": address},
            _FIXTURE_KEYS["geocode"],
        )

    async def regeocode(self, lng: float, lat: float) -> tuple[dict, str]:
        """逆地理编码：经纬度 → 地址。配 Key 但 live 失败时自动降级到 mock。"""
        try:
            lng_f, lat_f = float(lng), float(lat)
        except (TypeError, ValueError):
            raise AMapError(status=400, code="INVALID_PARAM", message="lng/lat 必须为数字")
        if not (-180 <= lng_f <= 180) or not (-90 <= lat_f <= 90):
            raise AMapError(status=400, code="INVALID_PARAM", message="lng/lat 超出合法范围")
        return await self._request_with_fallback(
            "geocode/regeo",
            {"location": f"{lng_f},{lat_f}", "extensions": "base"},
            _FIXTURE_KEYS["regeocode"],
        )

    async def place_text(
        self,
        keywords: str,
        city: str | None = None,
        offset: int = 20,
    ) -> tuple[dict, str]:
        """POI 关键字搜索。配 Key 但 live 失败时自动降级到 mock。"""
        keywords = (keywords or "").strip()
        if not keywords:
            raise AMapError(status=400, code="INVALID_PARAM", message="keywords 不能为空")
        offset = max(1, min(int(offset or 20), 50))
        params: dict[str, Any] = {"keywords": keywords, "offset": str(offset), "page": "1"}
        if city:
            params["city"] = city.strip()
        return await self._request_with_fallback(
            "place/text",
            params,
            _FIXTURE_KEYS["place_text"],
        )

    async def place_around(
        self,
        lng: float,
        lat: float,
        radius: int = 1000,
        types: str | None = None,
    ) -> tuple[dict, str]:
        """周边搜索。配 Key 但 live 失败时自动降级到 mock，并按真实经纬度重算 distance。"""
        try:
            lng_f, lat_f = float(lng), float(lat)
        except (TypeError, ValueError):
            raise AMapError(status=400, code="INVALID_PARAM", message="lng/lat 必须为数字")
        radius = max(50, min(int(radius or 1000), 50000))
        params: dict[str, Any] = {
            "location": f"{lng_f},{lat_f}",
            "radius": str(radius),
            "offset": "25",
            "page": "1",
        }
        if types:
            params["types"] = types.strip()
        return await self._request_with_fallback(
            "place/around",
            params,
            _FIXTURE_KEYS["place_around"],
            postprocess=lambda data: _regenerate_place_around_distances(data, lng_f, lat_f),
        )

    async def static_map(
        self,
        lng: float,
        lat: float,
        zoom: int = 14,
        size: str = "400*400",
    ) -> tuple[dict, str]:
        """生成静态图 URL（不直接下载图片，返回 URL 供前端 `<img>` 使用）。"""
        try:
            lng_f, lat_f = float(lng), float(lat)
        except (TypeError, ValueError):
            raise AMapError(status=400, code="INVALID_PARAM", message="lng/lat 必须为数字")
        zoom = max(1, min(int(zoom or 14), 18))
        # 真实模式：拼 URL
        if self.is_configured:
            url = (
                f"https://restapi.amap.com/v3/staticmap"
                f"?location={lng_f},{lat_f}&zoom={zoom}&size={size}"
                f"&markers=mid,,A:{lng_f},{lat_f}&key={self._key}"
            )
            return {"url": url, "zoom": zoom, "size": size, "lng": lng_f, "lat": lat_f}, SOURCE_LIVE
        # mock 模式：从 fixture 读取
        return self._load_fixture(_FIXTURE_KEYS["static_map"]), SOURCE_MOCK

    async def share_map(
        self,
        title: str,
        markers: list[dict] | None = None,
    ) -> tuple[dict, str]:
        """生成分享卡：调用高德"个人专属地图"Skill。占位实现。"""
        title = (title or "").strip() or "我的卫星地图"
        if not self.is_configured:
            # mock 模式：直接读 fixture（包含 url + qrcode_base64 占位）
            return self._load_fixture(_FIXTURE_KEYS["share_map"]), SOURCE_MOCK
        # 真实模式：个人专属地图需特殊 PoiID 流程，这里走占位
        # TODO: 后续接入 https://www.amap.com/share/map 真实生成
        return {
            "url": f"https://www.amap.com/share/map/mock/{title}",
            "qrcode_base64": _placeholder_qrcode(),
            "title": title,
            "markers": markers or [],
        }, SOURCE_LIVE


# ==================== 工具 ====================
def _placeholder_qrcode() -> str:
    """1x1 透明 PNG 的 base64（占位 QR）。"""
    # 67 字节的 1x1 透明 PNG
    return (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )


# ==================== 工具: haversine 距离 + mock distance 重算 ====================
def _haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """两点间球面距离(米);Phase D.2 用它按用户传入的 (lng,lat) 重算 fixture 距离。

    公式
    ----
    a = sin²(Δφ/2) + cos(φ1)·cos(φ2)·sin²(Δλ/2)
    c = 2·atan2(√a, √(1−a))
    d = R·c
    """
    r = 6371000.0  # 地球平均半径(米)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return r * c


def _parse_lng_lat(location: str) -> tuple[float, float] | None:
    """解析 POI 的 'lng,lat' 字符串;解析失败返回 None。"""
    try:
        parts = [p.strip() for p in (location or "").split(",")]
        if len(parts) != 2:
            return None
        return float(parts[0]), float(parts[1])
    except (ValueError, AttributeError):
        return None


def _regenerate_place_around_distances(
    data: dict,
    center_lng: float,
    center_lat: float,
) -> dict:
    """对 mock 周边搜索结果按真实经纬度重算 distance 字段(米,取整)。

    行为
    ----
    - 输入 data 是 fixture 加载的 dict(含 pois 列表)
    - 对每条 POI:用其 location 与 center 计算 haversine 距离
    - 解析失败/缺字段:distance 留空字符串(不抛错)
    - 按距离升序排;同时更新 count 字段
    - 在 data 顶层塞 ``_mock_meta`` 标记,供测试断言
    """
    pois = data.get("pois") or []
    enriched: list[dict] = []
    for poi in pois:
        loc = poi.get("location")
        parsed = _parse_lng_lat(loc) if isinstance(loc, str) else None
        item = dict(poi)
        if parsed is None:
            item["distance"] = ""
        else:
            d_m = _haversine_m(center_lng, center_lat, parsed[0], parsed[1])
            item["distance"] = str(int(round(d_m)))
        enriched.append(item)
    enriched.sort(
        key=lambda x: int(x["distance"]) if x.get("distance", "").isdigit() else 1 << 30,
    )
    new_data = dict(data)
    new_data["pois"] = enriched
    new_data["count"] = str(len(enriched))
    new_data["_mock_meta"] = {
        "reason": "fixture_distances_regenerated",
        "center": [center_lng, center_lat],
        "distance_formula": "haversine",
    }
    return new_data


# ==================== 单例 ====================
_singleton: AMapClient | None = None


def get_amap_client() -> AMapClient:
    """获取进程级单例。"""
    global _singleton
    if _singleton is None:
        _singleton = AMapClient()
    return _singleton
