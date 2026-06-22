"""
报表下载端点状态码测试
======================

验证 ``backend/api/reports.py`` 的 ``GET /api/reports/{id}/download`` 端点
对不同 job 状态 / 鉴权 / 文件存在性返回正确的状态码。

测试矩阵
--------

| 用例                          | 期望状态码 |
|-------------------------------|------------|
| 未带 token                    | 401        |
| status=completed + 文件存在   | 200        |
| status=running                | 409        |
| status=completed + 文件缺失   | 410        |
| output_path 是绝对路径        | 200        |

设计要点
--------
- 不启 uvicorn；用 ``TestClient`` + ``dependency_overrides`` 注入假 user
- 复用 ``_run_export`` 的 builder 模式（参考 test_reports.py）
- 必要的数据清理在 fixture 末尾执行

运行：
    cd e:\\truth-视觉实践
    python -m pytest tests/test_report_download.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# PowerShell 默认 GBK
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.reports import (  # noqa: E402
    REPORT_BUILDERS,
    register_builder,
    router as reports_router,
)
from backend.db.base import (  # noqa: E402
    DATA_DIR,
    Base,
    SessionLocal,
    engine,
)
from backend.db.models import ExportJob, User  # noqa: E402
from backend.security.deps import get_current_user  # noqa: E402
from backend.security.password import hash_password  # noqa: E402


# ==================== 测试应用 ====================
app = FastAPI()
app.include_router(reports_router, prefix="/api", tags=["reports"])


# ==================== Helpers ====================
REPORTS_DIR = Path(DATA_DIR) / "reports"


def _ensure_user(db, username: str = "dl_tester") -> User:
    """确保 DB 中存在测试用户。"""
    u = db.query(User).filter(User.username == username).first()
    if u is None:
        u = User(
            username=username,
            email=f"{username}@test.local",
            password_hash=hash_password("dl123"),
            role="user",
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    return u


def _create_job(db, user_id: int, status: str, output_path: str | None) -> int:
    """插入一条 ExportJob 并返回 id。"""
    job = ExportJob(
        user_id=user_id,
        kind="txt",
        params_json=json.dumps({"time_range": None, "class_filter": None}, ensure_ascii=False),
        output_path=output_path,
        status=status,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


def _override_user(user: User):
    """生成 dependency override 闭包。"""
    def _override() -> User:
        return user
    return _override


# ==================== Fixtures ====================
@pytest.fixture(autouse=True)
def _setup_db():
    """建表 + 创建测试用户 + 测试结束清理。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = _ensure_user(db)
        user_id = user.id
    finally:
        db.close()

    yield {"user_id": user_id}

    # 测试结束：清理本次测试创建的 job
    db = SessionLocal()
    try:
        db.query(ExportJob).filter(ExportJob.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.username == "dl_tester").delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
    # 清理可能注册的 builder
    REPORT_BUILDERS.pop("dl_test_txt", None)


# ==================== Test 1: 未带 token → 401 ====================
def test_download_unauthenticated_401(_setup_db) -> None:
    """不带 Authorization 头 → 401。"""
    # 清空 override 让依赖走真实的 get_current_user
    app.dependency_overrides.pop(get_current_user, None)

    client = TestClient(app)
    r = client.get("/api/reports/1/download")
    assert r.status_code == 401, (
        f"未鉴权应 401，实际 {r.status_code}: {r.text[:200]}"
    )
    print(f"\n  ✓ 未鉴权 → 401")


# ==================== Test 2: status=completed + 文件存在 → 200 ====================
def test_download_completed_returns_200(_setup_db) -> None:
    """status=completed + 文件存在 → 200 + FileResponse 流。"""
    user_id = _setup_db["user_id"]

    # 准备真实文件（相对 DATA_DIR 父目录的路径，与 _run_export 写入方式一致）
    user_dir = REPORTS_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / "dl_test_completed.txt"
    file_path.write_text("hello world", encoding="utf-8")
    rel_path = str(file_path.relative_to(REPORTS_DIR.parent))

    db = SessionLocal()
    try:
        job_id = _create_job(db, user_id, status="completed", output_path=rel_path)
        user = db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()

    app.dependency_overrides[get_current_user] = _override_user(user)
    client = TestClient(app)
    r = client.get(f"/api/reports/{job_id}/download")
    assert r.status_code == 200, (
        f"completed + 文件存在应 200，实际 {r.status_code}: {r.text[:200]}"
    )
    # 验证文件流内容
    body = r.content
    assert b"hello world" in body, f"文件内容应含 'hello world'，实际 {body!r}"
    print(f"\n  ✓ completed + 文件存在 → 200, content={body!r}")


# ==================== Test 3: status=running → 409 ====================
def test_download_running_returns_409(_setup_db) -> None:
    """status=running → 409。"""
    user_id = _setup_db["user_id"]

    db = SessionLocal()
    try:
        # output_path 故意不创建文件（即使存在也会被 status 检查拦截）
        job_id = _create_job(db, user_id, status="running", output_path="reports/dummy.txt")
        user = db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()

    app.dependency_overrides[get_current_user] = _override_user(user)
    client = TestClient(app)
    r = client.get(f"/api/reports/{job_id}/download")
    assert r.status_code == 409, (
        f"status=running 应 409，实际 {r.status_code}: {r.text[:200]}"
    )
    detail = r.json().get("detail", "")
    assert "running" in str(detail).lower(), f"detail 应说明状态: {detail}"
    print(f"\n  ✓ status=running → 409, detail={detail}")


# ==================== Test 4: status=completed + 文件缺失 → 410 ====================
def test_download_completed_missing_file_returns_410(_setup_db) -> None:
    """status=completed 但 output_path 指向不存在的文件 → 410。"""
    user_id = _setup_db["user_id"]

    db = SessionLocal()
    try:
        # 指向一个**不存在的**文件
        missing_path = "reports/999/nonexistent_dl_test.txt"
        job_id = _create_job(db, user_id, status="completed", output_path=missing_path)
        user = db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()

    app.dependency_overrides[get_current_user] = _override_user(user)
    client = TestClient(app)
    r = client.get(f"/api/reports/{job_id}/download")
    assert r.status_code == 410, (
        f"completed + 文件缺失应 410，实际 {r.status_code}: {r.text[:200]}"
    )
    print(f"\n  ✓ completed + 文件缺失 → 410")


# ==================== Test 5: output_path 是绝对路径 → 200 ====================
def test_download_with_absolute_path(_setup_db) -> None:
    """output_path 是绝对路径 → 端点应能解析并返回 200。"""
    user_id = _setup_db["user_id"]

    # 创建一个真实存在的文件，然后**直接写绝对路径**到 output_path
    abs_file = Path(DATA_DIR).resolve() / "reports" / "dl_test_abs.txt"
    abs_file.parent.mkdir(parents=True, exist_ok=True)
    abs_file.write_text("absolute path ok", encoding="utf-8")

    db = SessionLocal()
    try:
        # 注意：这里故意写绝对路径，验证端点对绝对路径的兼容性
        job_id = _create_job(
            db, user_id, status="completed", output_path=str(abs_file)
        )
        user = db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()

    app.dependency_overrides[get_current_user] = _override_user(user)
    client = TestClient(app)
    r = client.get(f"/api/reports/{job_id}/download")
    assert r.status_code == 200, (
        f"output_path 是绝对路径时端点应能找到文件并 200，"
        f"实际 {r.status_code}: {r.text[:200]}"
    )
    body = r.content
    assert b"absolute path ok" in body, f"绝对路径文件内容应能读到，实际 {body!r}"
    print(f"\n  ✓ output_path 是绝对路径 → 200, content={body!r}")


# ==================== Pytest 入口兼容 ====================
def main() -> int:
    """允许 ``python tests/test_report_download.py`` 直接跑。"""
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())
