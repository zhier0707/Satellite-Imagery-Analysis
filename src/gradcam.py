"""
Grad-CAM 类别激活热力图
=======================

按 卫星图像分析项目方案.md 5.2 节实现：
- 前向 hook 收集目标层激活
- 反向 hook 收集目标层梯度
- 梯度全局平均作为权重，加权求和
- ReLU、归一化、上采样到原图尺寸

目标层：
    timm 的 tf_efficientnetv2_m 推荐用 model.conv_head
    （最后 1x1 卷积，输出 1280 通道的特征图）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Tuple

# ==================== 让 `python src/gradcam.py` 也能找到 `src.data` ====================
# 必须放在所有项目内 import 之前
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def generate_gradcam(
    model: nn.Module,
    input_tensor: torch.Tensor,
    target_layer: nn.Module,
    target_class: int | None = None,
) -> np.ndarray:
    """对单张输入图像生成 Grad-CAM 热力图。

    Args:
        model: 已切换到 eval 模式的 nn.Module
        input_tensor: shape (1, 3, H, W) 的张量，已归一化
        target_layer: 用于提取特征图的子模块
        target_class: 目标类别索引；None 时取 top-1

    Returns:
        shape (H, W) 的 numpy 数组，值域 [0, 1]
    """
    model.eval()
    activations: list[torch.Tensor] = []
    gradients: list[torch.Tensor] = []

    def forward_hook(_module, _input, output):
        activations.append(output.detach())

    def backward_hook(_module, _grad_input, grad_output):
        gradients.append(grad_output[0].detach())

    fh = target_layer.register_forward_hook(forward_hook)
    bh = target_layer.register_full_backward_hook(backward_hook)

    try:
        # 前向
        output = model(input_tensor)
        if target_class is None:
            target_class = int(output.argmax(dim=1).item())
        # 反向
        model.zero_grad()
        one_hot = torch.zeros_like(output)
        one_hot[0, target_class] = 1.0
        output.backward(gradient=one_hot, retain_graph=True)
    finally:
        fh.remove()
        bh.remove()

    if not activations or not gradients:
        raise RuntimeError("Hook 未捕获到激活或梯度，请检查目标层是否正确")

    # 梯度与激活 shape: (1, C, h, w)
    gradient = gradients[0].cpu().numpy()[0]   # (C, h, w)
    activation = activations[0].cpu().numpy()[0]  # (C, h, w)

    # 通道维全局平均 -> (C,)
    weights = np.mean(gradient, axis=(1, 2))
    cam = np.zeros(activation.shape[1:], dtype=np.float32)
    for i, w in enumerate(weights):
        cam += w * activation[i]

    cam = np.maximum(cam, 0)  # ReLU
    # 归一化到 [0, 1]
    if cam.max() > cam.min():
        cam = (cam - cam.min()) / (cam.max() - cam.min())
    else:
        cam = np.zeros_like(cam)

    # 上采样到输入尺寸
    _, _, H, W = input_tensor.shape
    cam = cv2.resize(cam, (W, H))
    return cam


def overlay_heatmap(
    img: np.ndarray,
    cam: np.ndarray,
    alpha: float = 0.4,
    colormap: int = cv2.COLORMAP_JET,
) -> np.ndarray:
    """把热力图叠加到原图上。

    Args:
        img: HxWx3 的 BGR 图像（cv2 读取）
        cam: HxW 的 [0,1] 浮点热力图
        alpha: 透明度
        colormap: cv2 colormap

    Returns:
        BGR 叠加图
    """
    heatmap = np.uint8(255 * cam)
    heatmap = cv2.applyColorMap(heatmap, colormap)
    if img.shape[:2] != heatmap.shape[:2]:
        img = cv2.resize(img, (heatmap.shape[1], heatmap.shape[0]))
    return cv2.addWeighted(img, 1 - alpha, heatmap, alpha, 0)


# ==================== CLI ====================
def get_target_layer(model: nn.Module) -> nn.Module:
    """为 timm tf_efficientnetv2_m 选择默认目标层。"""
    # 1x1 卷积，输出 1280 通道
    if hasattr(model, "conv_head"):
        return model.conv_head
    raise ValueError("无法自动定位目标层，请显式传入 target_layer")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Grad-CAM 单图热力图")
    p.add_argument("--image", required=True, help="输入图像路径")
    p.add_argument("--weights", default=None, help="模型权重 .pt 路径；不传则用随机初始化")
    p.add_argument("--model", default="tf_efficientnetv2_m")
    p.add_argument("--num-classes", type=int, default=10)
    p.add_argument("--image-size", type=int, default=384)
    p.add_argument("--output", default="reports/gradcam.png", help="热力图保存路径")
    p.add_argument("--alpha", type=float, default=0.4)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        import timm
        from torchvision import transforms

        from src.data.dataset import IMAGENET_MEAN, IMAGENET_STD  # noqa: E501
    except ImportError as e:
        print(f"[x] missing dep: {e}", file=sys.stderr)
        return 1

    print(f"[1/3] loading model {args.model} ...")
    model = timm.create_model(args.model, pretrained=False, num_classes=args.num_classes)
    if args.weights and Path(args.weights).is_file():
        ckpt = torch.load(args.weights, map_location="cpu")
        state = ckpt.get("model", ckpt)
        model.load_state_dict(state, strict=False)
        print(f"      loaded weights from {args.weights}")
    else:
        print("      using random init (no weights provided)")

    model.eval()

    # 读取图像
    print(f"[2/3] reading image {args.image} ...")
    img = cv2.imread(args.image)
    if img is None:
        print(f"[x] cannot read image: {args.image}", file=sys.stderr)
        return 1
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((args.image_size, args.image_size)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    tensor = transform(rgb).unsqueeze(0).requires_grad_(True)

    # 推理 + Grad-CAM
    print(f"[3/3] generating Grad-CAM ...")
    target_layer = get_target_layer(model)
    cam = generate_gradcam(model, tensor, target_layer=target_layer)
    overlay = overlay_heatmap(img, cam, alpha=args.alpha)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), overlay)
    print(f"      saved -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
