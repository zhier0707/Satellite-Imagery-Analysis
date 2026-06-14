"""
PyTorch -> ONNX -> TensorFlow SavedModel -> TF.js 转换脚本
=========================================================

按 卫星图像分析项目方案.md 5.3 节命令序列实现。

依赖（按需安装）：
    pip install onnx onnx2tf tensorflow tensorflowjs
    pip install tensorflow-io-gcs-filesystem   # TF2.16+ 必需

执行：
    python scripts/convert_to_tfjs.py --weights models/checkpoints/best.pt
    python scripts/convert_to_tfjs.py --weights models/checkpoints/best.pt --dry-run

产物：
    models/web_model/
    ├── model.json
    └── group1-shard1of1.bin
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert PyTorch model to TF.js")
    p.add_argument("--weights", required=True, help=".pt 检查点路径")
    p.add_argument("--model", default="tf_efficientnetv2_m", help="timm 模型名")
    p.add_argument("--num-classes", type=int, default=10)
    p.add_argument("--image-size", type=int, default=384)
    p.add_argument("--output-dir", default="models/web_model")
    p.add_argument("--opset", type=int, default=13)
    p.add_argument("--dry-run", action="store_true", help="只打印命令不执行")
    return p.parse_args()


def step1_pytorch_to_onnx(weights: Path, onnx_path: Path, model_name: str,
                          num_classes: int, image_size: int, opset: int, dry_run: bool) -> None:
    """第一步：PyTorch -> ONNX。"""
    code = f"""
import torch, timm
m = timm.create_model("{model_name}", pretrained=False, num_classes={num_classes})
ckpt = torch.load(r"{weights}", map_location="cpu")
state = ckpt.get("model", ckpt)
m.load_state_dict(state, strict=False)
m.eval()
dummy = torch.randn(1, 3, {image_size}, {image_size})
torch.onnx.export(
    m, dummy, r"{onnx_path}",
    input_names=["input"], output_names=["output"],
    opset_version={opset}, dynamic_axes={{"input": {{0: "batch"}}, "output": {{0: "batch"}}}},
)
print("[OK] ONNX saved")
"""
    if dry_run:
        print("--- [Step 1] would run inline script ---")
        print(code)
        return
    exec(code, {"__name__": "__main__", "torch": torch} if False else {})


def step2_onnx_to_tf(onnx_path: Path, tf_dir: Path, dry_run: bool) -> None:
    """第二步：ONNX -> TensorFlow SavedModel（用 onnx2tf）。"""
    cmd = [
        sys.executable, "-m", "onnx2tf",
        "-i", str(onnx_path),
        "-o", str(tf_dir),
    ]
    print(f"--- [Step 2] {' '.join(cmd)} ---")
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def step3_tf_to_tfjs(tf_dir: Path, output_dir: Path, dry_run: bool) -> None:
    """第三步：TensorFlow SavedModel -> TF.js。"""
    cmd = [
        "tensorflowjs_converter",
        "--input_format=tf_saved_model",
        "--output_format=tfjs_graph_model",
        "--signature_name=serving_default",
        str(tf_dir),
        str(output_dir),
    ]
    print(f"--- [Step 3] {' '.join(cmd)} ---")
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def main() -> int:
    args = parse_args()
    weights = Path(args.weights)
    if not args.dry_run and not weights.is_file():
        print(f"[x] weights not found: {weights}", file=sys.stderr)
        return 1

    onnx_path = ROOT / "models" / f"{weights.stem}.onnx"
    tf_dir = ROOT / "models" / "tf_saved"
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        step1_pytorch_to_onnx(weights, onnx_path, args.model, args.num_classes,
                               args.image_size, args.opset, args.dry_run)
        step2_onnx_to_tf(onnx_path, tf_dir, args.dry_run)
        step3_tf_to_tfjs(tf_dir, output_dir, args.dry_run)
    except subprocess.CalledProcessError as e:
        print(f"[x] subprocess failed: {e}", file=sys.stderr)
        return e.returncode
    except Exception as e:
        print(f"[x] conversion failed: {e}", file=sys.stderr)
        return 1

    if not args.dry_run:
        # 清理中间产物
        if onnx_path.exists():
            onnx_path.unlink()
        if tf_dir.exists():
            shutil.rmtree(tf_dir)
        print(f"\n[OK] TF.js model saved to {output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
