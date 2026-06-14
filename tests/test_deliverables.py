"""检查所有 Phase 关键交付物是否齐全"""
from pathlib import Path

ROOT = Path("e:/truth-视觉实践")
KEY_FILES = [
    # Phase 1
    "backend/db/models.py",
    "backend/security/password.py",
    "backend/security/jwt.py",
    "backend/security/deps.py",
    "backend/api/auth.py",
    "backend/api/records.py",
    # Phase 2
    "src/train.py",
    "tests/test_train_checkpoint.py",
    # Phase 3
    "backend/api/change.py",
    "backend/api/reports.py",
    "backend/reports/pdf_builder.py",
    "backend/reports/excel_builder.py",
    "backend/reports/csv_builder.py",
    "backend/api/admin/__init__.py",
    # Phase 4
    "scripts/convert_to_onnx.py",
    "notebooks/tfjs_convert.ipynb",
    "tests/test_onnx_export.py",
    "tests/test_notebook_validity.py",
    # Phase 5
    "frontend/package.json",
    "frontend/src/router/index.ts",
    "frontend/src/router/guards.ts",
    "frontend/src/stores/auth.ts",
    "frontend/src/stores/upload.ts",
    "frontend/src/stores/reports.ts",
    "frontend/src/stores/admin.ts",
    "frontend/src/views/LoginView.vue",
    "frontend/src/views/NotFoundView.vue",
    "frontend/src/views/AppLayout.vue",
    "frontend/src/views/AdminLayout.vue",
    "frontend/src/views/user/UploadView.vue",
    "frontend/src/views/user/Top5View.vue",
    "frontend/src/views/user/HeatmapView.vue",
    "frontend/src/views/user/StatsView.vue",
    "frontend/src/views/user/ChangeView.vue",
    "frontend/src/views/user/ReportsView.vue",
    "frontend/src/views/admin/UserManageView.vue",
    "frontend/src/views/admin/AllRecordsView.vue",
    "frontend/src/views/admin/TrainingJobsView.vue",
    "frontend/src/views/admin/ConvertView.vue",
    "frontend/src/views/admin/ReportManageView.vue",
    # Phase 6
    "src/gradcam.py",
    "README.md",
    "scripts/quickstart.ps1",
    "scripts/quickstart.sh",
    "reports/e2e_test.py",
    "reports/FULL_STATUS.md",
]

missing = []
present = []
for rel in KEY_FILES:
    p = ROOT / rel
    if p.is_file():
        present.append(rel)
    else:
        missing.append(rel)

print(f"[OK] {len(present)}/{len(KEY_FILES)} key files present")
if missing:
    print("[MISS]")
    for m in missing:
        print(f"  - {m}")
else:
    print("[ALL GREEN]")

# 按 Phase 分组统计
phases = {
    "Phase 1 (Auth/DB)": KEY_FILES[0:6],
    "Phase 2 (Train)":   KEY_FILES[6:8],
    "Phase 3 (Reports/Change/Admin)": KEY_FILES[8:15],
    "Phase 4 (ONNX/TF.js)": KEY_FILES[15:19],
    "Phase 5 (Frontend)": KEY_FILES[19:38],
    "Phase 6 (Docs/Docs)": KEY_FILES[38:44],
}
print()
for name, files in phases.items():
    n = sum(1 for f in files if (ROOT / f).is_file())
    print(f"  {name}: {n}/{len(files)}")
