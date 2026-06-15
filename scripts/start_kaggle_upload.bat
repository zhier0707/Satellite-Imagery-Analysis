@echo off
REM ============================================================
REM  Kaggle EuroSAT uploader (run from a NORMAL PowerShell,
REM  not Trae IDE's terminal — Trae kills long-running detached
REM  Python processes that emit tqdm-style progress bars).
REM ============================================================

REM 配置 =====================================================
set PY=F:\anaconda\python.exe
set DATASET_ROOT=e:\truth-视觉实践\data\eurosat
set LOG=%USERPROFILE%\kaggle_upload.log
set META=%DATASET_ROOT%\dataset-metadata.json
set SCRIPT=%~dp0_upload_now.py
REM ============================================================

REM 确认 .kaggle\access_token 已就位
if not exist "%USERPROFILE%\.kaggle\access_token" (
    echo [ERR] %USERPROFILE%\.kaggle\access_token not found
    echo       1. kaggle.com ^> Settings ^> API ^> Create New Token
    echo       2. save token to that path
    pause
    exit /b 1
)

echo ============================================================
echo  Kaggle EuroSAT upload
echo    data  : %DATASET_ROOT%
echo    meta  : %META%
echo    log   : %LOG%
echo ============================================================

REM 写最小 dataset-metadata.json(无 BOM,UTF-8)
echo {"title": "EuroSAT 10-class Sentinel-2 RGB", "id": "zhier1/eurosat-10class", "licenses": [{"name": "CC0-1.0"}]} > "%META%"

REM 清空旧 log
del /f /q "%LOG%" 2>nul

REM 跑上传(写 log)
"%PY%" -u "%SCRIPT%" 2>&1 | tee "%LOG%"

echo.
echo ============================================================
echo  DONE
echo ============================================================
pause
