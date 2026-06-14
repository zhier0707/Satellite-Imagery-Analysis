"""
端到端联调测试脚本
==================

Phase 6 扩展:
- 注册 → 登录 → /me → 上传 classify → /records → /change 两图 → /reports/export PDF → 轮询 → 下载
- 4xx 验证: 未登录 /api/records 应 401
"""
from __future__ import annotations

import io
import json
import sys
import time
import uuid
from pathlib import Path

import requests

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

    print("\n=============================================")
    print("  ALL E2E TESTS PASSED (7 parts)")
    print("=============================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
