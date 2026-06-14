# ============================================================
# Satellite Image Analysis Platform - Quickstart (PowerShell 5+)
# ============================================================
# Usage:
#   $env:PY = "F:\anaconda\python.exe"
#   ./scripts/quickstart.ps1
#
# Optional flags:
#   -SkipInstall     skip pip install
#   -SkipE2E         skip E2E smoke test
#   -NoFrontend      do not start the Vite dev server
# ============================================================

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall,
    [switch]$SkipE2E,
    [switch]$NoFrontend
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# ----------------------------------------------------------
# 0. Resolve Python interpreter
# ----------------------------------------------------------
if (-not $env:PY) {
    Write-Host "[x] Please set `$env:PY first, e.g.:" -ForegroundColor Red
    Write-Host "    `$env:PY = 'F:\anaconda\python.exe'" -ForegroundColor Red
    exit 1
}
$Py = $env:PY
Write-Host "[OK] Python interpreter: $Py" -ForegroundColor Green
& $Py --version

# ----------------------------------------------------------
# 1. Install Python dependencies
# ----------------------------------------------------------
if (-not $SkipInstall) {
    Write-Host "`n[STEP 1] Installing Python dependencies..." -ForegroundColor Cyan
    & $Py -m pip install -r requirements.txt --quiet
    Write-Host "[OK] Python dependencies installed" -ForegroundColor Green
} else {
    Write-Host "[SKIP] pip install" -ForegroundColor Yellow
}

# ----------------------------------------------------------
# 2. Download EuroSAT (if not present)
# ----------------------------------------------------------
if (-not (Test-Path "data/eurosat/Forest")) {
    Write-Host "`n[STEP 2] Downloading EuroSAT..." -ForegroundColor Cyan
    & $Py scripts/download_eurosat.py
} else {
    Write-Host "[SKIP] EuroSAT already exists" -ForegroundColor Yellow
}

# ----------------------------------------------------------
# 3. Start backend
# ----------------------------------------------------------
Write-Host "`n[STEP 3] Starting backend (port $BackendPort)..." -ForegroundColor Cyan
$env:PYTHONPATH = "."
$backendCmd = "$Py -m uvicorn backend.main:app --host 127.0.0.1 --port $BackendPort --log-level info"
$backendProc = Start-Process -FilePath powershell `
    -ArgumentList "-NoProfile", "-Command", $backendCmd `
    -PassThru -WindowStyle Hidden
Write-Host "[OK] backend PID = $($backendProc.Id)" -ForegroundColor Green

# ----------------------------------------------------------
# 4. Start frontend
# ----------------------------------------------------------
if (-not $NoFrontend) {
    Write-Host "`n[STEP 4] Starting frontend (port $FrontendPort)..." -ForegroundColor Cyan
    Set-Location frontend
    if (-not (Test-Path node_modules)) {
        Write-Host "[INFO] Installing frontend dependencies..." -ForegroundColor Cyan
        npm install --silent
    }
    $frontendCmd = "npm run dev -- --port $FrontendPort"
    $frontendProc = Start-Process -FilePath powershell `
        -ArgumentList "-NoProfile", "-Command", $frontendCmd `
        -PassThru -WindowStyle Hidden
    Set-Location ..
    Write-Host "[OK] frontend PID = $($frontendProc.Id)" -ForegroundColor Green
}

# ----------------------------------------------------------
# 5. Wait 5s and run E2E
# ----------------------------------------------------------
if (-not $SkipE2E) {
    Write-Host "`n[STEP 5] Waiting 5s then running E2E smoke test..." -ForegroundColor Cyan
    Start-Sleep -Seconds 5
    & $Py reports/e2e_test.py
}

Write-Host "`n===============================================" -ForegroundColor Green
Write-Host " Startup complete!" -ForegroundColor Green
Write-Host "   backend:  http://127.0.0.1:$BackendPort" -ForegroundColor Cyan
Write-Host "   frontend: http://localhost:$FrontendPort" -ForegroundColor Cyan
Write-Host "   Swagger:  http://127.0.0.1:$BackendPort/docs" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Green
Write-Host " Stop with:  Stop-Process -Id $($backendProc.Id)" -ForegroundColor Yellow
if (-not $NoFrontend) {
    Write-Host "             Stop-Process -Id $($frontendProc.Id)" -ForegroundColor Yellow
}
