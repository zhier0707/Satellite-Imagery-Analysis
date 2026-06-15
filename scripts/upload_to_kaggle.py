"""
一键上传 EuroSAT 到 Kaggle Datasets
=========================================================
依赖：pip install kaggle
认证（选一种）：
  1. 把 kaggle.json 放在 ~/.kaggle/kaggle.json（推荐）
  2. 或设环境变量：KAGGLE_USERNAME / KAGGLE_KEY

用法：
  $PY scripts/upload_to_kaggle.py                       # 默认上传 data/eurosat
  $PY scripts/upload_to_kaggle.py --slug myname/eurosat-10class
  $PY scripts/upload_to_kaggle.py --dry-run            # 不真传，只校验
  $PY scripts/upload_to_kaggle.py --yes                 # 跳过确认

上传后：
  - Kaggle 会发邮件通知
  - 在 https://www.kaggle.com/<username>/eurosat-10class 可见
  - 然后去 Kaggle Notebook → Add Data → 搜 "eurosat-10class" 即可
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_data_dir(arg: str) -> Path:
    p = Path(arg).resolve()
    if not p.is_dir():
        raise SystemExit(f"[x] 数据目录不存在: {p}")
    subdirs = sorted([d for d in p.iterdir() if d.is_dir()])
    if len(subdirs) != 10:
        print(f"[!] 警告: {p} 下有 {len(subdirs)} 个子目录, 期望 10 (EuroSAT 类别)")
    n_files = sum(1 for _ in p.rglob("*") if _.is_file())
    print(f"[OK] 数据目录: {p}  ({n_files} files, {len(subdirs)} classes)")
    return p


def ensure_kaggle_cli() -> None:
    # 用 pip show 代替 import，避免 kaggle 包 import 时自动触发 auth
    r = subprocess.run(
        [sys.executable, "-m", "pip", "show", "kaggle"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("[i] 未安装 kaggle 包, 正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "kaggle>=1.6.0"])
    k = shutil.which("kaggle")
    if not k:
        raise SystemExit("[x] 安装了 kaggle 但找不到 kaggle 命令, 请检查 PATH")


def check_credentials() -> None:
    # 新版 (Kaggle 2024+): KAGGLE_API_TOKEN = KGAT_xxx
    env_token = os.environ.get("KAGGLE_API_TOKEN")
    access_token_file = Path.home() / ".kaggle" / "access_token"
    if env_token:
        print(f"[OK] 使用 $env:KAGGLE_API_TOKEN ({len(env_token)} chars, KGAT_*)")
        return
    if access_token_file.is_file():
        size = access_token_file.stat().st_size
        if size > 30:  # KGAT_ token 36 chars
            print(f"[OK] 使用 {access_token_file} (新版 KGAT_*, {size} bytes)")
            return
        else:
            print(f"[!] {access_token_file} 存在但 size={size} 异常")

    # 旧版: KAGGLE_USERNAME + KAGGLE_KEY
    env_user = os.environ.get("KAGGLE_USERNAME")
    env_key = os.environ.get("KAGGLE_KEY")
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if env_user and env_key:
        print(f"[OK] 使用环境变量 (旧版) (user={env_user})")
        return
    if kaggle_json.is_file():
        try:
            import json
            with kaggle_json.open() as f:
                cfg = json.load(f)
            print(f"[OK] 使用 {kaggle_json} (旧版) (user={cfg.get('username')})")
            return
        except Exception as e:
            raise SystemExit(f"[x] {kaggle_json} 解析失败: {e}")

    raise SystemExit(
        "[x] 未找到 Kaggle 认证。\n"
        "  方案 A (新版, 推荐): 把 KGAT_xxx token 存到 %USERPROFILE%\\.kaggle\\access_token\n"
        "          (kaggle.com/settings → API → Create New Token)\n"
        "  方案 B (新版 env):  $env:KAGGLE_API_TOKEN = 'KGAT_...'\n"
        "  方案 C (旧版):  把 kaggle.json 放到 %USERPROFILE%\\.kaggle\\kaggle.json\n"
        "  方案 D (旧版 env):  $env:KAGGLE_USERNAME = 'user'; $env:KAGGLE_KEY = 'key'\n"
    )


def dataset_exists(slug: str) -> bool:
    r = subprocess.run(
        ["kaggle", "datasets", "status", slug],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and "ready" in r.stdout.lower()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default=str(ROOT / "data" / "eurosat"),
                   help="本地 EuroSAT 根目录 (default: data/eurosat)")
    p.add_argument("--slug", default="eurosat-10class",
                   help="Kaggle Dataset slug (default: eurosat-10class)\n"
                        "首次上传会变成 <你的用户名>/<slug>\n"
                        "更新已存在 dataset 用同样 slug")
    p.add_argument("--title", default="EuroSAT 10-class Sentinel-2 RGB",
                   help="Dataset 标题 (default: EuroSAT 10-class Sentinel-2 RGB)")
    p.add_argument("--dry-run", action="store_true",
                   help="只检查不传")
    p.add_argument("--yes", action="store_true",
                   help="跳过交互确认")
    return p.parse_args()


def write_dataset_metadata(data_dir: Path, slug: str, title: str) -> Path:
    """新版 kaggle CLI 用 datasets-metadata.json 而不是 --title 参数"""
    meta = {
        "title": title,
        "id": slug,                       # 创建时也可以只填 title,id 由 Kaggle 分配
        "licenses": [{"name": "CC0-1.0"}],
    }
    meta_path = data_dir / "datasets-metadata.json"
    import json
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[OK] metadata -> {meta_path}")
    return meta_path


def main() -> int:
    args = parse_args()

    print("=" * 60)
    print("  EuroSAT → Kaggle Datasets 一键上传")
    print("=" * 60)

    data_dir = find_data_dir(args.data_dir)
    ensure_kaggle_cli()

    if args.dry_run:
        full_slug = args.slug if "/" in args.slug else f"<username>/{args.slug}"
        print(f"\n[DRY-RUN] 不实际执行, 上传命令预览:")
        print(f"  数据: {data_dir}")
        print(f"  slug: {full_slug}")
        print(f"  标题: {args.title}")
        print()
        print("  下一步先做认证 (选一种):")
        print("    方案 A: 把 kaggle.json 放到 ~/.kaggle/kaggle.json")
        print("             (kaggle.com/settings → API → Create New Token 下载)")
        print("    方案 B: 设环境变量")
        print('             $env:KAGGLE_USERNAME = "你的用户名"')
        print('             $env:KAGGLE_KEY      = "你的API key"')
        print()
        print("  认证完再跑:")
        print('    $PY scripts/upload_to_kaggle.py --yes')
        return 0

    check_credentials()

    full_slug = args.slug if "/" in args.slug else f"<username>/{args.slug}"
    print(f"\n[PLAN] 将上传到 Kaggle Dataset: {full_slug}")
    print(f"       标题: {args.title}")
    print(f"       源: {data_dir}")

    # 新版 kaggle CLI: 写 datasets-metadata.json（替代 --title）
    write_dataset_metadata(data_dir, full_slug, args.title)

    if not args.yes:
        ans = input("\n确认上传? (yes/no): ").strip().lower()
        if ans not in ("y", "yes"):
            print("[!] 用户取消")
            return 0

    if dataset_exists(args.slug):
        print(f"\n[STEP] Dataset 已存在, 提交新版本: {args.slug}")
        cmd = ["kaggle", "datasets", "version",
               "-p", str(data_dir), "-m", "update from local",
               "--dir-mode", "zip"]
    else:
        print(f"\n[STEP] 创建新 Dataset: {args.slug}")
        # 新版: 不用 --title, 不用 --public (默认 private, 加 -u 转 public)
        cmd = ["kaggle", "datasets", "create",
               "-p", str(data_dir), "--dir-mode", "zip", "-u"]

    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    ret = subprocess.call(cmd)
    if ret != 0:
        print(f"\n[x] 上传失败, 退出码 {ret}")
        return ret

    print("\n" + "=" * 60)
    print("  [OK] 上传完成!")
    print("=" * 60)
    print(f"  Dataset URL: https://www.kaggle.com/{full_slug}")
    print()
    print("  下一步：")
    print("    1. Kaggle → New Notebook")
    print("    2. Settings → Accelerator = GPU T4 x2")
    print("    3. Add Data → 搜 'eurosat-10class'")
    print("    4. 把 scripts/kaggle_train.py 全选粘进一个 cell")
    print("    5. 改 CONFIG 段 → Run All")
    return 0


if __name__ == "__main__":
    sys.exit(main())
