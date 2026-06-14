"""
PyTorch -> ONNX 导出脚本
=========================

按 .trae/specs/satellite-image-full/tasks.md Task 16 实现。

设计：
- 单文件、单函数 `export_onnx(weights, output_path, model_name, num_classes, image_size, opset)`
- 加载 .pt -> 重建 timm 模型 -> eval() -> dummy tensor -> torch.onnx.export
- dynamic_axes={"input":{0:"batch"}, "output":{0:"batch"}}
- onnxruntime.InferenceSession 做一次 sanity 推理，验证 output shape == (1, num_classes)
- 没有 best.pt 时退化为"以随机权重导出"以支持 dry-run 链验证

执行：
    # 正常导出
    python scripts/convert_to_onnx.py --weights models/checkpoints/best.pt

    # 随机权重导出（用于 CI / 链验证）
    python scripts/convert_to_onnx.py --random --output models/web_model/best.onnx

    # dry-run（只打印将要做的步骤，不真导出）
    python scripts/convert_to_onnx.py --weights x.pt --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# PowerShell GBK 兼容
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("convert_to_onnx")


# ==================== 核心函数 ====================
def export_onnx(
    weights: Path | None,
    output_path: Path,
    model_name: str = "tf_efficientnetv2_m",
    num_classes: int = 10,
    image_size: int = 384,
    opset: int = 13,
    random_weights: bool = False,
) -> Path:
    """PyTorch -> ONNX 导出。

    Args:
        weights: .pt 路径（如果 random_weights=True 可以为 None）
        output_path: 输出 .onnx 路径
        model_name: timm 模型名
        num_classes: 分类数（EuroSAT=10）
        image_size: 训练分辨率
        opset: ONNX opset 版本
        random_weights: True 时跳过加载权重（用随机初始化）

    Returns:
        output_path（绝对路径）
    """
    import numpy as np
    import torch
    import timm

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ==================== 1. 加载权重 ====================
    if not random_weights:
        if weights is None or not Path(weights).is_file():
            raise FileNotFoundError(f"weights not found: {weights}")
        ckpt = torch.load(weights, map_location="cpu")
        state = ckpt.get("model", ckpt)  # 兼容 {model:..., optimizer:...} 与纯 state_dict
        log.info("[1/4] 已加载权重: %s (%.1f MB)", weights, Path(weights).stat().st_size / 1024 / 1024)
    else:
        state = None
        log.info("[1/4] random_weights=True，跳过权重加载")

    # ==================== 2. 重建模型 ====================
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    if state is not None:
        missing, unexpected = model.load_state_dict(state, strict=False)
        log.info(
            "[2/4] load_state_dict strict=False, missing=%d unexpected=%d",
            len(missing), len(unexpected),
        )
    else:
        log.info("[2/4] 模型为随机初始化（random_weights）")
    model.eval()

    # ==================== 3. 导出 ONNX ====================
    dummy = torch.randn(1, 3, image_size, image_size)
    log.info(
        "[3/4] torch.onnx.export: input=(1,3,%d,%d) opset=%d -> %s",
        image_size, image_size, opset, output_path,
    )
    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        input_names=["input"],
        output_names=["output"],
        opset_version=opset,
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        do_constant_folding=True,
    )
    size_mb = output_path.stat().st_size / 1024 / 1024
    log.info("[3/4] ONNX 写出: %.1f MB", size_mb)

    # ==================== 4. onnxruntime sanity 推理 ====================
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
        out = sess.run(None, {"input": dummy.numpy()})
        out_shape = out[0].shape
        expected = (1, num_classes)
        assert out_shape == expected, f"output shape {out_shape} != {expected}"
        log.info("[4/4] onnxruntime sanity 推理 OK, output shape=%s", out_shape)
    except ImportError:
        log.warning("[4/4] onnxruntime 未安装，跳过 sanity 推理（pip install onnxruntime）")
    except Exception as e:
        log.error("[4/4] onnxruntime 推理失败: %s", e)
        raise

    return output_path


# ==================== CLI ====================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PyTorch -> ONNX 导出")
    p.add_argument("--weights", default=None, help=".pt 权重路径（与 --random 互斥）")
    p.add_argument("--random", action="store_true", help="用随机权重导出（CI/dry-run）")
    p.add_argument("--output", default="models/web_model/best.onnx", help="输出 .onnx 路径")
    p.add_argument("--model", default="tf_efficientnetv2_m", help="timm 模型名")
    p.add_argument("--num-classes", type=int, default=10)
    p.add_argument("--image-size", type=int, default=384)
    p.add_argument("--opset", type=int, default=13)
    p.add_argument("--dry-run", action="store_true", help="只打印参数，不真导出")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.random and not args.weights:
        print("[x] 必须传 --weights 或 --random", file=sys.stderr)
        return 1
    if args.dry_run:
        print("--- DRY RUN ---")
        print(f"  weights:    {args.weights}")
        print(f"  random:     {args.random}")
        print(f"  output:     {args.output}")
        print(f"  model:      {args.model}")
        print(f"  num-classes:{args.num_classes}")
        print(f"  image-size: {args.image_size}")
        print(f"  opset:      {args.opset}")
        return 0

    try:
        out = export_onnx(
            weights=Path(args.weights) if args.weights else None,
            output_path=Path(args.output),
            model_name=args.model,
            num_classes=args.num_classes,
            image_size=args.image_size,
            opset=args.opset,
            random_weights=args.random,
        )
        print(f"\n[OK] ONNX 导出成功: {out}")
        return 0
    except Exception as e:
        log.exception("导出失败: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
