"""
FastAPI 应用入口
================

启动：
    uvicorn backend.main:app --reload
    或：python -m backend.main
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.classify import router as classify_router
from backend.api.stats import router as stats_router
from backend.api.auth import router as auth_router
from backend.api.records import router as records_router
from backend.api.change import router as change_router
from backend.api.reports import router as reports_router
from backend.api.admin import router as admin_router
from backend.api.lbs import router as lbs_router
from backend.services.model_manager import ModelManager
from backend.services.model_manager import load_model
from backend.classes import EUROSAT_CLASSES
from backend.db.base import Base, engine
from backend.services.amap_client import AMapError

# ==================== .env 加载 ====================
# 轻量级 .env loader:不引入 python-dotenv 依赖
# 已存在的环境变量不会被覆盖,便于生产环境显式注入
def _load_dotenv(*candidates: str) -> str | None:
    """尝试按顺序加载 .env,返回第一个加载成功的路径,否则 None"""
    for path in candidates:
        p = Path(path)
        if not p.is_file():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
        return str(p)
    return None


_BACKEND_DIR = Path(__file__).resolve().parent
_loaded_env = _load_dotenv(
    _BACKEND_DIR / ".env",       # 标准启动: backend/main.py
    "backend/.env",              # 从项目根目录启动
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("backend")

if _loaded_env:
    log.info("已加载环境文件: %s", _loaded_env)
else:
    log.info("未找到 .env,使用系统环境变量")

app = FastAPI(
    title="Satellite Image Analysis API",
    description="基于 EfficientNetV2-M 的卫星图像分类与 Grad-CAM 可视化接口",
    version="0.1.0",
    classes=EUROSAT_CLASSES,
)

# CORS：允许前端开发服务器
# CORS_ALLOW_ORIGINS 环境变量(逗号分隔)可覆盖默认
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
]
_env_origins = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
allow_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    """启动钩子：建表 + 加载模型（模型失败不影响 mock 模式） + 注册报表生成器。"""
    log.info("starting up, ensuring database tables ...")
    # SQLite 启动时建表；幂等
    Base.metadata.create_all(bind=engine)
    log.info("attempting to load model ...")
    load_model()
    log.info("class labels: %s", EUROSAT_CLASSES)

    # 注册报表生成器（pdf / excel / csv）
    from backend.reports import register_all as _register_report_builders
    _register_report_builders()

    # 高德 Web Service Key 状态自检
    amap_key = os.environ.get("AMAP_WEBSERVICE_KEY", "").strip()
    if amap_key:
        masked = f"{amap_key[:4]}***{amap_key[-4:]}" if len(amap_key) > 8 else "***"
        log.info("AMAP_WEBSERVICE_KEY 已配置: %s", masked)
    else:
        log.warning(
            "AMAP_WEBSERVICE_KEY 未配置,后端 LBS API(POI/地理编码/路径规划)将无法使用。"
            "请在 backend/.env 中填入 Web 服务 Key。"
        )


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    """关闭钩子：释放 httpx 异步客户端连接。"""
    from backend.services.amap_client import get_amap_client
    await get_amap_client().aclose()
    log.info("AMap client closed")


@app.get("/")
def root() -> dict:
    return {
        "service": "satellite-image-api",
        "version": "0.1.0",
        "endpoints": ["/api/classify", "/api/heatmap", "/api/stats", "/docs"],
        "classes": EUROSAT_CLASSES,
    }


@app.get("/api/config/amap")
def amap_config_status() -> dict:
    """供前端探测后端 LBS 配置是否就绪(仅返回是否配置,不返回 Key 本身)。"""
    return {
        "webservice_key_configured": bool(
            os.environ.get("AMAP_WEBSERVICE_KEY", "").strip()
        ),
    }


app.include_router(classify_router, prefix="/api", tags=["classify"])
app.include_router(stats_router, prefix="/api", tags=["stats"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(records_router, prefix="/api", tags=["records"])
app.include_router(change_router, prefix="/api", tags=["change"])
app.include_router(reports_router, prefix="/api", tags=["reports"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(lbs_router, prefix="/api/lbs", tags=["lbs"])


# ==================== 全局异常处理 ====================
@app.exception_handler(AMapError)
async def amap_error_handler(_request: Request, exc: AMapError) -> JSONResponse:
    """AMapError 统一转为 502 + {code, message}。

    AMapError 内部的 status 字段已带有语义（400/500/502/504），
    但默认 502 Bad Gateway 是与"上游服务不可用"语义最贴合的码。
    """
    log.warning("[lbs] AMapError code=%s message=%s", exc.code, exc.message)
    return JSONResponse(
        status_code=exc.status,
        content={"code": exc.code, "message": exc.message, "status": "error"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
