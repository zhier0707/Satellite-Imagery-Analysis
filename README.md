# 卫星图像分析项目

> 基于 EfficientNetV2-M 的卫星遥感图像分类与土地利用监测 Web 平台  
> 当前迭代：完整 **6-Phase** 全栈（用户系统 / 训练 / 转换 / 前端路由化 / 联调 / 文档）

## 目录约定

```
truth-视觉实践/
├── data/                       # 数据集
│   └── eurosat/                # EuroSAT 解压后目录（10 个类别子目录）
├── models/                     # 模型权重
│   ├── checkpoints/            # PyTorch 训练检查点
│   └── web_model/              # TF.js 转换产物
├── scripts/                    # 工具脚本
│   ├── download_eurosat.py     # EuroSAT 下载与解压
│   ├── convert_to_onnx.py      # PyTorch → ONNX
│   └── convert_to_tfjs.py      # ONNX → TF.js（本地链路，需 onnx2tf/TF）
├── src/                        # 核心代码（Python）
│   ├── data/dataset.py         # EuroSAT 数据加载器
│   ├── train.py                # 训练入口（支持恢复 / 早停 / TensorBoard）
│   └── gradcam.py              # Grad-CAM 热力图
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 入口
│   ├── api/                    # auth/classify/change/reports/stats/admin
│   ├── db/                     # SQLAlchemy 6 张表
│   ├── reports/                # PDF/Excel/CSV 生成器
│   └── security/               # JWT + bcrypt
├── frontend/                   # Vue 3 + Vite + Element Plus + Pinia + Router
│   └── src/
│       ├── api/                # 后端 API 封装（拦截器 + 自动 refresh）
│       ├── stores/             # 4 个 pinia store
│       ├── router/             # vue-router + guards
│       └── views/              # Login / AppLayout / AdminLayout + 11 视图
├── notebooks/                  # Jupyter 探索
│   └── tfjs_convert.ipynb      # ONNX → TF.js Colab 笔记本
├── reports/                    # 评估 / 状态 / 烟测日志
│   ├── SCAFFOLD_STATUS.md      # 骨架完成度
│   ├── FULL_STATUS.md          # 全 6-Phase 完成度
│   └── e2e_test.py             # 后端 6 个接口一键验证
├── scripts/quickstart.ps1      # PowerShell 一键启动
├── scripts/quickstart.sh       # Git Bash 一键启动
└── 卫星图像分析项目方案.md       # 原始方案文档
```

---

## 快速开始

> ⚠️ **不要使用 `hermes-agent` 自带的虚拟环境**——它没有 pip，无法安装依赖。请使用本机已有的 Anaconda。

### 0. 设置 Python 解释器变量

本项目要求 **Python 3.10+**，且需 `torch` / `timm` / `opencv-python` 等。下面所有命令用变量统一引用解释器。

**Windows PowerShell 5.x**（一次会话，注意 PS5 不支持 `&&`，所有命令中用 `&` 调外部程序、用 `;` 分隔）：

```powershell
# 一次性设置
$env:PY = "F:\anaconda\python.exe"
$env:PYTHONPATH = "."

# 验证（注意要用 & 调用）
& $env:PY --version
```

**Windows PowerShell 7+ / pwsh**（可选，支持 `&&`）：

```powershell
$env:PY = "F:\anaconda\python.exe"
& $env:PY --version
```

**Git Bash / macOS / Linux**（写入 `~/.bashrc` 或 `~/.zshrc`）：

```bash
export PY="F:/anaconda/python.exe"   # Windows
# 或
export PY="python3"                   # *nix
export PYTHONPATH="."

# 验证
$PY --version
```

### 1. 一键启动（最省事）

```powershell
# PowerShell：先设置 $env:PY
./scripts/quickstart.ps1
# 可选参数：-SkipInstall / -SkipE2E / -NoFrontend
```

```bash
# Git Bash
./scripts/quickstart.sh
# 可选参数：--skip-install / --skip-e2e / --no-frontend
```

脚本会自动完成：装依赖 → 下载 EuroSAT（如缺）→ 启动后端（新进程）→ 启动前端（新进程）→ 等待 5 秒后跑 E2E 烟测。

### 2. 手动逐步启动

#### 2.1 装 Python 依赖

**PowerShell**：
```powershell
& $env:PY -m pip install -r requirements.txt
```

**Bash**：
```bash
$PY -m pip install -r requirements.txt
```

#### 2.2 下载 EuroSAT 数据集

```powershell
& $env:PY scripts/download_eurosat.py
```
```bash
$PY scripts/download_eurosat.py
```

下载完成后 `data/eurosat/` 出现 10 个类别目录，每个约 2500-3000 张 64×64 JPG。

#### 2.3 训练（可选，本轮不实际跑）

```bash
# 干跑：验证代码链路（不下载预训练权重）
$PY src/train.py --dry-run --no-pretrained --data-root data/eurosat

# 真实训练 stage1（仅解冻分类头）
$PY src/train.py --data-root data/eurosat --stage 1 --epochs 50
```

#### 2.4 启动后端

**PowerShell**（用 `;` 代替 `&&`）：
```powershell
$env:PYTHONPATH = "."
& $env:PY -m uvicorn backend.main:app --reload --port 8000
```
**Bash**：
```bash
PYTHONPATH=. $PY -m uvicorn backend.main:app --reload --port 8000
```

Swagger UI: `http://127.0.0.1:8000/docs`

#### 2.5 启动前端

**PowerShell**（必须用 `;` 不用 `&&`，且 `cd` 写在一行）：
```powershell
cd frontend; npm install; npm run dev
```
**Bash**：
```bash
cd frontend
npm install      # 仅首次
npm run dev      # 默认 http://localhost:5173
```

#### 2.6 跑 E2E 烟测

```powershell
& $env:PY reports/e2e_test.py
```
```bash
$PY reports/e2e_test.py
```

---

## 用户系统 & 路由化架构（Phase 1 + Phase 5）

### 角色
- **user** (默认)：注册即可使用。访问 `/app/*` 路径，6 个功能页。
- **admin** (首个注册者自动获得)：额外访问 `/admin/*` 路径，5 个管理页。

### 用户端 6 菜单项（`/app`）

| 路径 | 名称 | 后端接口 |
|------|------|---------|
| `/app/upload` | 图像上传 | `POST /api/classify` |
| `/app/top5` | Top-5 概率条 | 共享 upload store |
| `/app/heatmap` | Grad-CAM 热力图 | `POST /api/heatmap` |
| `/app/stats` | 分类统计 | `GET /api/stats` |
| `/app/change` | 时相变化检测 | `POST /api/change` |
| `/app/reports` | 我的报表 | `POST /api/reports/export`, `GET /api/reports/...` |

### 管理端 5 菜单项（`/admin`）

| 路径 | 名称 | 后端接口 |
|------|------|---------|
| `/admin/users` | 用户管理 | `GET/PATCH/DELETE /api/admin/users[/:id]` |
| `/admin/records` | 全量记录 | `GET /api/admin/records` |
| `/admin/training` | 训练任务 | `GET/POST /api/admin/training[/:id]/start\|stop` |
| `/admin/convert` | ONNX 转换 | `POST /api/admin/converts/start` |
| `/admin/reports` | 全部报表 | `GET /api/admin/reports` |

### 路由守卫
- 未登录访问受保护路由 → 跳 `/login?redirect=...`
- `user` 访问 `/admin/*` → 跳 `/app` + toast
- 已登录访问 `/login` → 跳 `/app`（admin 跳 `/admin`）
- 401 → 拦截器自动用 `refresh_token` 续签一次，失败再清登录态

---

## 模型转换链路（Phase 4）

```
PyTorch .pt
    │
    ▼ scripts/convert_to_onnx.py --weights <pt> --output <onnx>
ONNX
    │
    ▼ notebooks/tfjs_convert.ipynb (在 Colab 跑)
TF.js graph model
    │
    ▼ 放到 frontend/public/web_model_tfjs/
tf.loadGraphModel('/web_model_tfjs/model.json')
```

### ONNX 真实导出（本地）
```bash
$PY scripts/convert_to_onnx.py --weights models/checkpoints/best.pt \
    --output models/web_model/best.onnx --image-size 384 --opset 13
```

> **PowerShell 写法**：把 `$PY` 换成 `& $env:PY`，反斜杠 `\` 续行 PS5 也支持（直接 `<Enter>` 也能断行）。

### TF.js 转换（Colab）
1. 把 `best.onnx` 推到 GitHub Release 或公开 URL
2. 在 Colab 打开 `notebooks/tfjs_convert.ipynb`
3. 把 Cell 3 的 `<user>/<repo>` 换成你的真实 GitHub
4. 依次执行 6 个 cell，最后自动下载 `web_model_tfjs.zip`

---

## 命令清单

> **PowerShell** 中把 `$PY` 换成 `& $env:PY`，把 `&&` 换成 `;`。  
> 下面命令用 `$PY` 形式展示（bash 友好），PS 写法照上述转换。

| 用途 | 命令 |
|------|------|
| 下载数据 | `$PY scripts/download_eurosat.py` |
| 干跑训练（离线） | `$PY src/train.py --dry-run --no-pretrained --data-root data/eurosat` |
| 真实训练 stage1 | `$PY src/train.py --data-root data/eurosat --stage 1 --epochs 50` |
| 恢复训练 | `$PY src/train.py --data-root data/eurosat --resume-from models/checkpoints/last.pt` |
| Grad-CAM 单图 | `$PY src/gradcam.py --image data/eurosat/Forest/Forest_1.jpg --output reports/gradcam_forest.png` |
| ONNX 导出 | `$PY scripts/convert_to_onnx.py --weights models/checkpoints/best.pt` |
| 启动后端 | `$PY -m uvicorn backend.main:app --reload --port 8000` |
| 启动前端 dev | `cd frontend; npm run dev` |
| 构建前端 prod | `cd frontend; npm run build` |
| 后端 E2E 验证 | `$PY reports/e2e_test.py` |
| ONNX 导出测试 | `$PY tests/test_onnx_export.py` |
| 训练烟测 | `$PY tests/test_train_checkpoint.py` |
| 报表生成器测试 | `$PY tests/test_report_builders.py` |

---

## 在 Kaggle 训练（免费 GPU）

```powershell
# 1. 本地上传数据集到 Kaggle Datasets（一次性，87 MB）
$env:PY = "F:\anaconda\python.exe"
& $env:PY scripts/upload_to_kaggle.py --dry-run     # 先看预览
# 认证: 把 kaggle.json 放到 ~/.kaggle/kaggle.json（kaggle.com/settings → API 下载）
& $env:PY scripts/upload_to_kaggle.py --yes
```

```python
# 2. Kaggle Notebook → New Notebook
#    Settings → Accelerator = GPU T4 x2
#    Add Data → 搜 "eurosat-10class"
#    把整个 scripts/kaggle_train.py 粘进一个 cell
#    改顶部 CONFIG 段 → Run All
```

训练完成后从 `/kaggle/working/{tag}_checkpoints.zip` 下载，回到本地：
```
e:/truth-视觉实践/models/checkpoints/best.pt
```

---

## 类别映射（EuroSAT 10 类）

| Index | Label | 中文 |
|------:|-------|------|
| 0 | AnnualCrop | 一年生作物 |
| 1 | Forest | 森林 |
| 2 | HerbaceousVegetation | 草本植被 |
| 3 | Highway | 高速公路 |
| 4 | Industrial | 工业区 |
| 5 | Pasture | 牧场 |
| 6 | PermanentCrop | 多年生作物 |
| 7 | Residential | 住宅区 |
| 8 | River | 河流 |
| 9 | SeaLake | 海/湖 |

---

## 高德地图 Skill 集成

本项目按方案文档 5.2 节集成 3 个高德 Skill：**amap-jsapi-skill**（前端地图 SDK） / **amap-lbs-skill**（后端 LBS） / **personal-map**（个人地图小程序）。

### Key 配置速查

| Key | 用途 | 服务平台 | 配置位置 |
|-----|------|---------|---------|
| **Web 端 (JS API) Key** | 前端加载高德地图 SDK | 高德控制台 → 「Web 端」 | `frontend/.env` → `VITE_AMAP_JS_KEY` |
| **Web 端 安全密钥** | JSAPI v2.0 强制鉴权 | 控制台 → Key 详情 → 「安全密钥」 | `frontend/.env` → `VITE_AMAP_SECURITY_CODE` |
| **Web 服务 Key** | 后端 LBS API（POI/地理编码/路径规划/...） | 高德控制台 → 「Web 服务」 | `backend/.env` → `AMAP_WEBSERVICE_KEY` |

### 申请步骤
1. 注册 [高德开放平台](https://lbs.amap.com) → 进入「应用管理」
2. 创建 2 个 Key（Web 端 + Web 服务），域名白名单填 `localhost:5173`，IP 白名单填 `127.0.0.1`
3. 在 Web 端 Key 详情页点「安全密钥」→「生成」获得 `securityJsCode`
4. 把 3 个值分别填入 `frontend/.env` 与 `backend/.env`（真实 Key），模板见 `.env.example`

> ⚠️ **安全提示**: 生产环境务必通过后端代理转发 `serviceHost`，避免 `securityJsCode` 暴露（详见 `~/.agents/skills/amap-jsapi-skill/SKILL.md` 的 `references/security.md`）。

---

## 完成度

详见 `reports/FULL_STATUS.md`（6-Phase 全景）与 `reports/SCAFFOLD_STATUS.md`（骨架版本）。

## 参考

- 方案文档：`卫星图像分析项目方案.md`
- EuroSAT 官方：<https://github.com/phelber/eurosat>
- timm 模型库：<https://github.com/huggingface/pytorch-image-models>
- EfficientNetV2 论文：<https://arxiv.org/abs/2104.00298>
