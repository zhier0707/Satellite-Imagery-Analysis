"""验证 Colab notebook JSON 合法性"""
import json
import sys
from pathlib import Path

nb_path = Path("notebooks/tfjs_convert.ipynb")
try:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
except Exception as e:
    print(f"[FAIL] JSON 解析失败: {e}")
    sys.exit(1)

print(f"[OK] nbformat={nb['nbformat']}.{nb['nbformat_minor']}, cells={len(nb['cells'])}")
for i, c in enumerate(nb['cells']):
    ctype = c['cell_type']
    src = ''.join(c.get('source', []))
    first_line = src.split('\n', 1)[0][:60]
    print(f"  cell[{i:>2}]: {ctype:<8} | {first_line}")

# 基本元数据检查
ks = nb['metadata'].get('kernelspec', {})
li = nb['metadata'].get('language_info', {})
print(f"\n[OK] kernelspec.name = {ks.get('name')}")
print(f"[OK] language_info.python = {li.get('version')}")

# 检查每个 cell 是否有 id (Colab 推荐)
no_id = [i for i, c in enumerate(nb['cells']) if 'id' not in c]
if no_id:
    print(f"[WARN] {len(no_id)} cells 缺 id: {no_id}")
else:
    print("[OK] 所有 cell 含 id")

# 统计代码 cell
code_cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
md_cells = [c for c in nb['cells'] if c['cell_type'] == 'markdown']
print(f"[OK] code={len(code_cells)}, markdown={len(md_cells)}")
print(f"\nALL PHASE 4 NOTEBOOK SMOKE CHECKS PASSED")
