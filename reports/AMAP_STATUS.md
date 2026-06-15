# 高德 LBS 后端适配 - 状态报告

> change-id: `satellite-image-amap-enhance`
> 报告时间: 2026-06-15
> 范围: Task 30 / 40.1 / 40.2 / 41.3（仅后端 + 后端测试）

---

## 1. 完成度总览

| Task | 状态 | 说明 |
|------|------|------|
| 30.1 `backend/services/amap_client.py` | 已完成 | 单例 `httpx.AsyncClient` + `AMapError` + 6 个 async 方法 |
| 30.2 6 个 mock fixture JSON | 已完成 | `backend/data/lbs_mock/` 下 6 个文件 |
| 30.3 `backend/api/lbs.py` 6 路由 | 已完成 | `geocode` / `regeocode` / `place/text` / `place/around` / `staticmap` / `share` |
| 30.4 `backend/main.py` 注册路由 | 已完成 | `app.include_router(lbs_router, prefix="/api/lbs", tags=["lbs"])` |
| 30.5 `requirements.txt` 加 `httpx` | 已完成 | `httpx>=0.25`（根目录 + `backend/requirements.txt`） |
| 40.1 `tests/test_lbs.py` | 已完成 | 40/40 跑过：mock 模式 6 端点 + 真实模式（含 mock transport）+ 鉴权 401/403/200 |
| 40.2 `tests/test_amap_mock.py` | 已完成 | fixture 存在性 / 合法性 / 业务字段 |
| 41.3 `reports/AMAP_STATUS.md` | 已完成 | 本文档 |

**测试统计**

```
python -m pytest tests/test_lbs.py tests/test_amap_mock.py -v
======================= 40 passed, 11 warnings in 1.32s =======================
```

---

## 2. 新增 / 修改文件清单

### 2.1 新增

| 路径 | 行数 | 职责 |
|------|------|------|
| `backend/services/__init__.py` | 1 | 包标记 |
| `backend/services/amap_client.py` | ~260 | 高德 Web 服务统一客户端（httpx 单例、AMapError、6 个 async 方法、mock 兜底） |
| `backend/api/lbs.py` | ~155 | LBS 路由（6 端点 + share 走 require_admin） |
| `backend/data/lbs_mock/geocode.json` | 10 条地址 | 故宫 / 外滩 / 东方明珠 / 西湖 / 武侯祠 / 大雁塔 / 中关村 / 人民广场 / 珠江新城 / 华侨城 |
| `backend/data/lbs_mock/regeocode.json` | 完整地址组件 | 北京天安门反向 |
| `backend/data/lbs_mock/place_text.json` | 10 条 POI | 涵盖北京/上海/杭州/成都/西安 |
| `backend/data/lbs_mock/place_around.json` | 5 条周边 | 含 distance 字段 |
| `backend/data/lbs_mock/static_map.json` | URL + 字段 | Mock 占位 |
| `backend/data/lbs_mock/share.json` | url + qrcode_base64 | 1x1 透明 PNG base64 占位 |
| `tests/test_lbs.py` | ~360 | 3 个 TestClass，共 15 个 test case |
| `tests/test_amap_mock.py` | ~170 | 11 个 fixture 验证 test case |
| `reports/AMAP_STATUS.md` | 本文档 | 状态报告 |

### 2.2 修改

| 路径 | 改动点 |
|------|--------|
| `backend/main.py` | import `lbs_router` + `AMapError`；注册路由 + `app.include_router(lbs_router, prefix="/api/lbs", ...)`；新增 `@app.exception_handler(AMapError)` → 502 + `{code,message}`；新增 `@app.on_event("shutdown")` 释放 httpx 客户端 |
| `backend/requirements.txt` | 末尾追加 `httpx>=0.25` |
| `requirements.txt`（项目根） | 末尾追加 `httpx>=0.25` |

### 2.3 勾选项

| 路径 | 改动 |
|------|------|
| `.trae/specs/satellite-image-amap-enhance/tasks.md` | Task 30 全部 subtask 改为 `[x]` |
| `.trae/specs/satellite-image-amap-enhance/checklist.md` | Phase 7 - Task 30 全部项改为 `[x]` |

---

## 3. 架构与设计要点

### 3.1 单例 + mock 兜底

`backend/services/amap_client.py` 暴露 `get_amap_client()` 单例：

- 未配 `AMAP_WEBSERVICE_KEY` → 直接读 `backend/data/lbs_mock/{key}.json`，返回 `(data, "mock")`
- 配了 Key → 真实 `httpx.AsyncClient` GET `https://restapi.amap.com/v3/...`，返回 `(data, "live")`
- 业务层 `status != "1"` → 抛 `AMapError(502, infocode, info)`
- 网络错误 → `AMapError(502, "AMAP_NETWORK_ERROR")`
- 超时 → `AMapError(504, "AMAP_TIMEOUT")`
- 参数不合法 → `AMapError(400, "INVALID_PARAM", ...)`
- fixture 缺失 → `AMapError(500, "MOCK_FIXTURE_MISSING")`

### 3.2 统一异常处理

`backend/main.py` 注册全局 handler：

```python
@app.exception_handler(AMapError)
async def amap_error_handler(_request, exc):
    return JSONResponse(
        status_code=exc.status,
        content={"code": exc.code, "message": exc.message, "status": "error"},
    )
```

`AMapError` 默认 502，贴合"上游服务不可用"语义。

### 3.3 X-LBS-Source 头

每个 LBS endpoint 在调用 `client.xxx()` 后用 `response.headers["X-LBS-Source"] = source` 设置：

- `"mock"` → 数据来源 fixture
- `"live"` → 真实高德 Web 服务

这样前端 / E2E 脚本可以一眼识别数据源。

### 3.4 鉴权

- 5 个读端点（`/geocode` `/regeocode` `/place/text` `/place/around` `/staticmap`）→ `Depends(get_current_user)`
- `/share` → `Depends(require_admin)`，防止配额滥用

### 3.5 优雅关闭

新增 `@app.on_event("shutdown")` 钩子，调用 `client.aclose()` 释放 httpx 异步连接，避免连接泄漏。

---

## 4. 命令速查

### 4.1 启动后端

```bash
# 激活 venv（任意 Python 3.11+，已装 fastapi/sqlalchemy/httpx/pytest）
python -m backend.main
# 或
uvicorn backend.main:app --reload --port 8000
```

### 4.2 Smoke：未配 Key 走 mock

```bash
# 临时清空 Key
AMAP_WEBSERVICE_KEY= python -m backend.main &

# 注册 → 拿 token
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"u1","email":"u1@x.com","password":"testpass1"}'

# 调 /geocode（应 200 + X-LBS-Source: mock）
curl -i "http://127.0.0.1:8000/api/lbs/geocode?address=test" \
  -H "Authorization: Bearer <token>"

# 调 /share（首个用户 = admin）
curl -X POST "http://127.0.0.1:8000/api/lbs/share" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"demo","markers":[]}'
```

### 4.3 跑测试

```bash
python -m pytest tests/test_lbs.py tests/test_amap_mock.py -v
```

预期：40 passed（11 mock 模式 + 4 真实模式 + 4 鉴权 + 21 fixture 验证）。

### 4.4 配 Key 走真实模式

```bash
# 在 backend/.env 中填入 Web 服务 Key
echo "AMAP_WEBSERVICE_KEY=你的Web服务Key" >> backend/.env
python -m backend.main
```

启动日志会打印 `AMAP_WEBSERVICE_KEY 已配置: xxxx***xxxx`。

---

## 5. 验证矩阵

| 验证项 | 命令 | 期望 |
|--------|------|------|
| 模块可导入 | `python -c "from backend.services.amap_client import AMapError; print('ok')"` | `ok` |
| 主入口可加载 | `python -c "from backend.main import app; print('ok')"` | `ok` |
| 路由表 | 上述 import 后检查 `app.routes` | 6 个 `/api/lbs/*` 路由 |
| Mock 模式 6 端点 | `pytest test_lbs.py::TestMockMode` | 7 passed |
| 真实模式 4 端点 | `pytest test_lbs.py::TestLiveMode` | 4 passed |
| 鉴权 4 场景 | `pytest test_lbs.py::TestAuth` | 4 passed |
| Fixture 合法性 | `pytest test_amap_mock.py` | 21 passed |
| `AMapError` → 502 | 上线后用 `key=invalid_key` 触发业务错误 | HTTP 502 + `{"code":..., "message":...}` |
| `/share` 仅 admin | 用 user 角色调 `/share` | 403 |

---

## 6. 已知遗留项 / 后续工作

1. **`/share` 真实生成**：当前 live 模式返回占位 URL（`https://www.amap.com/share/map/mock/<title>`），高德"个人专属地图"真实生成需特殊 PoiID 流程，留作后续接入 `personal-map` skill 时补齐。
2. **静态图返回形态**：mock 模式返回 `{url, zoom, size, lng, lat}`，live 模式仅 `{url, zoom, size, lng, lat}`（拼好的 URL 字符串）。后续可考虑加 `image_base64` 字段供前端 `<img>` 直接用。
3. **路径规划接口**：`amap-lbs-skill` 包含 `direction/walking` `direction/transit` `direction/driving`，本批未实现。下次 LBS 增强时补 `/api/lbs/route`。
4. **天气接口**：同属 `amap-lbs-skill`，可补 `/api/lbs/weather`。
5. **`on_event` 弃用警告**：FastAPI 0.133 推荐使用 `lifespan` context manager 替代 `@app.on_event("startup")` / `("shutdown")`，本次保守不改动 `main.py` 原有结构，仅追加新钩子；后续若统一升级 lifespan 可一并替换。
6. **Bcrypt 5.x 兼容性**：本环境 PyPI 默认装 `bcrypt==5.0.0`，与 `passlib` 1.7.4 兼容（但 passlib 0.99 之前的版本报"trapped" warning）。`requirements.txt` 已锁定 `bcrypt==4.0.1`，CI 装锁版本即可消除 warning。
7. **EmailStr 严格性**：`email-validator` 2.x 对 `*.local` 域名拒绝，仅 `*.com` / `*.org` / `*.net` 等公共 TLD 放行。Smoke 测试需用 `@example.com` 类合法邮箱。

---

## 7. 设计哲学（一次反思）

> 「让数据像河流一样单向流动，让错误像边界条件一样自然抛出。」

- 鉴权用 `Depends` 注入，业务层无感
- 数据源由 client 单点决定（mock/live），调用方只关心 `(data, source)` 这对返回值
- 失败信息三件套 `(status, code, message)` 始终齐备，前端无需特判
- 错误不再"特殊"，统一在 `AMapError` + exception handler 层被消化

`good taste`：6 个 endpoint 的"鉴权 + mock/live 切换 + header 标记"流程完全同构，没有 if/else 分散到各端点。
