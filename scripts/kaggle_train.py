"""
Kaggle Notebook 一键训练脚本
=========================================================
把整个文件的所有 cell 直接粘到 Kaggle Notebook（GPU accelerator），
按顺序执行即可完成：克隆项目 → 装 timm → 验证数据 → 训练 → 打包下载。

环境约定：
- Kaggle 默认 Python 3.10，PyTorch 2.x 已预装
- /kaggle/input/<dataset>/<path>   数据集挂载点（只读）
- /kaggle/working/                  训练输出（容器重启清空，但会自动生成下载链接）

使用步骤：
1. Kaggle.com → New Notebook
2. Settings → Accelerator = GPU T4 x2（免费 30h/周）
3. Add Data → 搜 "eurosat-10class"（先在 Dataset 页面创建）
4. 整个文件全选粘进一个 cell
5. 编辑下方 CONFIG 段的路径，点运行
"""
from __future__ import annotations

# ============================================================
# CONFIG（按你的实际值改这 3 行即可）
# ============================================================
PROJECT_REPO = "https://github.com/zhier0707/Satellite-Imagery-Analysis.git"
DATASET_ROOT = "/kaggle/input/eurosat-10class/eurosat"   # 你的 Kaggle Dataset 根目录
RUN_TAG      = "stage1-baseline"                          # 训练名（决定输出目录）

# 训练超参（Kaggle GPU T4/P100 默认 batch 16 即可，OOM 再降）
STAGE    = 1        # 1=仅解冻分类头；2=解冻末 2-3 阶段；3=全量微调
EPOCHS   = 5        # Kaggle 跑 1-2 epoch 试水；本地试好再 50
BATCH    = 16
LR       = 1e-3
IMAGE_SZ = 384      # EfficientNetV2-M 推荐 384；想快用 224
# ============================================================


# ============================================================
# Cell 1: 克隆项目
# ============================================================
import os
import subprocess
import sys

WORK = "/kaggle/working"
os.chdir(WORK)
if not os.path.isdir(os.path.join(WORK, "Satellite-Imagery-Analysis")):
    print("[STEP] git clone ...")
    subprocess.check_call(["git", "clone", "--depth", "1", PROJECT_REPO])
else:
    print("[SKIP] repo already cloned, pulling latest ...")
    subprocess.check_call(["git", "-C", "Satellite-Imagery-Analysis", "pull", "--ff-only"])

os.chdir(os.path.join(WORK, "Satellite-Imagery-Analysis"))
print(f"[OK] cwd = {os.getcwd()}")


# ============================================================
# Cell 2: 装缺失依赖（Kaggle 默认有 torch/torchvision，无 timm）
# ============================================================
def pip_install_quiet(pkg: str) -> None:
    print(f"[pip] {pkg}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

pip_install_quiet("timm>=0.9.12")
pip_install_quiet("matplotlib>=3.7.0")
pip_install_quiet("opencv-python>=4.8.0")

print("[OK] deps ready")


# ============================================================
# Cell 3: 验证数据 + 打印硬件信息
# ============================================================
import shutil
import torch


def auto_detect_data_root(preferred: str | None = None) -> str:
    """
    智能探测 Kaggle 上的 EuroSAT 数据集根目录。

    优先级：
      1. 用户在 CONFIG 段填的 DATASET_ROOT（且该路径存在 10 个类别子目录）
      2. /kaggle/input/ 下名字含 'eurosat' 的 dataset
      3. /kaggle/input/ 下任何含 10 个子目录且子目录里有 jpg 的路径
    """
    if preferred and os.path.isdir(preferred):
        classes = [d for d in os.listdir(preferred) if os.path.isdir(os.path.join(preferred, d))]
        if len(classes) >= 2:  # 至少 2 个类别算通过
            print(f"[detect] using preferred: {preferred} ({len(classes)} classes)")
            return preferred

    candidates = []
    for entry in sorted(os.listdir("/kaggle/input")):
        full = f"/kaggle/input/{entry}"
        if not os.path.isdir(full):
            continue
        # 找含 10 个类别子目录的路径
        for root, dirs, _files in os.walk(full):
            jpg_dirs = [d for d in dirs if os.path.isdir(os.path.join(root, d))]
            jpg_count = sum(1 for _f in os.listdir(root) if _f.lower().endswith((".jpg", ".jpeg")))
            if 5 <= len(jpg_dirs) <= 20 and jpg_count < 5:
                # 这一级有 ~10 个子目录,几乎就是 eurosat 根
                candidates.append((entry, root, len(jpg_dirs)))
                break
        # 也考虑直接是根
        subdirs = [d for d in os.listdir(full) if os.path.isdir(os.path.join(full, d))]
        if 5 <= len(subdirs) <= 20:
            # 检查是否像 eurosat
            sample = subdirs[0]
            sample_files = os.listdir(os.path.join(full, sample))
            n_jpg = sum(1 for f in sample_files if f.lower().endswith((".jpg", ".jpeg")))
            if n_jpg > 100:
                candidates.append((entry, full, len(subdirs)))

    if not candidates:
        raise SystemExit(
            f"[x] 无法自动探测 EuroSAT 路径, 请在 CONFIG 段显式填 DATASET_ROOT\n"
            f"   提示: !ls /kaggle/input/  看看实际 dataset 名字"
        )
    # 优先选名字含 'eurosat' 的
    candidates.sort(key=lambda c: ("eurosat" not in c[0].lower(), c[0]))
    chosen = candidates[0]
    print(f"[detect] auto-resolved: {chosen[1]} (dataset={chosen[0]}, {chosen[2]} classes)")
    return chosen[1]


DATASET_ROOT = auto_detect_data_root(DATASET_ROOT)
classes = sorted(os.listdir(DATASET_ROOT))
assert len(classes) == 10, f"期望 10 个类别, 实际 {len(classes)}: {classes}"
n_imgs = sum(
    len(files)
    for _, _, files in os.walk(DATASET_ROOT)
)
print(f"[OK] 数据集: {DATASET_ROOT}")
print(f"     类别: {classes}")
print(f"     总图数: {n_imgs}")
print(f"     PyTorch: {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"     GPU: {torch.cuda.get_device_name(0)}  "
          f"({torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB)")


# ============================================================
# Cell 4: 训练
# ============================================================
OUTPUT_DIR = f"/kaggle/working/checkpoints/{RUN_TAG}"
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"[STEP] training -> {OUTPUT_DIR}")

cmd = [
    sys.executable, "src/train.py",
    "--data-root", DATASET_ROOT,
    "--stage", str(STAGE),
    "--epochs", str(EPOCHS),
    "--batch-size", str(BATCH),
    "--lr", str(LR),
    "--image-size", str(IMAGE_SZ),
    "--output-dir", OUTPUT_DIR,
]
print(" ".join(cmd))
ret = subprocess.call(cmd)
if ret != 0:
    raise SystemExit(f"[FAIL] train.py 退出码 {ret}")
print(f"[OK] training finished")


# ============================================================
# Cell 5: 打包权重 + 打印下载入口
# ============================================================
ckpt_dir = OUTPUT_DIR
if not os.path.isdir(ckpt_dir):
    raise SystemExit(f"未找到 checkpoint 目录: {ckpt_dir}")

# 找到 best.pt / last.pt
best = os.path.join(ckpt_dir, "best.pt")
last = os.path.join(ckpt_dir, "last.pt")
print(f"[OK] best: {os.path.getsize(best)/1e6:.1f} MB" if os.path.isfile(best) else "[!] no best.pt")
print(f"[OK] last: {os.path.getsize(last)/1e6:.1f} MB" if os.path.isfile(last) else "[!] no last.pt")

# 打包成 zip 方便 Kaggle Output 面板下载
zip_base = f"/kaggle/working/{RUN_TAG}_checkpoints"
shutil.make_archive(zip_base, "zip", ckpt_dir)
zip_path = zip_base + ".zip"
print(f"\n[DONE] {zip_path}  ({os.path.getsize(zip_path)/1e6:.1f} MB)")
print("下载: 右侧 Output 面板 → 点击 zip 文件下载")
print()
print("回本地后放到:")
print("  e:/truth-视觉实践/models/checkpoints/best.pt")
print()
print("回本地后端启用真实推理:")
print("  cd backend && python -c \"from backend.api.classify import load_model; load_model('models/checkpoints/best.pt')\"")
