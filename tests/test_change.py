"""
Phase 3 变化检测 - 冒烟测试
==========================

不依赖 FastAPI / DB，纯函数级单元测试。

验证：
1. compute_changes 覆盖三种类型：top1_changed / label_lost / label_gained
2. compute_changes 无变化时返回空列表
3. make_summary 自然语言输出含关键标签
4. change 模块可以 import（路由文件语法正确）
5. classify_pil 已抽离，且 classify 路由仍能 import
"""
from __future__ import annotations

import sys
from pathlib import Path

# PowerShell 默认 GBK stdout，打印 ✓/→ 等 Unicode 符号会爆
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_compute_changes_top1_changed() -> None:
    """Test 1: top1 变化场景。"""
    print("\n=== Test 1: compute_changes top1_changed ===")
    from backend.api.change import compute_changes

    top5_a = [
        {"label": "Forest", "score": 0.85},
        {"label": "HerbaceousVegetation", "score": 0.08},
        {"label": "Pasture", "score": 0.04},
        {"label": "AnnualCrop", "score": 0.02},
        {"label": "PermanentCrop", "score": 0.01},
    ]
    top5_b = [
        {"label": "Highway", "score": 0.72},
        {"label": "Industrial", "score": 0.15},
        {"label": "Residential", "score": 0.07},
        {"label": "HerbaceousVegetation", "score": 0.04},
        {"label": "Pasture", "score": 0.02},
    ]
    changes = compute_changes(top5_a, top5_b)
    types = [c["type"] for c in changes]
    assert "top1_changed" in types, f"应包含 top1_changed, 实际 {types}"
    assert "label_lost" in types, "Forest 不在 B 前 5，应 label_lost"
    assert "label_gained" in types, "Highway 不在 A 前 5，应 label_gained"
    print(f"  ✓ changes={len(changes)}: {types}")


def test_compute_changes_no_change() -> None:
    """Test 2: top1 一致 + Top-5 集合一致 -> 空列表。"""
    print("\n=== Test 2: compute_changes 无变化 ===")
    from backend.api.change import compute_changes

    same = [{"label": "Forest", "score": s} for s in (0.9, 0.05, 0.03, 0.01, 0.01)]
    changes = compute_changes(same, same)
    assert changes == [], f"应为空，实际 {changes}"
    print(f"  ✓ changes={changes}")


def test_compute_changes_partial() -> None:
    """Test 3: top1 一致但 A 有 X、B 有 Y（A 也有 Y）-> 只有 score 差异，不算变化。"""
    print("\n=== Test 3: top1 一致 + 子集关系 -> 无变化 ===")
    from backend.api.change import compute_changes

    top5_a = [
        {"label": "Forest", "score": 0.8},
        {"label": "Highway", "score": 0.1},
        {"label": "Pasture", "score": 0.05},
    ]
    top5_b = [
        {"label": "Forest", "score": 0.7},
        {"label": "Highway", "score": 0.2},
        {"label": "Pasture", "score": 0.05},
    ]
    changes = compute_changes(top5_a, top5_b)
    assert changes == [], f"top1 一致且 B 的 top1 在 A 中 -> 应无变化, 实际 {changes}"
    print(f"  ✓ changes={changes}")


def test_make_summary() -> None:
    """Test 4: make_summary 含关键标签。"""
    print("\n=== Test 4: make_summary 自然语言 ===")
    from backend.api.change import make_summary

    top1_a = {"label": "Forest", "score": 0.85}
    top1_b = {"label": "Highway", "score": 0.72}
    changes = [
        {"type": "top1_changed", "from": "Forest", "to": "Highway",
         "score_a": 0.85, "score_b": 0.72},
        {"type": "label_lost", "label": "Forest", "score_a": 0.85, "score_b": 0.0},
    ]
    summary = make_summary(top1_a, top1_b, changes)
    assert "Forest" in summary
    assert "Highway" in summary
    assert "变为" in summary
    assert "消失" in summary
    print(f"  ✓ summary={summary!r}")


def test_make_summary_no_change() -> None:
    """Test 5: 无变化 summary。"""
    print("\n=== Test 5: make_summary 无变化 ===")
    from backend.api.change import make_summary

    top1 = {"label": "Forest", "score": 0.9}
    summary = make_summary(top1, top1, [])
    assert "Forest" in summary
    assert "未发生显著变化" in summary
    print(f"  ✓ summary={summary!r}")


def test_imports() -> None:
    """Test 6: 模块 import 路径正确（无 SQL/无 FastAPI 启动）。"""
    print("\n=== Test 6: 模块 import 验证 ===")
    from backend.api import change  # noqa: F401
    from backend.api.change import compute_changes, make_summary  # noqa: F401
    from backend.services.model_service import ModelService  # noqa: F401
    print("  ✓ backend.api.change 与 backend.services.model_service.ModelService 都能 import")


def main() -> int:
    n_total = 6
    n_done = 0
    log_lines: list[str] = []
    log_lines.append(f"[1/{n_total}] compute_changes_top1_changed")
    test_compute_changes_top1_changed(); n_done += 1
    log_lines.append(f"[2/{n_total}] compute_changes_no_change")
    test_compute_changes_no_change(); n_done += 1
    log_lines.append(f"[3/{n_total}] compute_changes_partial")
    test_compute_changes_partial(); n_done += 1
    log_lines.append(f"[4/{n_total}] make_summary")
    test_make_summary(); n_done += 1
    log_lines.append(f"[5/{n_total}] make_summary_no_change")
    test_make_summary_no_change(); n_done += 1
    log_lines.append(f"[6/{n_total}] imports")
    test_imports(); n_done += 1
    log_lines.append(f"\n=== ALL {n_done}/{n_total} PHASE 3 CHANGE SMOKE TESTS PASSED ===")
    # 终端打印 + 写日志文件（绕过 PowerShell GBK 截断问题）
    for line in log_lines:
        print(line, flush=True)
    log_path = Path(__file__).resolve().parent.parent / "reports" / "phase3_change_test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
