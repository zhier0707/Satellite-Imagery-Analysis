# 高德地图 Skill 接入指南

> 本文档面向「想在本地真实跑通地图视图」的开发者。  
> 跟着 4 步走完，前后端即可对接高德 JS API / LBS / 个人专属地图 3 个 Skill。  
> 如果只是想看地图效果，**不配 Key 也能用**——后端会自动 fallback 到 `backend/data/lbs_mock/` 下的本地 fixture（`X-LBS-Source: mock` 标识），但**前端地图 SDK 必须有 Key 才能加载**。

## 目录

1. [申请 Key](#1-申请-key)
2. [配置 .env](#2-配置-env)
3. [验证](#3-验证)
4. [排错](#4-排错)

---

## 1. 申请 Key

入口：<https://lbs.amap.com>（高德开放平台）

### 1.1 注册并登录

1. 打开 <https://lbs.amap.com>，点击右上角「注册」完成开发者账号注册（支持手机号 / 支付宝）。
2. 完成实名认证（个人开发者即可，**个人配额 = 30 万次/日**，对本项目绰绰有余）。

### 1.2 创建应用

1. 登录后进入「**控制台**」。
2. 左侧菜单「**应用管理**」→「**我的应用**」→ 右上角「**创建新应用**」。
3. 填写：
   - 应用名称：自填（如 `truth-视觉实践-本地开发`）
   - 应用类型：选「**其他**」
4. 创建成功后进入应用详情，可以看到「**添加 Key**」按钮。

### 1.3 申请 3 个 Key（关键步骤！）

在「**添加 Key**」弹窗中，分别按下面的配置创建 **3 个 Key**（每个 Key 必须勾选正确的「服务平台」）：

| 序号 | Key 名称 | 服务平台（必选） | 用途 |
|------|----------|------------------|------|
| ① | `truth-前端-JSAPI` | **Web 端 (JS API)** | 前端浏览器加载高德地图 SDK |
| ② | `truth-前端-Web服务` | **Web 服务** | 前端展示用 mock 数据来源标识（真实调用走后端） |
| ③ | `truth-后端-Web服务` | **Web 服务** | 后端 LBS API（POI / 地理编码 / 路径规划 …） |

> **常见错误**：选错服务平台会导致 `INVALID_USER_KEY`。例如把 Key ① 选成了「Web 服务」就完全没法用。

#### 1.3.1 白名单设置（建议）

创建 Key 时在「**白名单**」区域填写：

- **Key ①（前端 JSAPI）**：
  - 域名白名单：`localhost:5173`（开发） + 你的生产域名
  - IP 白名单：可不填（开发期放宽）
- **Key ③（后端 Web 服务）**：
  - IP 白名单：`127.0.0.1`（本地）+ 你的服务器公网 IP（生产）

> 不填白名单在开发期也能跑通；上生产前一定要加白名单，防止 Key 被盗用刷配额。

### 1.4 生成安全密钥 `securityJsCode`

> 这是 **JSAPI v2.0 的强制鉴权机制**。漏了这一步，控制台会报 `_AMapSecurityConfig 缺失`。

1. 进入「**应用管理** → 你的应用 → **Key ①（Web 端 JSAPI）的详情页**」。
2. 找到「**安全密钥**」标签 → 点「**生成**」。
3. 复制 `securityJsCode`（一串 32 位左右的字符）保存到本地。

> ⚠️ 安全提示：生产环境务必通过后端代理转发 `serviceHost`，避免 `securityJsCode` 暴露到前端 bundle。本项目前端 `.env` 中保留 `VITE_AMAP_SECURITY_CODE` 仅作开发期使用。

---

## 2. 配置 .env

把仓库里的 `.env.example` 复制成 `.env`，然后填入上面的 3 个 Key。

### 2.1 前端 `frontend/.env`

```bash
# 复制模板
cp frontend/.env.example frontend/.env   # Git Bash
# 或 PowerShell: Copy-Item frontend/.env.example frontend/.env
```

模板（与仓库内 `frontend/.env.example` 一致）：

```dotenv
# Web 端 (JS API) Key - 前端浏览器加载高德地图 SDK 鉴权用
# 服务平台必须选 "Web 端 (JS API)"
# 域名白名单建议: localhost:5173 (开发) + 你的生产域名
VITE_AMAP_JS_KEY=请填入你的_Web端_JS_API_Key

# 高德安全密钥 (securityJsCode) - JSAPI v2.0 强制要求
# 申请路径: 控制台 -> 你的 Key 详情 -> "安全密钥" -> 生成
# 安全建议: 生产环境通过后端代理 serviceHost 转发,不要明文暴露在前端
VITE_AMAP_SECURITY_CODE=请填入对应的安全密钥

# 是否启用地图模块
VITE_ENABLE_MAP=true
```

填好后的真实值示例（**占位符请替换**）：

```dotenv
VITE_AMAP_JS_KEY=0123456789abcdef0123456789abcdef
VITE_AMAP_SECURITY_CODE=0123456789abcdef0123456789abcdef01234567
VITE_ENABLE_MAP=true
```

### 2.2 后端 `backend/.env`

```bash
cp backend/.env.example backend/.env
```

模板（与仓库内 `backend/.env.example` 一致）：

```dotenv
# 高德 Web 服务 Key - 后端 LBS API (POI/地理编码/路径规划/天气/...) 鉴权用
# 服务平台必须选 "Web 服务",IP 白名单建议填本机 + 生产服务器公网 IP
# amap-lbs-skill 读取此变量(也可写成 AMAP_API_KEY,personal-map skill 兼容)
AMAP_WEBSERVICE_KEY=请填入你的_Web服务_Key
AMAP_API_KEY=同上
```

填好后的真实值示例（**占位符请替换**）：

```dotenv
AMAP_WEBSERVICE_KEY=fedcba9876543210fedcba9876543210
AMAP_API_KEY=fedcba9876543210fedcba9876543210
```

> `AMAP_API_KEY` 是兼容 `personal-map` skill 的别名，值与 `AMAP_WEBSERVICE_KEY` 保持一致即可。

### 2.3 配置总览

| 变量名 | 写在哪个 `.env` | 来源 Key | 是否必填 |
|--------|-----------------|----------|----------|
| `VITE_AMAP_JS_KEY` | `frontend/.env` | ① Web 端 (JS API) | **必填**（否则地图白屏） |
| `VITE_AMAP_SECURITY_CODE` | `frontend/.env` | ① 的安全密钥 | **必填**（JSAPI v2.0 强制） |
| `VITE_AMAP_WEBSERVICE_KEY` | `frontend/.env` | ② Web 服务 | 可选（仅展示标识） |
| `AMAP_WEBSERVICE_KEY` | `backend/.env` | ③ Web 服务 | 可选（不填走 mock） |
| `AMAP_API_KEY` | `backend/.env` | ③ Web 服务 | 可选（同上，personal-map 兼容） |

---

## 3. 验证

### 3.1 启动服务

**PowerShell**：

```powershell
$env:PY = "F:\anaconda\python.exe"
$env:PYTHONPATH = "."

# 启动后端（新终端）
& $env:PY -m uvicorn backend.main:app --reload --port 8000

# 启动前端（另一终端）
cd frontend; npm run dev
```

**Git Bash / macOS / Linux**：

```bash
export PY="F:/anaconda/python.exe"   # Windows; 或 python3
export PYTHONPATH="."

# 启动后端
$PY -m uvicorn backend.main:app --reload --port 8000

# 启动前端（另一终端）
cd frontend && npm run dev
```

### 3.2 命令行验证后端 LBS

> `/api/lbs/*` 需要带 JWT。下面的 `TOKEN` 用登录接口或 admin 初始化接口获取（详见 `README.md`「用户系统」段）。

**未配置 Key**（应返回 mock 数据）：

```bash
curl -i -H "Authorization: Bearer <TOKEN>" \
     "http://127.0.0.1:8000/api/lbs/geocode?address=故宫"
```

期望响应头：

```
HTTP/1.1 200 OK
X-LBS-Source: mock
content-type: application/json
```

**配置 Key 后**（应调用真实高德 API）：

期望响应头：

```
HTTP/1.1 200 OK
X-LBS-Source: live
content-type: application/json
```

也可以用 `curl -I` 快速看头：

```bash
curl -sI -H "Authorization: Bearer <TOKEN>" \
     "http://127.0.0.1:8000/api/lbs/geocode?address=故宫" | grep -i x-lbs-source
```

### 3.3 浏览器验证地图视图

1. 打开 <http://localhost:5173/login>，登录账号（普通用户或 admin 均可）。
2. 左侧菜单「**地图视图**」→ 进入 `/app/map`。
3. 看到卫星底图 + 左 320px 工具栏（地理编码 / POI 搜索 / 图层切换 / 周边搜索）即说明前端 JSAPI 加载成功。
4. 抽屉里试一下「**POI 搜索**」输入「北京故宫」回车，结果列表点击后会 `flyTo` 到对应位置。
5. 工具栏切到「**图层切换**」勾选「分类热力图」，应能看到最近 50 条分类记录渲染为热力点。

### 3.4 一键烟测脚本

仓库自带 E2E 烟测（8 段含「地图视图」）：

```bash
$PY reports/e2e_test.py
```

期望最终输出：

```
ALL E2E TESTS PASSED
```

---

## 4. 排错

### 4.1 常见错误速查表

| 症状 / 错误码 | 根因 | 解决方案 |
|---------------|------|---------|
| `INVALID_USER_KEY` | Key 失效 / 服务平台选错 / 白名单拒绝 | 检查高德控制台 Key 详情：① 状态是否「启用」；② 服务平台是否对应（前端 = `Web 端 (JS API)`，后端 = `Web 服务`）；③ 域名/IP 白名单是否包含 `localhost:5173` 或 `127.0.0.1` |
| `CUQPS_HAS_EXCEEDED_THE_LIMIT` | 个人配额超限（30 万/日） | 高德控制台 → 应用 → 流量统计 查看当日调用量；临时可改走 mock 模式（清空 `AMAP_WEBSERVICE_KEY`） |
| `_AMapSecurityConfig 缺失` | `VITE_AMAP_SECURITY_CODE` 未设 | 在 `frontend/.env` 填入 `securityJsCode`，**重启前端 dev server** 让 Vite 重新加载环境变量 |
| 地图白屏 / 容器高度为 0 | CSS 高度未撑开 | 检查 `frontend/src/components/map/AMapContainer.vue` 的 `min-height: 480px` 是否被父容器覆盖 |
| `401 Unauthorized` | 没带 JWT | 浏览器先登录，再访问 `/app/map`；命令行加 `Authorization: Bearer <TOKEN>` |
| CORS 跨域报错 | 后端 CORS 未允许前端源 | 检查 `backend/.env` 的 `CORS_ALLOW_ORIGINS`，至少包含 `http://localhost:5173` |
| 浏览器控制台 `net::ERR_BLOCKED_BY_CLIENT` | 浏览器扩展（AdBlock / Privacy Badger）拦截了高德静态资源 | 临时禁用扩展，或把 `*.amap.com` 加入白名单 |
| 工具栏勾选「分类热力图」后无任何点 | 当前用户 `classify_records` 为空 | 先去「图像上传」分类几张图，再回到地图视图 |
| `/api/lbs/share` 普通用户返回 403 | 该端点仅 admin 可调 | 用 admin 账号登录或调用 |
| `X-LBS-Source` 一直是 `mock` | 后端 Key 未生效 | ① 确认 `backend/.env` 中 `AMAP_WEBSERVICE_KEY` 已填；② **重启 uvicorn** 让环境变量重新加载；③ 确认 Key 的「服务平台」是「Web 服务」 |

### 4.2 配额监控

- 入口：高德控制台 → 我的应用 → 选中应用 → 「**流量统计**」
- 个人开发者上限：30 万次/日 ≈ 3.5 次/秒 持续；本项目正常使用 < 1k 次/日
- 超限后：等次日 0 点自动重置；或申请企业认证扩容

### 4.3 安全最佳实践

- **前端 Key 限制域名白名单**（生产必须）：避免被其他网站盗用
- **`securityJsCode` 通过后端代理**：参考 `~/.agents/skills/amap-jsapi-skill/references/security.md`
- **后端 Key 限制 IP 白名单**：仅允许你的服务器公网 IP
- **不要把 `.env` 提交到 git**：仓库根目录的 `.gitignore` 已默认排除

### 4.4 进一步排查

如果以上速查表未覆盖你的问题：

1. 看后端启动日志：`backend/services/amap_client.py` 会打印真实请求 URL
2. 看浏览器 Network 面板：F12 → Network → 过滤 `amap.com` 域名的请求 → 看返回 body
3. 看后端 LBS 日志：`backend/api/lbs.py` 的异常处理会打印 `AMapError(status, code, message)`
4. 临时切到 mock 模式验证业务链路：把 `AMAP_WEBSERVICE_KEY` 改成空串重启后端

---

## 附录 A：相关文件位置

| 文件 | 作用 |
|------|------|
| `frontend/src/utils/amap/loader.ts` | AMap SDK 异步 loader |
| `frontend/src/utils/amap/geocode.ts` | 正/逆地理编码前端封装 |
| `frontend/src/utils/amap/poi.ts` | POI 关键字 / 周边搜索前端封装 |
| `frontend/src/utils/amap/coord.ts` | WGS84 ↔ GCJ02 转换（近似） |
| `frontend/src/utils/amap/types.d.ts` | AMap 命名空间类型声明 |
| `frontend/src/components/map/AMapContainer.vue` | 地图容器 |
| `frontend/src/views/user/MapView.vue` | `/app/map` 主视图 |
| `backend/api/lbs.py` | `/api/lbs/*` 路由 |
| `backend/services/amap_client.py` | 高德 Web 服务异步客户端 |
| `backend/data/lbs_mock/*.json` | 未配 Key 时的本地 fixture（6 个文件） |

## 附录 B：参考链接

- 高德开放平台：<https://lbs.amap.com>
- JSAPI v2.0 安全密钥说明：<https://lbs.amap.com/api/jsapi-v2/guide/abc/prepare>
- Web 服务 API 文档：<https://lbs.amap.com/api/webservice/guide/api/georegeo>
- 个人专属地图 Skill：`~/.agents/skills/personal-map/SKILL.md`
- LBS Skill：`~/.agents/skills/amap-lbs-skill/SKILL.md`
- JSAPI Skill：`~/.agents/skills/amap-jsapi-skill/SKILL.md`
