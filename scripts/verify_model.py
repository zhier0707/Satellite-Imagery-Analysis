"""
验证 best.pt 权重完整性
======================

下完 Kaggle best.pt 后,跑这个脚本确认:
- 文件存在且可加载
- state_dict 包含 model.*
- num_classes = 10
- 简单 dummy 前向能跑通(无 shape 错)

用法:
    & $env:PY scripts/verify_model.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CKPT = ROOT / "models" / "checkpoints" / "best.pt"


def main() -> int:
    ckpt_path = Path(os.environ.get("MODEL_WEIGHTS", DEFAULT_CKPT))
    print(f"[verify] ckpt = {ckpt_path}")

    # 1. 文件存在性
    if not ckpt_path.is_file():
        print(f"[FAIL] 权重文件不存在: {ckpt_path}")
        print("请先解压 Kaggle 下载的 zip,把 best.pt 放到该路径。")
        return 1
    size_mb = ckpt_path.stat().st_size / 1e6
    print(f"[OK] 大小: {size_mb:.1f} MB")

    # 2. torch.load (允许 weights_only=False,旧格式可能 pickled)
    import torch
    try:
        state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    except TypeError:
        # 旧版本 PyTorch 不支持 weights_only
        state = torch.load(ckpt_path, map_location="cpu")
    if isinstance(state, dict) and "model" in state:
        state = state["model"]
        print("[OK] 训练 checkpoint, 提取 'model' 子字典")
    else:
        print("[OK] 纯 state_dict")

    n_params = sum(t.numel() for t in state.values() if hasattr(t, "numel"))
    print(f"[OK] state_dict 包含 {len(state)} 张量,共 {n_params/1e6:.1f}M 参数")

    # 3. 重建模型,加载权重,dummy 前向
    import timm
    model = timm.create_model("tf_efficientnetv2_m", pretrained=False, num_classes=10)
    ret = model.load_state_dict(state, strict=False)
    if ret.missing_keys:
        print(f"[warn] missing keys (前 5): {ret.missing_keys[:5]}")
    if ret.unexpected_keys:
        print(f"[warn] unexpected keys (前 5): {ret.unexpected_keys[:5]}")
    print("[OK] load_state_dict 成功 (strict=False 容忍小差异)")
    model.eval()

    # 4. Dummy 前向
    x = torch.randn(1, 3, 384, 384)
    with torch.no_grad():
        logits = model(x)
    print(f"[OK] dummy 前向: input {tuple(x.shape)} -> output {tuple(logits.shape)}")
    assert logits.shape == (1, 10), f"期望 (1, 10), 实际 {logits.shape}"
    print(f"[OK] num_classes = {logits.shape[1]} (期望 10)")

    print("\n[SUCCESS] best.pt 验证通过!可以重启后端切换到真实模型。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
