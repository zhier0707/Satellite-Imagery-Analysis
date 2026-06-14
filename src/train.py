"""
EfficientNetV2-M 微调训练入口（卫星图像土地利用分类）
=====================================================

按 卫星图像分析项目方案.md 第 3 节配置：
- 三阶段冻结/解冻微调
- AdamW（lr=1e-4, weight_decay=1e-5）
- CosineAnnealing（warmup 5 epochs）
- Label Smoothing Cross Entropy（smoothing=0.1）
- FP16 混合精度

执行示例：
    # 干跑：验证代码链路
    python src/train.py --dry-run --data-root data/eurosat

    # 真实训练 stage 1（仅分类头）
    python src/train.py --data-root data/eurosat --stage 1 --epochs 50

    # 真实训练 stage 2（解冻末 2-3 阶段）
    python src/train.py --data-root data/eurosat --stage 2 --epochs 30
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Iterator

# Windows PowerShell 默认 GBK stdout 无法输出 ✓/✗ 等 Unicode 符号，
# 这里强制 UTF-8 重配置，失败时（部分老 Windows）静默回退。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LambdaLR, SequentialLR
from torch.utils.data import DataLoader

# 允许从项目根直接 import
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.dataset import EUROSAT_CLASSES, make_loaders  # noqa: E402

try:
    import timm  # noqa: F401
except ImportError:
    print("✗ 缺少 timm，请先 `pip install timm`", file=sys.stderr)
    sys.exit(1)


# ==================== 参数 ====================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="EfficientNetV2-M EuroSAT 微调")
    p.add_argument("--data-root", default="data/eurosat", help="数据集根目录")
    p.add_argument("--stage", type=int, choices=[1, 2, 3], default=2, help="微调阶段")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--weight-decay", type=float, default=1e-5)
    p.add_argument("--label-smoothing", type=float, default=0.1)
    p.add_argument("--warmup-epochs", type=int, default=5)
    p.add_argument("--image-size", type=int, default=384)
    p.add_argument("--num-workers", type=int, default=4)
    p.add_argument("--num-classes", type=int, default=len(EUROSAT_CLASSES))
    p.add_argument("--model", default="tf_efficientnetv2_m", help="timm 模型名")
    p.add_argument("--output-dir", default="models/checkpoints", help="检查点输出目录")
    p.add_argument("--dry-run", action="store_true", help="只跑 1 个 batch，不存盘")
    p.add_argument("--no-pretrained", action="store_true", help="不下载 ImageNet 预训练权重（用于离线干跑）")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    # 恢复训练（Task 7）
    p.add_argument("--resume-from", default=None, help="从检查点恢复训练（.pt 路径）")
    # 早停与检查点轮转（Task 8）
    p.add_argument("--early-stop-patience", type=int, default=0,
                   help="验证集不提升的连续 epoch 数达到该阈值则早停；0 禁用")
    p.add_argument("--save-every", type=int, default=0,
                   help="每 N 个 epoch 多保存一份纯权重（仅 model state_dict）；0 禁用")
    # TensorBoard（Task 9）
    p.add_argument("--tensorboard-dir", default=None,
                   help="TensorBoard 日志目录；不传则禁用")
    return p.parse_args()


# ==================== 模型 ====================
def build_model(model_name: str, num_classes: int, pretrained: bool = True) -> nn.Module:
    """创建模型（可选 ImageNet 预训练）。"""
    return timm.create_model(model_name, pretrained=pretrained, num_classes=num_classes)


def apply_stage_freezing(model: nn.Module, stage: int) -> int:
    """按文档 3.3 节实现三阶段冻结/解冻，返回可训练参数数量。

    timm 的 tf_efficientnetv2_m 结构：
        conv_stem -> bn1 -> blocks (Sequential of 7 stage-Sequentials)
        -> conv_head -> bn2 -> global_pool -> classifier (Linear)
    """
    # 全部先冻结
    for p in model.parameters():
        p.requires_grad = False

    if stage == 1:
        # Stage 1：仅训练分类头
        for p in model.get_classifier().parameters():
            p.requires_grad = True
    elif stage == 2:
        # Stage 2：解冻末 2 个 stage + 分类头 + 头部卷积（conv_head / bn2）
        blocks = getattr(model, "blocks", None)
        if blocks is not None and len(blocks) >= 2:
            for s in list(blocks)[-2:]:
                for p in s.parameters():
                    p.requires_grad = True
        for attr in ("conv_head", "bn2", "classifier"):
            mod = getattr(model, attr, None)
            if mod is not None:
                for p in mod.parameters():
                    p.requires_grad = True
    else:
        # Stage 3：全量解冻
        for p in model.parameters():
            p.requires_grad = True

    return sum(p.numel() for p in model.parameters() if p.requires_grad)


# ==================== 调度器 ====================
def make_scheduler(
    optimizer: torch.optim.Optimizer,
    epochs: int,
    warmup_epochs: int,
) -> LambdaLR:
    """Warmup（线性） + Cosine Annealing。"""
    def lr_lambda(epoch: int) -> float:
        if epoch < warmup_epochs:
            return (epoch + 1) / max(1, warmup_epochs)
        progress = (epoch - warmup_epochs) / max(1, epochs - warmup_epochs)
        return 0.5 * (1.0 + math.cos(math.pi * progress))
    return LambdaLR(optimizer, lr_lambda)


# ==================== 损失 ====================
def make_loss(smoothing: float) -> nn.Module:
    """Label Smoothing Cross Entropy。"""
    return nn.CrossEntropyLoss(label_smoothing=smoothing)


# ==================== 检查点 ====================
def save_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler,
    scaler: GradScaler,
    epoch: int,
    val_acc: float,
) -> None:
    """写入完整训练状态（model/optimizer/scheduler/scaler/epoch/val_acc）。

    last.pt 走此格式，用于恢复训练。
    best.pt / epoch{N}.pt 由调用方按需用更精简的 dict。
    """
    torch.save({
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "scaler": scaler.state_dict(),
        "epoch": epoch,
        "val_acc": val_acc,
    }, path)


# ==================== 评估 ====================
@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str) -> tuple[float, float]:
    model.eval()
    total = 0
    correct = 0
    loss_sum = 0.0
    loss_fn = nn.CrossEntropyLoss()
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with autocast():
            logits = model(x)
            loss = loss_fn(logits, y)
        loss_sum += loss.item() * x.size(0)
        pred = logits.argmax(dim=1)
        total += x.size(0)
        correct += (pred == y).sum().item()
    return loss_sum / max(1, total), correct / max(1, total)


# ==================== 训练主循环 ====================
def train(args: argparse.Namespace) -> int:
    print("=" * 60)
    print(f"Train Config  stage={args.stage}  epochs={args.epochs}  "
          f"batch={args.batch_size}  lr={args.lr}  device={args.device}")
    print("=" * 60)

    # Data
    print(f"[1/5] loading data from {args.data_root} ...")
    train_loader, val_loader, test_loader = make_loaders(
        args.data_root, args.batch_size, args.num_workers, args.image_size
    )
    print(f"      train={len(train_loader.dataset)}  "
          f"val={len(val_loader.dataset)}  test={len(test_loader.dataset)}")

    # Model
    print(f"[2/5] building model {args.model} ...")
    model = build_model(args.model, args.num_classes, pretrained=not args.no_pretrained).to(args.device)
    n_trainable = apply_stage_freezing(model, args.stage)
    n_total = sum(p.numel() for p in model.parameters())
    print(f"      总参 {n_total/1e6:.1f}M  可训练 {n_trainable/1e6:.1f}M")

    # 优化器 / 调度器 / 损失 / 混合精度
    print("[3/5] 配置优化器 ...")
    optimizer = AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.lr, weight_decay=args.weight_decay,
    )
    scheduler = make_scheduler(optimizer, args.epochs, args.warmup_epochs)
    loss_fn = make_loss(args.label_smoothing)
    scaler = GradScaler()

    if args.dry_run:
        print("[4/5] DRY RUN：跑 1 个 batch ...")
        model.train()
        x, y = next(iter(train_loader))
        x, y = x.to(args.device), y.to(args.device)
        optimizer.zero_grad()
        with autocast():
            logits = model(x)
            loss = loss_fn(logits, y)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        print(f"      loss={loss.item():.4f}  shape={tuple(logits.shape)}")
        print("✓ dry run 通过")
        return 0

    # 真实训练
    print(f"[4/5] 训练 {args.epochs} epochs ...")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ============== 恢复训练（Task 7） ==============
    start_epoch = 0
    best_val_acc = 0.0
    if args.resume_from:
        resume_path = Path(args.resume_from)
        if not resume_path.is_file():
            print(f"[x] --resume-from 文件不存在: {resume_path}", file=sys.stderr)
            return 1
        ckpt = torch.load(resume_path, map_location="cpu")
        # 兼容旧 checkpoint：缺字段时给出合理默认
        missing, unexpected = model.load_state_dict(ckpt.get("model", {}), strict=False)
        if missing or unexpected:
            print(f"[!] 权重恢复 strict=False  missing={len(missing)}  unexpected={len(unexpected)}")
        optimizer.load_state_dict(ckpt["optimizer"])
        scheduler.load_state_dict(ckpt["scheduler"])
        scaler.load_state_dict(ckpt["scaler"])
        start_epoch = ckpt.get("epoch", -1) + 1
        best_val_acc = ckpt.get("val_acc", 0.0)
        print(f"✓ Resumed from epoch {start_epoch}, best_val_acc={best_val_acc:.4f}")

    # ============== TensorBoard（Task 9） ==============
    # 重要兼容：tf gfile 的 C 实现在 Windows + 中文路径下硬编码 UTF-8 解码，
    # 会抛 `'utf-8' codec can't decode byte 0xc6` 错误。先把 logdir 解析为
    # 绝对路径，再用纯 ASCII 临时目录绕过 gfile，训练结束再把 events 文件
    # 复制回用户期望的中文目录。
    import tempfile
    import shutil
    writer = None
    tb_user_dir: Path | None = None
    tb_actual_dir: Path | None = None
    if args.tensorboard_dir:
        from torch.utils.tensorboard import SummaryWriter
        tb_user_dir = Path(args.tensorboard_dir).resolve()
        # ASCII 临时目录（短路径，避开 gfile 中文 bug）
        tb_actual_dir = Path(tempfile.mkdtemp(prefix="tb_", dir="C:\\"))
        writer = SummaryWriter(log_dir=str(tb_actual_dir))
        print(f"      TensorBoard 日志 -> {tb_actual_dir} (将合并到 {tb_user_dir})")

    # ============== 训练循环（Task 7/8/9 整合） ==============
    patience = args.early_stop_patience
    save_every = args.save_every
    patience_counter = 0
    global_step = 0
    early_stopped = False
    stopped_epoch = args.epochs

    for epoch in range(start_epoch, args.epochs):
        model.train()
        t0 = time.time()
        loss_sum = 0.0
        seen = 0
        for x, y in train_loader:
            x, y = x.to(args.device), y.to(args.device)
            optimizer.zero_grad()
            with autocast():
                logits = model(x)
                loss = loss_fn(logits, y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            loss_sum += loss.item() * x.size(0)
            seen += x.size(0)
            if writer is not None:
                writer.add_scalar("train/loss", loss.item(), global_step)
            global_step += 1
        scheduler.step()
        train_loss = loss_sum / max(1, seen)
        val_loss, val_acc = evaluate(model, val_loader, args.device)
        dt = time.time() - t0
        cur_lr = optimizer.param_groups[0]["lr"]

        if writer is not None:
            writer.add_scalar("val/loss", val_loss, epoch)
            writer.add_scalar("val/acc", val_acc, epoch)
            writer.add_scalar("train/lr", cur_lr, epoch)

        print(f"  epoch {epoch+1:>3}/{args.epochs}  "
              f"train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  "
              f"val_acc={val_acc:.4f}  lr={cur_lr:.2e}  ({dt:.1f}s)")

        # 每 epoch 末尾无条件保存 last.pt（完整 dict，用于恢复）
        save_checkpoint(
            output_dir / "last.pt", model, optimizer, scheduler, scaler, epoch, val_acc
        )

        # 验证集提升 -> 保存 best.pt（仅 model state，节省空间）
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience_counter = 0
            torch.save(
                {"model": model.state_dict(), "val_acc": val_acc, "epoch": epoch},
                output_dir / "best.pt",
            )
            print(f"      ↳ 保存最佳检查点 -> {output_dir / 'best.pt'}  val_acc={val_acc:.4f}")
        else:
            patience_counter += 1

        # 周期保存（仅 model state）
        if save_every > 0 and (epoch + 1) % save_every == 0:
            torch.save(model.state_dict(), output_dir / f"epoch{epoch+1}.pt")
            print(f"      ↳ 保存周期检查点 -> {output_dir / f'epoch{epoch+1}.pt'}")

        # 早停
        if patience > 0 and patience_counter >= patience:
            stopped_epoch = epoch + 1
            early_stopped = True
            print(f"Early stopping at epoch {stopped_epoch}")
            break

    # ============== 测试 ==============
    print("[5/5] 测试集评估 ...")
    test_loss, test_acc = evaluate(model, test_loader, args.device)
    print(f"      test_loss={test_loss:.4f}  test_acc={test_acc:.4f}")

    if writer is not None:
        writer.close()
        # 把 ASCII 临时目录里的 events 文件复制回用户指定的中文目录
        if tb_user_dir is not None and tb_actual_dir is not None:
            tb_user_dir.mkdir(parents=True, exist_ok=True)
            for ev in tb_actual_dir.glob("events.out.tfevents.*"):
                target = tb_user_dir / ev.name
                shutil.copy2(ev, target)
                print(f"      ↳ 复制 events -> {target}")
            # 清理临时目录
            try:
                shutil.rmtree(tb_actual_dir)
            except OSError:
                pass

    if early_stopped:
        print(f"Early stopped at epoch {stopped_epoch}")
    else:
        print("✓ Training completed")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return train(args)
    except KeyboardInterrupt:
        print("\n[x] user interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
