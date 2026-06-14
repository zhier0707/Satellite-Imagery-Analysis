"""
下载并解压 EuroSAT RGB 数据集
===========================

数据集：欧盟联合研究中心（JRC）发布的 Sentinel-2 卫星图像分类数据集
来源：https://github.com/phelber/eurosat

执行：
    python scripts/download_eurosat.py

行为：
    - 若 data/eurosat/ 已含 10 个类别目录，跳过下载
    - 否则下载到 data/eurosat.zip 并解压
    - 完成后打印每个类别的图像数量
    - 失败时非零退出，不留半成品
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ==================== 配置 ====================
# EuroSAT 官方源（GitHub 镜像，便于国内访问）
# 原始地址：http://madm.dfki.de/files/sentinel/EuroSAT.zip （约 90MB）
# 多个备用地址，任一成功即可
DOWNLOAD_URLS = [
    # HuggingFace 中国镜像（最稳）
    "https://hf-mirror.com/datasets/torchgeo/eurosat/resolve/main/EuroSAT.zip",
    # torchgeo 官方 HuggingFace（境外环境时使用）
    "https://huggingface.co/datasets/torchgeo/eurosat/resolve/main/EuroSAT.zip",
    # Zenodo 官方托管（与原 madm.dfki.de 同一文件）
    "https://zenodo.org/record/7711810/files/EuroSAT.zip",
    # 原 madm.dfki.de 镜像（已多次 403，仅作最后兜底）
    "http://madm.dfki.de/files/sentinel/EuroSAT.zip",
]

# 校验用 MD5（torchgeo 镜像对应值）
EXPECTED_MD5 = "c8fa014336c82ac7804f0398fcb19387"

# 期望解压后的 10 个类别目录
EXPECTED_CLASSES = [
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

# 路径
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ZIP_PATH = DATA_DIR / "eurosat.zip"
EXTRACT_DIR = DATA_DIR / "eurosat"


# EuroSAT 官方 zip 内的根目录名（表示 10m 空间分辨率）
ZIP_ROOT_NAME = "2750"


# ==================== 工具函数 ====================
def is_already_extracted() -> bool:
    """检查是否已存在解压后的 10 个类别目录。"""
    if not EXTRACT_DIR.is_dir():
        return False
    missing = [c for c in EXPECTED_CLASSES if not (EXTRACT_DIR / c).is_dir()]
    if missing:
        return False
    # 至少一个类别里有图像
    sample = EXTRACT_DIR / EXPECTED_CLASSES[0]
    return any(sample.glob("*.jpg"))


def relocate_extracted() -> None:
    """EuroSAT zip 解压后根目录是 2750/，需要把里面的 10 个类别目录搬到 data/eurosat/。"""
    src_root = DATA_DIR / ZIP_ROOT_NAME
    if not src_root.is_dir():
        return
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in src_root.iterdir():
        target = EXTRACT_DIR / sub.name
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(sub), str(target))
    shutil.rmtree(src_root)


def download_with_progress(url: str, dest: Path, chunk_size: int = 64 * 1024) -> None:
    """带进度条地下载文件。"""
    print(f"  > 下载 {url}")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    bar = "=" * (pct // 2) + " " * (50 - pct // 2)
                    print(f"\r  [{bar}] {pct}% ({downloaded / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB)", end="", flush=True)
        if total > 0:
            print()  # 换行
    print(f"  > 已保存到 {dest}")


def download_with_fallback() -> None:
    """尝试多个下载源，任一成功即返回。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for url in DOWNLOAD_URLS:
        try:
            download_with_progress(url, ZIP_PATH)
            return
        except (URLError, HTTPError, TimeoutError, OSError) as e:
            print(f"  ! 失败: {e}")
            last_error = e
            if ZIP_PATH.exists():
                ZIP_PATH.unlink()
    raise RuntimeError(f"所有下载源都失败: {last_error}")


def verify_md5(path: Path, expected: str) -> bool:
    """校验文件 MD5。"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest() == expected


def safe_extract(zip_path: Path, target: Path) -> None:
    """解压 zip，处理 zip slip 漏洞。"""
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # 防止路径穿越
            member_path = (target / member.filename).resolve()
            if not str(member_path).startswith(str(target.resolve())):
                raise RuntimeError(f"非法路径: {member.filename}")
        zf.extractall(target)


def print_class_summary() -> None:
    """打印每个类别的图像数量。"""
    print("\n数据集摘要：")
    total = 0
    for cls in EXPECTED_CLASSES:
        cls_dir = EXTRACT_DIR / cls
        n = len(list(cls_dir.glob("*.jpg"))) + len(list(cls_dir.glob("*.jpeg")))
        total += n
        print(f"  {cls:<24} {n:>6} 张")
    print(f"  {'合计':<24} {total:>6} 张")


# ==================== 主流程 ====================
def main() -> int:
    print("=" * 60)
    print("EuroSAT 数据集下载")
    print("=" * 60)

    # 1. 已存在则跳过
    if is_already_extracted():
        print("✓ data/eurosat/ 已含 10 个类别目录，跳过下载")
        print_class_summary()
        return 0

    # 2. 下载
    if not ZIP_PATH.exists():
        try:
            download_with_fallback()
        except Exception as e:
            print(f"\n✗ 下载失败: {e}", file=sys.stderr)
            if ZIP_PATH.exists():
                ZIP_PATH.unlink()
            return 1
    else:
        print(f"  > 复用已存在的 {ZIP_PATH}")

    # 2.5 校验
    print(f"  > 校验 MD5 ({EXPECTED_MD5[:8]}...) ...")
    if not verify_md5(ZIP_PATH, EXPECTED_MD5):
        print(f"\n✗ MD5 校验失败，文件可能损坏", file=sys.stderr)
        ZIP_PATH.unlink(missing_ok=True)
        return 1
    print(f"  > MD5 校验通过")

    # 3. 解压
    print(f"  > 解压到 {DATA_DIR} ...")
    try:
        # 若有 2750/ 或同名目录残留，先清空
        zip_root = DATA_DIR / ZIP_ROOT_NAME
        if zip_root.exists():
            shutil.rmtree(zip_root)
        if EXTRACT_DIR.exists():
            shutil.rmtree(EXTRACT_DIR)
        safe_extract(ZIP_PATH, DATA_DIR)
        # 把 2750/AnnualCrop 等搬出来到 data/eurosat/
        relocate_extracted()
    except Exception as e:
        print(f"\n✗ 解压失败: {e}", file=sys.stderr)
        return 1

    # 4. 验证
    if not is_already_extracted():
        print("\n✗ 解压后未找到预期的 10 个类别目录，请检查 zip 包内容", file=sys.stderr)
        return 1

    # 5. 清理 zip
    ZIP_PATH.unlink(missing_ok=True)
    print(f"  > 已清理 {ZIP_PATH}")

    # 6. 摘要
    print_class_summary()
    print("\n✓ 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
