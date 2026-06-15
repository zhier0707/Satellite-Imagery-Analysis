# 切换到真实模型 — 完整 4 步
# =============================

# 假设 Edge 下载 best.pt 到: $env:USERPROFILE\Downloads\eurosat-stage2-best.zip
# 下面 4 步:

# 1) 解压 zip
$zip = "$env:USERPROFILE\Downloads\eurosat-stage2-best.zip"
$dst = "e:\truth-视觉实践\models\checkpoints\_eurosat-stage2-extracted"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Expand-Archive -Path $zip -DestinationPath $dst -Force
Get-ChildItem $dst

# 2) 移动 best.pt 到目标路径
$src = Join-Path $dst "best.pt"
$dstFinal = "e:\truth-视觉实践\models\checkpoints\best.pt"
Move-Item -Path $src -Destination $dstFinal -Force
Get-Item $dstFinal | Select-Object Name, Length

# 3) 验证 best.pt 完整性
& "F:\anaconda\python.exe" e:\truth-视觉实践\scripts\verify_model.py

# 4) 重启后端(uvicorn --reload 不会自动检测 .pt, 必须手动重启)
#    找到当前 uvicorn 进程(端口 8000), Ctrl+C 停掉,然后:
$env:PYTHONPATH = "."
$env:PY = "F:\anaconda\python.exe"
& $env:PY -m uvicorn backend.main:app --reload --port 8000

# 启动日志应包含:
#   [INFO] backend.api.classify: model loaded from models\checkpoints\best.pt
# 这是切换成功的标志
