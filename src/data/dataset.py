"""EuroSAT 数据加载器与数据增强。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Tuple

from torch.utils.data import DataLoader, random_split
from torchvision import transforms
from torchvision.datasets import ImageFolder

# 10 个 EuroSAT 类别
EUROSAT_CLASSES = [
    "AnnualCrop",
    "Forest",
    "HerbaceousVegetation",
    "Highway",
    "Industrial",
    "Pasture",
    "PermanentCrop",
    "Residential",
    "River",
    "SeaLake",
]

# ImageNet 预训练模型的归一化参数（timm 内部转换最终会归一化到同分布）
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transforms(
    image_size: int = 384,
    train: bool = True,
) -> transforms.Compose:
    """构造训练/验证变换。

    训练：随机翻转、旋转、色彩抖动、归一化
    验证：缩放 + 中心裁剪 + 归一化
    """
    if train:
        return transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(degrees=15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def make_datasets(
    data_root: str | Path,
    image_size: int = 384,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    seed: int = 42,
) -> Tuple[ImageFolder, ImageFolder, ImageFolder]:
    """构造训练/验证/测试三个 ImageFolder。

    使用 random_split 切分（70/20/10），返回的对象共享同一图像列表。
    """
    data_root = Path(data_root)
    if not data_root.is_dir():
        raise FileNotFoundError(f"数据集根目录不存在: {data_root}")

    train_tf = build_transforms(image_size, train=True)
    eval_tf = build_transforms(image_size, train=False)

    full = ImageFolder(root=str(data_root))
    if not full.classes:
        raise RuntimeError(f"在 {data_root} 下未发现任何类别子目录")

    # 70/20/10 切分
    n = len(full)
    n_test = int(n * test_ratio)
    n_val = int(n * val_ratio)
    n_train = n - n_test - n_val
    g = torch.Generator().manual_seed(seed)
    splits = random_split(full, [n_train, n_val, n_test], generator=g)

    # 把不同的 transform 绑回去
    train_ds = _TransformDataset(splits[0], train_tf)
    val_ds = _TransformDataset(splits[1], eval_tf)
    test_ds = _TransformDataset(splits[2], eval_tf)
    return train_ds, val_ds, test_ds


def make_loaders(
    data_root: str | Path,
    batch_size: int = 16,
    num_workers: int = 4,
    image_size: int = 384,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """构造数据加载器。"""
    train_ds, val_ds, test_ds = make_datasets(data_root, image_size)
    return (
        DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=True),
        DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True),
        DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True),
    )


# ==================== 内部 ====================
import torch  # 放在下面避免循环引用


class _TransformDataset(torch.utils.data.Dataset):
    """把 random_split 子集包一层，加 transform。"""

    def __init__(self, subset: torch.utils.data.Subset, transform: Callable):
        self.subset = subset
        self.transform = transform
        # 继承类别映射
        self.classes = subset.dataset.classes
        self.class_to_idx = subset.dataset.class_to_idx

    def __len__(self) -> int:
        return len(self.subset)

    def __getitem__(self, idx: int):
        path, label = self.subset.dataset.samples[self.subset.indices[idx]]
        from PIL import Image
        img = Image.open(path).convert("RGB")
        return self.transform(img), label
