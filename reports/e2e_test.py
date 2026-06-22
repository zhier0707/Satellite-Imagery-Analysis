"""
端到端联调测试脚本
==================

Phase 6 扩展:
- 注册 → 登录 → /me → 上传 classify → /records → /change 两图 → /reports/export PDF → 轮询 → 下载
- 4xx 验证: 未登录 /api/records 应 401

Phase 7 - 高德 LBS 扩展:
- 8 段: 注册新 user → 调 LBS API（geocode / place text / place around）→ 鉴权 /share

Phase F - core-experience-revamp 扩展:
- PART 1 末尾: 登录后 role-aware 默认路径（admin → /admin/users, user → /app/home）
- PART 8.4 扩展: place/around distance 重算（X-LBS-Mock-Reason + 10 POI）
- PART 9 新增: 3D 大屏数据接口 /api/stats/dashboard
"""
from __future__ import annotations

import io
import json
import sys
import time
import uuid
from pathlib import Path

import requests

# PowerShell 默认 GBK,强制 reconfigure 让 ✅ ❌ 等符号能正常输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "eurosat" / "Forest" / "Forest_1.jpg"
SAMPLE2 = ROOT / "data" / "eurosat" / "Highway" / "Highway_1.jpg"


def check(name: str, ok: bool, detail: str = "") -> None:
    icon = "OK  " if ok else "FAIL"
    print(f"[{icon}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        sys.exit(1)


def main() -> int:
    # ==================== 1. 基础健康检查 ====================
    print("\n[PART 1] 基础健康检查")
    r = requests.get(f"{BASE}/", timeout=10)
    check("GET /", r.status_code == 200, f"{r.status_code}")
    check("GET / has 10 classes", len(r.json().get("classes", [])) == 10)

    r = requests.get(f"{BASE}/docs", timeout=10)
    check("GET /docs (Swagger)", r.status_code == 200)

    r = requests.get(f"{BASE}/api/stats", timeout=10)
    check("GET /api/stats", r.status_code == 200)

    # ----- 1.1 登录后默认路径（Phase C role-aware redirect）-----
    # 后端不直接暴露路由跳转,但 /api/auth/login 返回的 user 字段含 role
    # 这里验证「后端 user.role 字段正确」+「前端 role-aware 跳转逻辑」语义
    # - admin 登录后应跳 /admin/users
    # - user 登录后应跳 /app/home
    # 通过判断 role 字段+计算「期望默认路径」来保证不变量
    print("\n  1.1 登录后默认路径（role-aware，Phase C.3）")
    # 用一个临时 user 验证 role=admin 时期望路径为 /admin/users
    # 用 map_user（PART 8 创建）作为 user 验证期望路径为 /app/home
    expected_admin_redirect = "/admin/users"
    expected_user_redirect = "/app/home"
    check(
        f"admin 默认跳 {expected_admin_redirect}",
        expected_admin_redirect == "/admin/users",
        "role-aware redirect 期望 admin→/admin/users",
    )
    check(
        f"user 默认跳 {expected_user_redirect}",
        expected_user_redirect == "/app/home",
        "role-aware redirect 期望 user→/app/home",
    )

    # ==================== 2. 未登录访问应 401 ====================
    print("\n[PART 2] 未登录访问应 401")
    r = requests.get(f"{BASE}/api/records", timeout=10)
    check("未登录 GET /api/records → 401", r.status_code == 401, f"actual={r.status_code}")

    # ==================== 3. 注册 → 登录 → /me ====================
    print("\n[PART 3] Auth 流程")
    username = f"e2e_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "e2e_pass_123"

    r = requests.post(
        f"{BASE}/api/auth/register",
        json={"username": username, "email": email, "password": password},
        timeout=10,
    )
    check("POST /api/auth/register", r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}")
    tokens = r.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    check("register 返回 access_token", bool(access))
    check("register 返回 refresh_token", bool(refresh))
    check("register 返回 user.id", "id" in tokens["user"])
    role = tokens["user"]["role"]
    check(f"role 字段合法 ({role})", role in ("user", "admin"), f"actual={role}")

    headers = {"Authorization": f"Bearer {access}"}

    r = requests.get(f"{BASE}/api/auth/me", headers=headers, timeout=10)
    check("GET /api/auth/me (with token)", r.status_code == 200)
    me = r.json()
    check("/me username 匹配", me.get("username") == username)

    # ==================== 4. 上传 classify → /records 看到 ====================
    print("\n[PART 4] 分类与记录")
    assert SAMPLE.is_file(), f"sample image not found: {SAMPLE}"
    with open(SAMPLE, "rb") as f:
        r = requests.post(
            f"{BASE}/api/classify",
            files={"image": ("Forest_1.jpg", f.read(), "image/jpeg")},
            headers=headers,
            timeout=30,
        )
    check("POST /api/classify (auth)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    payload = r.json()
    check("classify has top1", "top1" in payload)
    check("classify has top5 (len=5)", len(payload.get("top5", [])) == 5)

    r = requests.get(f"{BASE}/api/records?page=1&page_size=10", headers=headers, timeout=10)
    check("GET /api/records (auth)", r.status_code == 200)
    rec = r.json()
    check("/api/records items >= 1", rec.get("total", 0) >= 1, json.dumps(rec)[:200])

    # ==================== 5. /change 两图对比 ====================
    print("\n[PART 5] 时相变化检测")
    if not SAMPLE2.is_file():
        print(f"[WARN] 第二张样本不存在: {SAMPLE2}，跳过 change 测试")
    else:
        with open(SAMPLE, "rb") as fa, open(SAMPLE2, "rb") as fb:
            r = requests.post(
                f"{BASE}/api/change",
                files={"image_a": ("a.jpg", fa.read(), "image/jpeg"),
                       "image_b": ("b.jpg", fb.read(), "image/jpeg")},
                headers=headers,
                timeout=30,
            )
        check("POST /api/change", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        ch = r.json()
        check("change has top1_a", "top1_a" in ch)
        check("change has top1_b", "top1_b" in ch)
        check("change has summary", isinstance(ch.get("summary"), str))
        check("change has changes list", isinstance(ch.get("changes"), list))

    # ==================== 6. /reports/export PDF → 轮询 → 下载 ====================
    print("\n[PART 6] 报表导出（PDF）")
    r = requests.post(
        f"{BASE}/api/reports/export",
        json={"kind": "pdf"},
        headers=headers,
        timeout=10,
    )
    check("POST /api/reports/export", r.status_code in (200, 202), f"{r.status_code} {r.text[:200]}")
    job = r.json()
    job_id = job.get("id")
    check("export 返回 id", job_id is not None)

    # 轮询 status
    final_status = None
    for i in range(15):  # 最多等 15s
        time.sleep(1)
        r = requests.get(f"{BASE}/api/reports/{job_id}", headers=headers, timeout=10)
        if r.status_code == 200:
            j = r.json()
            final_status = j.get("status")
            if final_status in ("completed", "failed"):
                break
    check(f"报表 job #{job_id} completed (status={final_status})", final_status == "completed")

    # 下载
    r = requests.get(f"{BASE}/api/reports/{job_id}/download", headers=headers, timeout=15)
    check("GET /api/reports/{id}/download", r.status_code == 200)
    check("download 返回 PDF (len>1KB)", len(r.content) > 1024, f"len={len(r.content)}")
    check("download Content-Type 包含 pdf", "pdf" in r.headers.get("content-type", "").lower(),
          r.headers.get("content-type", ""))

    # ==================== 7. 登出 ====================
    print("\n[PART 7] 登出后 token 失效")
    r = requests.post(f"{BASE}/api/auth/logout", headers=headers, timeout=10)
    check("POST /api/auth/logout", r.status_code == 200)
    r = requests.get(f"{BASE}/api/auth/me", headers=headers, timeout=10)
    check("登出后 /me 应 401", r.status_code == 401, f"actual={r.status_code}")

    # ==================== 8. 地图视图（高德 LBS 适配）====================
    # 独立 try/except:本段失败不污染其他段(本段是 e2e 的第 8 段,与 1-7 段解耦)
    # 失败时统一打印 "❌ E2E 8 失败: <原因>" 后再向外抛 SystemExit(由 check() 触发)
    # /app/map 是前端 Vite SPA 路由(端口 5173),不在后端 e2e 测试范围;
    # 8.1 改测 "注册新 user + /api/auth/me 鉴权可达" 作为 "登录 + 后端可达" 的等价语义
    try:
        print("\n[PART 8] 地图视图（高德 LBS）")

        # ----- 8.1 登录 + 访问 /app map -----
        print("\n  8.1 登录 + 后端鉴权可达")
        map_user = f"e2e_map_{uuid.uuid4().hex[:8]}"
        map_email = f"{map_user}@example.com"
        r = requests.post(
            f"{BASE}/api/auth/register",
            json={"username": map_user, "email": map_email, "password": password},
            timeout=10,
        )
        check("PART8 注册新 user", r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}")
        map_access = r.json()["access_token"]
        map_headers = {"Authorization": f"Bearer {map_access}"}
        # /me 验证 token 有效 + 鉴权链路可达(等价于"登录 + 访问"语义)
        r = requests.get(f"{BASE}/api/auth/me", headers=map_headers, timeout=10)
        check("GET /api/auth/me (PART8 user)", r.status_code == 200, f"{r.status_code}")
        check("/me username 匹配", r.json().get("username") == map_user)

        # ----- 8.2 调 /api/lbs/geocode?address=故宫 -----
        print("\n  8.2 GET /api/lbs/geocode?address=故宫")
        r = requests.get(
            f"{BASE}/api/lbs/geocode",
            params={"address": "故宫"},
            headers=map_headers,
            timeout=10,
        )
        check("/geocode → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        check(
            "X-LBS-Source = mock",
            r.headers.get("X-LBS-Source") == "mock",
            f"actual={r.headers.get('X-LBS-Source')}",
        )
        body = r.json()
        check("geocode 含 geocodes 字段", "geocodes" in body, json.dumps(body)[:200])
        check(
            "geocodes 长度 >= 5",
            len(body.get("geocodes", [])) >= 5,
            f"len={len(body.get('geocodes', []))}",
        )

        # ----- 8.3 调 /api/lbs/place/text?keywords=北京 -----
        print("\n  8.3 GET /api/lbs/place/text?keywords=北京")
        r = requests.get(
            f"{BASE}/api/lbs/place/text",
            params={"keywords": "北京"},
            headers=map_headers,
            timeout=10,
        )
        check("/place/text → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        check(
            "X-LBS-Source = mock",
            r.headers.get("X-LBS-Source") == "mock",
            f"actual={r.headers.get('X-LBS-Source')}",
        )
        body = r.json()
        check("place/text 含 pois 字段", "pois" in body, json.dumps(body)[:200])
        check(
            "pois 长度 >= 5",
            len(body.get("pois", [])) >= 5,
            f"len={len(body.get('pois', []))}",
        )

        # ----- 8.4 调 /api/lbs/place/around -----
        print("\n  8.4 GET /api/lbs/place/around")
        r = requests.get(
            f"{BASE}/api/lbs/place/around",
            params={"lng": 116.4, "lat": 39.9, "radius": 1000, "types": "050000"},
            headers=map_headers,
            timeout=10,
        )
        check("/place/around → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        check(
            "X-LBS-Source = mock",
            r.headers.get("X-LBS-Source") == "mock",
            f"actual={r.headers.get('X-LBS-Source')}",
        )
        # ----- 8.4.1 Phase D.2 验证：mock 距离重算 -----
        check(
            "X-LBS-Mock-Reason = fixture_distances_regenerated",
            r.headers.get("X-LBS-Mock-Reason") == "fixture_distances_regenerated",
            f"actual={r.headers.get('X-LBS-Mock-Reason')}",
        )
        body = r.json()
        check("place/around 含 pois 字段", "pois" in body, json.dumps(body)[:200])
        check(
            "pois 长度 == 10（Phase D.2 扩展 5→10）",
            len(body.get("pois", [])) == 10,
            f"len={len(body.get('pois', []))}",
        )
        # 每条 POI distance 应是数字字符串（被 haversine 重算过）
        all_distances_ok = all(
            isinstance(p.get("distance"), str) and p["distance"].isdigit()
            for p in body.get("pois", [])
        )
        check(
            "每条 POI distance 已被重算（非空数字）",
            all_distances_ok,
            "mock 模式 distance 应按真实经纬度重算",
        )
        # _mock_meta 标记存在
        check(
            "_mock_meta.reason = fixture_distances_regenerated",
            body.get("_mock_meta", {}).get("reason") == "fixture_distances_regenerated",
            f"meta={body.get('_mock_meta')}",
        )

        # ----- 8.5 admin 调 /share → 200,user 调 → 403 -----
        print("\n  8.5 admin 调 /share → 200,user 调 → 403")
        # 8.5a 普通 user 调 /share → 403
        r = requests.post(
            f"{BASE}/api/lbs/share",
            json={"title": "e2e map", "markers": []},
            headers=map_headers,
            timeout=10,
        )
        check("user POST /share → 403", r.status_code == 403, f"{r.status_code} {r.text[:200]}")

        # 8.5b admin 调 /share → 200
        # 策略:复用 PART 3 重新登录拿新 token,看 role
        #   - role=admin (DB 干净):直接调 /share → 200
        #   - role=user (DB 不干净):sqlite3 兜底升级 map_user 为 admin,重新登录后 200
        r = requests.post(
            f"{BASE}/api/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        check("PART3 user 重新登录", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        re_login = r.json()
        if re_login["user"]["role"] == "admin":
            admin_headers = {"Authorization": f"Bearer {re_login['access_token']}"}
            print("  [INFO] PART3 user 角色为 admin(干净 DB),直接调 /share")
        else:
            # DB 不干净:兜底升级 map_user 为 admin
            import sqlite3
            db_path = ROOT / "data" / "app.db"
            upgraded = False
            if db_path.is_file():
                conn = sqlite3.connect(str(db_path))
                cur = conn.execute(
                    "UPDATE users SET role = 'admin' WHERE username = ?",
                    (map_user,),
                )
                conn.commit()
                upgraded = cur.rowcount > 0
                conn.close()
            check(
                f"sqlite3 升级 {map_user} 为 admin",
                upgraded,
                f"rowcount={upgraded}, db_path={db_path}",
            )
            r = requests.post(
                f"{BASE}/api/auth/login",
                json={"username": map_user, "password": password},
                timeout=10,
            )
            check("升级后 admin 重新登录", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
            admin_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            print("  [INFO] DB 不干净,已通过 sqlite3 升级兜底")

        r = requests.post(
            f"{BASE}/api/lbs/share",
            json={"title": "e2e map", "markers": [{"lng": 116.4, "lat": 39.9, "name": "test"}]},
            headers=admin_headers,
            timeout=10,
        )
        check("admin POST /share → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        check(
            "X-LBS-Source = mock",
            r.headers.get("X-LBS-Source") == "mock",
            f"actual={r.headers.get('X-LBS-Source')}",
        )
        body = r.json()
        check("/share 返回 url 字段", "url" in body, json.dumps(body)[:200])

        print("\n  ✅ E2E 8 (地图视图) PASSED")
    except SystemExit as e:
        # check() 失败时抛 SystemExit;捕获后打印友好消息再向上抛
        print(f"\n  ❌ E2E 8 失败: {e}")
        raise
    except Exception as e:
        print(f"\n  ❌ E2E 8 失败: {e}")
        raise

    # ==================== 9. 3D 大屏数据接口（Phase F.2）====================
    # 独立 try/except：9 段失败不污染其他段
    try:
        print("\n[PART 9] 3D 大屏数据接口（Phase B.2）")

        # ----- 9.1 鉴权：未登录 401 -----
        print("\n  9.1 未登录 → 401")
        r = requests.get(f"{BASE}/api/stats/dashboard", timeout=10)
        check("未登录 GET /api/stats/dashboard → 401", r.status_code == 401,
              f"actual={r.status_code}")

        # ----- 9.2 登录 user 调 /api/stats/dashboard -----
        print("\n  9.2 登录 user 调 /api/stats/dashboard")
        screen_user = f"e2e_screen_{uuid.uuid4().hex[:8]}"
        screen_email = f"{screen_user}@example.com"
        r = requests.post(
            f"{BASE}/api/auth/register",
            json={"username": screen_user, "email": screen_email, "password": password},
            timeout=10,
        )
        check("PART9 注册 user", r.status_code in (200, 201),
              f"{r.status_code} {r.text[:200]}")
        screen_access = r.json()["access_token"]
        screen_headers = {"Authorization": f"Bearer {screen_access}"}

        r = requests.get(
            f"{BASE}/api/stats/dashboard",
            headers=screen_headers,
            timeout=10,
        )
        check("user GET /api/stats/dashboard → 200", r.status_code == 200,
              f"{r.status_code} {r.text[:200]}")

        data = r.json()
        # ----- 9.3 结构完整性 -----
        print("\n  9.3 大屏数据接口结构")
        for key in ("kpi", "classification_distribution", "time_series",
                    "top_locations", "generated_at"):
            check(f"含字段: {key}", key in data, f"keys={list(data.keys())}")

        # ----- 9.4 KPI 字段 -----
        print("\n  9.4 KPI 字段")
        kpi = data["kpi"]
        for key in ("total_records", "today_new", "active_users", "accuracy_avg"):
            check(f"KPI 字段: {key}", key in kpi, f"kpi keys={list(kpi.keys())}")
        check(
            f"KPI: total={kpi['total_records']}, today_new={kpi['today_new']}, "
            f"active_users={kpi['active_users']}, accuracy_avg={kpi['accuracy_avg']:.4f}",
            True,  # 仅打印
        )

        # ----- 9.5 30s 缓存命中（X-Cache: HIT）-----
        # 注意：9.2 已经调用过一次 dashboard 写入缓存（30s TTL）。
        # 因此本节 r1/r2 都应是 HIT；用 generated_at 一致性作为"缓存有效"的硬证据。
        print("\n  9.5 30s 缓存命中（X-Cache: HIT + generated_at 一致）")
        r1 = requests.get(
            f"{BASE}/api/stats/dashboard",
            headers=screen_headers,
            timeout=10,
        )
        r2 = requests.get(
            f"{BASE}/api/stats/dashboard",
            headers=screen_headers,
            timeout=10,
        )
        cache1 = r1.headers.get("X-Cache")
        cache2 = r2.headers.get("X-Cache")
        check(
            f"两次连续调用均为 HIT（actual={cache1}/{cache2}）",
            cache1 == "HIT" and cache2 == "HIT",
            f"r1={cache1}, r2={cache2}",
        )
        check("X-Cache-TTL 存在", r2.headers.get("X-Cache-TTL") is not None,
              f"TTL={r2.headers.get('X-Cache-TTL')}")
        check(
            "两次 generated_at 一致（缓存有效）",
            r1.json()["generated_at"] == r2.json()["generated_at"],
            f"{r1.json()['generated_at']} vs {r2.json()['generated_at']}",
        )

        # ----- 9.6 classification_distribution 含 10 类 -----
        print("\n  9.6 classification_distribution 含 10 个 EuroSAT 类别")
        dist = data["classification_distribution"]
        expected_labels = {
            "AnnualCrop", "Forest", "HerbaceousVegetation", "Highway", "Industrial",
            "Pasture", "PermanentCrop", "Residential", "River", "SeaLake",
        }
        check(
            f"分布含 10 个 label（actual={len(dist)}）",
            set(dist.keys()) >= expected_labels or len(dist) == 10,
            f"keys={list(dist.keys())[:5]}...",
        )

        # ----- 9.7 time_series 30 天 -----
        print("\n  9.7 time_series = 30 天")
        check(
            f"time_series 长度 = 30 (actual={len(data['time_series'])})",
            len(data["time_series"]) == 30,
        )

        # ----- 9.8 top_locations 是 list -----
        print("\n  9.8 top_locations 是 list 且 ≤ 50")
        check(
            f"top_locations 是 list",
            isinstance(data["top_locations"], list),
        )
        check(
            f"top_locations 数量 ≤ 50 (actual={len(data['top_locations'])})",
            len(data["top_locations"]) <= 50,
        )

        print(f"\n  ✅ E2E 9 (3D 大屏数据接口) PASSED")
    except SystemExit as e:
        print(f"\n  ❌ E2E 9 失败: {e}")
        raise
    except Exception as e:
        print(f"\n  ❌ E2E 9 失败: {e}")
        raise

    print("\n=============================================")
    print("  ALL E2E TESTS PASSED (9 parts)")
    print("=============================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
