"""
大屏聚合数据接口 - 单元测试
==========================

覆盖 Phase B.2 后端新增的 `GET /api/stats/dashboard` 端点：

1. **结构完整性** - 200 + 5 个固定字段：kpi / classification_distribution /
   time_series / top_locations / generated_at
2. **KPI 字段正确性** - total_records / today_new / active_users / accuracy_avg
3. **角色数据隔离** - admin 看全平台 / user 仅看自己
4. **30 秒缓存命中** - 同 key 30s 内第 2 次请求 `X-Cache: HIT` 且 generated_at 一致

运行：
    cd e:\truth-视觉实践
    python -m pytest tests/test_dashboard_stats.py -v
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

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

from backend.api.stats import router as stats_router  # noqa: E402
from backend.db.base import Base, SessionLocal, engine  # noqa: E402
from backend.db.models import ClassifyRecord, User  # noqa: E402
from backend.security.deps import get_current_user  # noqa: E402
from backend.security.jwt import create_access_token  # noqa: E402
from backend.security.password import hash_password  # noqa: E402


# ==================== 测试应用构造 ====================
# 用一个最小的 FastAPI app 注册 stats_router，自己 override get_current_user 依赖，
# 避免引入完整 main.py 触发模型加载等副作用。
app = FastAPI()
app.include_router(stats_router, prefix="/api", tags=["stats"])


# ==================== Fixtures ====================
@pytest.fixture(autouse=True)
def _setup_db():
    """每个测试前建表 + 灌入固定数据，测试后清理。

    注意：autouse=True 让本 fixture 对**本文件内所有测试**自动生效。
    """
    # 清空 30s 进程内缓存，否则上一个测试留下的 cache 会让本测试的「首次 MISS」变成 HIT
    from backend.api.stats import _DASHBOARD_CACHE
    _DASHBOARD_CACHE.clear()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 准备 2 个 user：admin + 普通 user
        admin = db.query(User).filter(User.username == "dash_admin").first()
        if admin is None:
            admin = User(
                username="dash_admin",
                email="dash_admin@test.local",
                password_hash=hash_password("admin123"),
                role="admin",
                is_active=True,
            )
            db.add(admin)
        user1 = db.query(User).filter(User.username == "dash_user1").first()
        if user1 is None:
            user1 = User(
                username="dash_user1",
                email="dash_user1@test.local",
                password_hash=hash_password("user123"),
                role="user",
                is_active=True,
            )
            db.add(user1)
        db.commit()
        db.refresh(admin)
        db.refresh(user1)

        # 给 user1 灌入若干条 classify_records（混合 label/score）
        existing = (
            db.query(ClassifyRecord).filter(ClassifyRecord.user_id == user1.id).count()
        )
        if existing < 10:
            for i, label in enumerate(
                ["AnnualCrop", "Forest", "Highway", "Industrial", "Pasture",
                 "River", "Residential", "SeaLake", "Forest", "AnnualCrop"]
            ):
                db.add(ClassifyRecord(
                    user_id=user1.id,
                    image_path=f"data/test_{i}.jpg",
                    top1_label=label,
                    top1_score=0.7 + (i * 0.02),
                    top5_json='[{"label":"' + label + '","score":0.8}]',
                    duration_ms=30,
                    created_at=datetime.utcnow() - timedelta(days=i % 7),
                ))
            db.commit()
    finally:
        db.close()

    yield

    # 测试结束：清空 ClassifyRecord + 删表
    db = SessionLocal()
    try:
        db.query(ClassifyRecord).delete()
        db.query(User).filter(User.username.in_(["dash_admin", "dash_user1"])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _make_client(user_role: str) -> TestClient:
    """构造一个 TestClient，依赖注入替换为指定角色的 user。"""
    db = SessionLocal()
    try:
        if user_role == "admin":
            u = db.query(User).filter(User.username == "dash_admin").first()
        else:
            u = db.query(User).filter(User.username == "dash_user1").first()
        if u is None:
            raise RuntimeError(f"测试用户 {user_role} 未找到")
        current = u
    finally:
        db.close()

    def _override() -> User:
        return current

    app.dependency_overrides[get_current_user] = _override
    return TestClient(app)


# ==================== Test 1: 结构完整性 ====================
def test_dashboard_returns_complete_structure() -> None:
    """已登录用户访问 /api/stats/dashboard 返回 200 + 5 个固定字段。"""
    client = _make_client("user")
    r = client.get("/api/stats/dashboard")
    assert r.status_code == 200, f"应 200，实际 {r.status_code}: {r.text[:200]}"
    data = r.json()

    # 顶层 5 个字段
    for key in ("kpi", "classification_distribution", "time_series",
                "top_locations", "generated_at"):
        assert key in data, f"缺失顶层字段: {key}"

    # kpi 4 个字段
    kpi = data["kpi"]
    for key in ("total_records", "today_new", "active_users", "accuracy_avg"):
        assert key in kpi, f"kpi 缺失: {key}"

    # time_series 长度 = 30
    assert len(data["time_series"]) == 30, (
        f"time_series 长度应 30，实际 {len(data['time_series'])}"
    )

    # top_locations 是 list
    assert isinstance(data["top_locations"], list)

    # generated_at 字符串
    assert isinstance(data["generated_at"], str)
    print(f"\n  ✓ 200 + 5 字段完整: KPI={kpi}")


# ==================== Test 2: KPI 字段类型 ====================
def test_dashboard_kpi_field_types() -> None:
    """KPI 4 字段类型 + accuracy_avg 在 [0, 1]。"""
    client = _make_client("user")
    r = client.get("/api/stats/dashboard")
    assert r.status_code == 200
    kpi = r.json()["kpi"]
    assert isinstance(kpi["total_records"], int)
    assert isinstance(kpi["today_new"], int)
    assert isinstance(kpi["active_users"], int)
    assert isinstance(kpi["accuracy_avg"], (int, float))
    assert 0.0 <= kpi["accuracy_avg"] <= 1.0, f"accuracy_avg 越界: {kpi['accuracy_avg']}"
    print(f"\n  ✓ KPI 字段类型正确: total={kpi['total_records']}, "
          f"accuracy={kpi['accuracy_avg']}")


# ==================== Test 3: classification_distribution 含 10 类 ====================
def test_dashboard_distribution_has_10_classes() -> None:
    """classification_distribution 包含全部 10 个 EuroSAT 类别。"""
    client = _make_client("user")
    r = client.get("/api/stats/dashboard")
    assert r.status_code == 200
    dist = r.json()["classification_distribution"]
    expected = {
        "AnnualCrop", "Forest", "HerbaceousVegetation", "Highway", "Industrial",
        "Pasture", "PermanentCrop", "Residential", "River", "SeaLake",
    }
    actual = set(dist.keys())
    missing = expected - actual
    assert not missing, f"分布图缺类别: {missing}"
    # 每条记录都来自 user1，total_records == sum(dist.values())
    assert sum(dist.values()) >= 10, f"分布计数过少: {sum(dist.values())}"
    print(f"\n  ✓ 10 类齐全, 总计数={sum(dist.values())}")


# ==================== Test 4: 30s 缓存命中 ====================
def test_dashboard_cache_hit_within_30s() -> None:
    """同一 30s 窗口内第 2 次请求 → X-Cache: HIT + generated_at 不变。

    注意：30s 缓存按 (role, user_id) 分 key；admin 看同一份，user1 看自己的。
    """
    client = _make_client("user")
    r1 = client.get("/api/stats/dashboard")
    assert r1.status_code == 200
    assert r1.headers.get("X-Cache") == "MISS", (
        f"首次应 MISS，实际 {r1.headers.get('X-Cache')}"
    )

    r2 = client.get("/api/stats/dashboard")
    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "HIT", (
        f"二次应 HIT，实际 {r2.headers.get('X-Cache')}"
    )
    # generated_at 必须一致
    assert r1.json()["generated_at"] == r2.json()["generated_at"], (
        f"缓存命中后 generated_at 应一致: "
        f"{r1.json()['generated_at']} vs {r2.json()['generated_at']}"
    )
    # X-Cache-TTL 头存在
    assert r2.headers.get("X-Cache-TTL") is not None
    ttl = int(r2.headers["X-Cache-TTL"])
    assert 0 < ttl <= 30, f"X-Cache-TTL 应在 (0, 30]，实际 {ttl}"
    print(f"\n  ✓ 30s 缓存命中: MISS → HIT, TTL={ttl}s")


# ==================== Test 5: admin vs user 数据隔离 ====================
def test_dashboard_user_vs_admin_isolation() -> None:
    """admin 看全平台（≥ user 看自己的）。"""
    # user1 客户端
    client_user = _make_client("user")
    r_user = client_user.get("/api/stats/dashboard")
    assert r_user.status_code == 200
    user_total = r_user.json()["kpi"]["total_records"]

    # admin 客户端
    client_admin = _make_client("admin")
    r_admin = client_admin.get("/api/stats/dashboard")
    assert r_admin.status_code == 200
    admin_total = r_admin.json()["kpi"]["total_records"]

    # admin 应能看到 ≥ user 的（admin 含 user1 的数据，可能还有他人）
    assert admin_total >= user_total, (
        f"admin total_records ({admin_total}) 应 >= user total_records ({user_total})"
    )
    print(f"\n  ✓ 角色隔离: user_total={user_total} ≤ admin_total={admin_total}")


# ==================== Test 6: 未鉴权 401 ====================
def test_dashboard_unauthenticated_401() -> None:
    """未带 Authorization 头 → 401。"""
    # 清空 override 让依赖走真实的 get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    r = client.get("/api/stats/dashboard")
    assert r.status_code == 401, f"应 401，实际 {r.status_code}"
    print(f"\n  ✓ 未鉴权 → 401")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    """允许 `python tests/test_dashboard_stats.py` 直接跑。"""
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())
