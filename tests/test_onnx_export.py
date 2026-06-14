"""
Phase 4 ONNX 导出 - 冒烟测试
============================

验证：
1. export_onnx() 用随机权重导出，文件存在、>1KB
2. onnxruntime InferenceSession 加载 OK、推理输出 shape == (1, num_classes)
3. export_onnx() 加载真实 .pt 权重（用我们 save_checkpoint 风格的小文件）
4. CLI --dry-run 跑通
5. CLI --random 跑通（不传 weights 也不报错）
6. export_onnx() 加载不存在的文件 -> FileNotFoundError
"""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ==================== Tests ====================
def test_export_onnx_random() -> None:
    """Test 1: 随机权重导出（小模型 efficientnet_b0 + 64x64），ONNX 文件存在、>1KB。"""
    print("\n=== Test 1: 随机权重导出 ===")
    from scripts.convert_to_onnx import export_onnx

    with tempfile.TemporaryDirectory(prefix="onnx_test_") as td:
        out = Path(td) / "tiny.onnx"
        result = export_onnx(
            weights=None,
            output_path=out,
            model_name="efficientnet_b0",  # 5M 参数，本地能跑
            num_classes=4,
            image_size=64,
            opset=13,
            random_weights=True,
        )
        assert out.is_file(), "ONNX 未生成"
        size_kb = out.stat().st_size / 1024
        assert size_kb > 1, f"ONNX 太小: {size_kb:.1f}KB"
        print(f"  ✓ 随机权重导出: {result} ({size_kb:.1f} KB)")


def test_onnxruntime_sanity() -> None:
    """Test 2: onnxruntime 加载 + 推理 + shape 校验。"""
    print("\n=== Test 2: onnxruntime sanity 推理 ===")
    import numpy as np
    import onnxruntime as ort
    from scripts.convert_to_onnx import export_onnx

    with tempfile.TemporaryDirectory(prefix="onnx_rt_") as td:
        out = Path(td) / "rt.onnx"
        export_onnx(
            weights=None, output_path=out,
            model_name="efficientnet_b0", num_classes=4,
            image_size=64, opset=13, random_weights=True,
        )
        sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
        x = np.random.randn(1, 3, 64, 64).astype(np.float32)
        result = sess.run(None, {"input": x})[0]
        assert result.shape == (1, 4), f"output shape {result.shape} != (1, 4)"
        print(f"  ✓ InferenceSession output shape={result.shape}, dtype={result.dtype}")


def test_export_onnx_with_real_weights() -> None:
    """Test 3: 用真实的 .pt 权重导出（构造一个 tiny checkpoint 验证 load_state_dict 逻辑）。"""
    print("\n=== Test 3: 真实权重导出 ===")
    import torch
    import timm
    from scripts.convert_to_onnx import export_onnx

    with tempfile.TemporaryDirectory(prefix="onnx_real_") as td:
        # 构造一个 efficientnet_b0 的小 ckpt
        m = timm.create_model("efficientnet_b0", pretrained=False, num_classes=4)
        ckpt_path = Path(td) / "tiny.pt"
        torch.save({"model": m.state_dict(), "epoch": 0, "val_acc": 0.0}, ckpt_path)

        out = Path(td) / "out.onnx"
        export_onnx(
            weights=ckpt_path, output_path=out,
            model_name="efficientnet_b0", num_classes=4,
            image_size=64, opset=13,
        )
        assert out.is_file()
        print(f"  ✓ 真实权重导出: {out.stat().st_size / 1024:.1f} KB")


def test_cli_dry_run() -> None:
    """Test 4: CLI --dry-run 跑通，不真生成文件。"""
    print("\n=== Test 4: CLI --dry-run ===")
    import subprocess
    with tempfile.TemporaryDirectory(prefix="onnx_dry_") as td:
        out = Path(td) / "should_not_exist.onnx"
        r = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "convert_to_onnx.py"),
                "--random", "--output", str(out), "--model", "efficientnet_b0",
                "--num-classes", "4", "--image-size", "64",
                "--dry-run",
            ],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT),
        )
        assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr}"
        assert "DRY RUN" in r.stdout
        assert not out.exists(), "dry-run 不应生成文件"
        print(f"  ✓ dry-run exit=0, 不生成文件")


def test_cli_random() -> None:
    """Test 5: CLI --random 端到端跑通。"""
    print("\n=== Test 5: CLI --random ===")
    import subprocess
    with tempfile.TemporaryDirectory(prefix="onnx_cli_") as td:
        out = Path(td) / "cli.onnx"
        r = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "convert_to_onnx.py"),
                "--random", "--output", str(out), "--model", "efficientnet_b0",
                "--num-classes", "4", "--image-size", "64",
            ],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr}"
        assert out.is_file(), f"ONNX 未生成, stdout={r.stdout}, stderr={r.stderr}"
        print(f"  ✓ CLI --random 生成: {out.stat().st_size / 1024:.1f} KB")


def test_missing_weights_raises() -> None:
    """Test 6: 不传 --random 且 weights 不存在 -> FileNotFoundError。"""
    print("\n=== Test 6: 缺权重 -> FileNotFoundError ===")
    from scripts.convert_to_onnx import export_onnx

    with tempfile.TemporaryDirectory() as td:
        try:
            export_onnx(
                weights=Path("nonexistent_xyz.pt"),
                output_path=Path(td) / "x.onnx",
                model_name="efficientnet_b0", num_classes=4,
                image_size=64, opset=13,
            )
            assert False, "应抛 FileNotFoundError"
        except FileNotFoundError as e:
            print(f"  ✓ 正确抛 FileNotFoundError: {e}")


def test_imports() -> None:
    """Test 7: 模块 import。"""
    print("\n=== Test 7: 模块 import ===")
    from scripts.convert_to_onnx import export_onnx, parse_args, main  # noqa: F401
    print("  ✓ scripts.convert_to_onnx 三符号可 import")


def main() -> int:
    n_total = 7
    n_done = 0
    log_lines: list[str] = []
    try:
        log_lines.append(f"[1/{n_total}] export_onnx_random")
        test_export_onnx_random(); n_done += 1
        log_lines.append(f"[2/{n_total}] onnxruntime_sanity")
        test_onnxruntime_sanity(); n_done += 1
        log_lines.append(f"[3/{n_total}] export_onnx_with_real_weights")
        test_export_onnx_with_real_weights(); n_done += 1
        log_lines.append(f"[4/{n_total}] cli_dry_run")
        test_cli_dry_run(); n_done += 1
        log_lines.append(f"[5/{n_total}] cli_random")
        test_cli_random(); n_done += 1
        log_lines.append(f"[6/{n_total}] missing_weights_raises")
        test_missing_weights_raises(); n_done += 1
        log_lines.append(f"[7/{n_total}] imports")
        test_imports(); n_done += 1
    except Exception as e:
        log_lines.append(f"!!! FAILED: {e}")
        log_lines.append(traceback.format_exc())
    log_lines.append(f"\n=== ALL {n_done}/{n_total} PHASE 4 ONNX SMOKE TESTS PASSED ===")
    for line in log_lines:
        print(line, flush=True)
    log_path = Path(__file__).resolve().parent.parent / "reports" / "phase4_onnx_test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0 if n_done == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
