#!/usr/bin/env bash
# ==================== 卫星图像分析平台 - 一键启动 (Git Bash / Linux) ====================
# 用法:
#   export PY="python3"   # 或 F:/anaconda/python.exe
#   ./scripts/quickstart.sh

set -e

# 解析参数
PY="${PY:-python3}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SKIP_INSTALL=""
SKIP_E2E=""
NO_FRONTEND=""
for arg in "$@"; do
  case $arg in
    --skip-install) SKIP_INSTALL=1 ;;
    --skip-e2e) SKIP_E2E=1 ;;
    --no-frontend) NO_FRONTEND=1 ;;
    *) echo "[x] unknown arg: $arg"; exit 1 ;;
  esac
done

# 切到项目根目录
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="."

# ==================== 0. 检查解释器 ====================
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[x] ${PY} not found. Set \$PY first: export PY=python3"
  exit 1
fi
echo "[OK] Python 解释器: $PY"
$PY --version

# ==================== 1. 装依赖 ====================
if [ -z "$SKIP_INSTALL" ]; then
  echo "[STEP 1] 装 Python 依赖..."
  $PY -m pip install -r requirements.txt --quiet
  echo "[OK] Python 依赖已装"
fi

# ==================== 2. 下载 EuroSAT ====================
if [ ! -d "data/eurosat/Forest" ]; then
  echo "[STEP 2] 下载 EuroSAT..."
  $PY scripts/download_eurosat.py
else
  echo "[SKIP] EuroSAT 已存在"
fi

# ==================== 3. 启动后端 ====================
echo "[STEP 3] 启动后端 (port $BACKEND_PORT)..."
$PY -m uvicorn backend.main:app --host 127.0.0.1 --port $BACKEND_PORT --log-level info &
BACKEND_PID=$!
echo "[OK] 后端 PID = $BACKEND_PID"
echo $BACKEND_PID > /tmp/backend.pid

# ==================== 4. 启动前端 ====================
if [ -z "$NO_FRONTEND" ]; then
  echo "[STEP 4] 启动前端 (port $FRONTEND_PORT)..."
  cd frontend
  [ -d node_modules ] || npm install --silent
  npm run dev -- --port $FRONTEND_PORT &
  FRONTEND_PID=$!
  cd ..
  echo "[OK] 前端 PID = $FRONTEND_PID"
  echo $FRONTEND_PID > /tmp/frontend.pid
fi

# ==================== 5. 5 秒后跑 E2E ====================
if [ -z "$SKIP_E2E" ]; then
  echo "[STEP 5] 等待 5 秒后跑 E2E 烟测..."
  sleep 5
  $PY reports/e2e_test.py || echo "[!] E2E 失败（可能后端未就绪）"
fi

cat <<EOF

===============================================
 启动完成！
   后端:   http://127.0.0.1:$BACKEND_PORT
   前端:   http://localhost:$FRONTEND_PORT
   Swagger: http://127.0.0.1:$BACKEND_PORT/docs
===============================================
 停止:  kill $BACKEND_PID $FRONTEND_PID
        或:  cat /tmp/backend.pid | xargs kill
EOF
