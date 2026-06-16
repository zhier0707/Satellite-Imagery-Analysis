"""
真实模型回归测试 (E2E)
======================

目的：
  防止 best.pt 在部署后被意外降级为 mock 模式。
  通过对 5 张 EuroSAT 已知类别图发起真实推理，
  固化预期 (top1 label + mock=false + 最低置信度) 作为回归基准。

前置条件：
  1) 后端服务已启动 (默认 http://127.0.0.1:8000)
  2) models/checkpoints/best.pt 存在且通过 verify_model.py
  3) data/eurosat/ 至少含 5 个类别子目录,每类至少 1 张 jpg

执行：
  & "F:\\anaconda\\python.exe" tests/test_real_model_e2e.py

输出：PASS / FAIL 表。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

# 强制 UTF-8 stdout,兼容 PowerShell GBK
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
DATA = ROOT / "data" / "eurosat"
USERNAME = os.environ.get("E2E_USER", "realmodel_test")
PASSWORD = os.environ.get("E2E_PWD", "RealModel123!")

# ==================== 回归基线 ====================
# (相对路径 -> 期望 top1 label, 最低置信度)
# 置信度阈值取 0.5 是因为真实模型对训练集图一般在 0.8+;
# mock 模式为伪随机 score, 几乎不可能 5 张全部 >= 0.5。
CASES: list[tuple[str, str, float]] = [
    ("AnnualCrop/AnnualCrop_1.jpg", "AnnualCrop", 0.50),
    ("Forest/Forest_1.jpg",         "Forest",      0.50),
    ("Highway/Highway_1.jpg",       "Highway",     0.50),
    ("River/River_1.jpg",           "River",       0.50),
    ("SeaLake/SeaLake_1.jpg",       "SeaLake",     0.50),
]


# ==================== 工具函数 ====================
def _ok(msg: str) -> None:
    print(f"  \u2713 {msg}")


def _fail(msg: str) -> None:
    print(f"  \u2717 {msg}")


def get_token() -> str:
    """注册 + 登录获取 JWT。已存在则直接登录。"""
    # 优先登录
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    if r.status_code == 200:
        return r.json()["access_token"]
    # 否则注册
    r = requests.post(
        f"{BASE}/api/auth/register",
        json={"username": USERNAME, "password": PASSWORD, "email": f"{USERNAME}@example.com"},
        timeout=10,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"register failed: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def classify(token: str, img_path: Path) -> dict:
    with open(img_path, "rb") as f:
        r = requests.post(
            f"{BASE}/api/classify",
            files={"image": (img_path.name, f, "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
    r.raise_for_status()
    return r.json()


# ==================== 主流程 ====================
def main() -> int:
    print("=" * 60)
    print("  真实模型回归测试 (E2E)")
    print("=" * 60)
    print(f"  BASE    = {BASE}")
    print(f"  DATA    = {DATA}")
    print(f"  CASES   = {len(CASES)}")
    print("-" * 60)

    # 1) 健康检查 (使用根路径代替 /api/health)
    try:
        r = requests.get(f"{BASE}/", timeout=5)
        r.raise_for_status()
        meta = r.json()
        _ok(f"后端在线 | version={meta.get('version')} | classes={len(meta.get('classes', []))}")
    except Exception as e:
        _fail(f"后端不可达: {e}")
        return 1

    # 2) 认证
    try:
        t0 = time.time()
        token = get_token()
        _ok(f"获取 JWT (用时 {time.time()-t0:.2f}s, len={len(token)})")
    except Exception as e:
        _fail(f"认证失败: {e}")
        return 1

    # 3) 检查权重是否存在
    ckpt = ROOT / "models" / "checkpoints" / "best.pt"
    if not ckpt.is_file():
        _fail(f"权重文件不存在: {ckpt}")
        return 1
    _ok(f"权重存在: {ckpt.name} ({ckpt.stat().st_size/1e6:.1f} MB)")

    # 4) 逐图推理
    print("-" * 60)
    print(f"  {'用例':28s} {'期望':18s} {'实际':18s} {'置信度':>8s}  状态")
    print("-" * 60)
    fail_count = 0
    mock_count = 0
    for rel, expected, min_score in CASES:
        img = DATA / rel
        if not img.is_file():
            _fail(f"测试图不存在: {img}")
            fail_count += 1
            continue
        try:
            res = classify(token, img)
        except Exception as e:
            _fail(f"{rel} 推理异常: {e}")
            fail_count += 1
            continue
        top1 = res.get("top1", {}).get("label", "?")
        score = float(res.get("top1", {}).get("score", 0.0))
        mock = bool(res.get("mock", True))
        ok_label = top1 == expected
        ok_score = score >= min_score
        ok_real = not mock
        if mock:
            mock_count += 1
        status = "PASS" if (ok_label and ok_score and ok_real) else "FAIL"
        if status == "FAIL":
            fail_count += 1
        marker = "MOCK!" if mock else "      "
        print(
            f"  {rel:28s} {expected:18s} {top1:18s} {score:>8.4f}  {status} {marker}"
        )

    # 5) 汇总
    print("-" * 60)
    if fail_count == 0 and mock_count == 0:
        print(f"  [SUCCESS] {len(CASES)}/{len(CASES)} 全部命中, 真实模型 (mock=false) 已生效")
        return 0
    elif mock_count > 0:
        print(f"  [FAIL] 检测到 {mock_count} 次 mock 响应,模型未加载或被降级")
        print("  排查:检查 uvicorn 启动时 MODEL_WEIGHTS 环境变量 / best.pt 是否完整")
        return 1
    else:
        print(f"  [FAIL] {fail_count}/{len(CASES)} 用例未通过")
        return 1


if __name__ == "__main__":
    sys.exit(main())
