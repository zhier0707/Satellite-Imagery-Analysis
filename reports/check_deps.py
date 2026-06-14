"""检查项目所需的所有 Python 依赖。"""
import importlib
import sys

modules = [
    "torch", "torchvision", "timm", "fastapi", "uvicorn",
    "python_multipart", "PIL", "cv2", "numpy",
    "src.data.dataset", "src.gradcam", "src.train",
    "backend.main", "backend.api.classify", "backend.api.stats",
]

ok, fail = [], []
for m in modules:
    try:
        importlib.import_module(m)
        ok.append(m)
    except Exception as e:
        fail.append((m, str(e)))

print("=" * 60)
print(f"OK  ({len(ok)}): {ok}")
print("-" * 60)
print(f"FAIL ({len(fail)}):")
for m, e in fail:
    print(f"  - {m}: {e}")
print("=" * 60)
sys.exit(0 if not fail else 1)
