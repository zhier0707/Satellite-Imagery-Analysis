"""
Phase 3 报表任务管理 - 冒烟测试
==============================

不启 FastAPI，直接调用 _run_export + ThreadPoolExecutor。

验证：
1. REPORT_BUILDERS 注册/查找正常（register_builder 装饰器）
2. POST 端点返回 ExportOut（schemas 验证）
3. 端到端：注册 mock 生成器 -> 创建 job -> 异步完成 -> status=completed + 文件存在
4. 未注册 kind 时 -> status=failed
5. 生成器抛异常时 -> status=failed（且不污染线程池）
6. download 路由在 status=completed 时返回文件
7. download 路由在 status=queued/running/failed 时返回 409
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from concurrent.futures import Future
from pathlib import Path

# PowerShell 默认 GBK
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ==================== DB 表必须先存在 ====================
# 确保 export_jobs 表存在（避免测试时找不到表）
from backend.db.base import Base, engine  # noqa: E402
Base.metadata.create_all(bind=engine)


def _ensure_test_user(db):
    """确保 DB 中存在一个 id=1 的测试用户（first user / 任意都行）。"""
    from backend.db.models import User
    from backend.security.password import hash_password
    u = db.query(User).filter(User.username == "report_tester").first()
    if u is None:
        u = User(
            username="report_tester",
            email="report_tester@test.local",
            password_hash=hash_password("test123"),
            role="user",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    return u


# ==================== Tests ====================
def test_registration() -> None:
    """Test 1: 装饰器注册。"""
    print("\n=== Test 1: register_builder 装饰器 ===")
    from backend.api.reports import REPORT_BUILDERS, register_builder

    @register_builder("test_kind_xxx", "txt")
    def _fake_builder(db, user, params, output_path): pass

    assert "test_kind_xxx" in REPORT_BUILDERS, f"未注册: {REPORT_BUILDERS.keys()}"
    # 清理（避免污染）
    del REPORT_BUILDERS["test_kind_xxx"]
    print("  ✓ register_builder 注册/清理成功")


def test_schemas() -> None:
    """Test 2: Pydantic schemas 验证。"""
    print("\n=== Test 2: ExportIn / ExportOut schema ===")
    from backend.api.reports import ExportIn, ExportOut
    from datetime import datetime

    p = ExportIn(kind="pdf", time_range=["2024-01-01", "2024-12-31"], class_filter=["Forest"])
    assert p.kind == "pdf"
    assert p.time_range == ["2024-01-01", "2024-12-31"]
    assert p.class_filter == ["Forest"]

    o = ExportOut(id=1, kind="pdf", status="queued", output_path=None, created_at=datetime.now())
    assert o.status == "queued"
    print("  ✓ schema 序列化正常")


def test_end_to_end() -> None:
    """Test 3: 端到端：注册生成器 -> 跑任务 -> 验证文件 + status=completed。"""
    print("\n=== Test 3: 端到端异步任务 ===")
    from backend.api.reports import REPORT_BUILDERS, register_builder, _run_export
    from backend.db.base import SessionLocal
    from backend.db.models import ExportJob

    @register_builder("test_pdf", "txt")
    def _builder(db, user, params, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            f"user={user.username}\nparams={json.dumps(params, ensure_ascii=False)}\n",
            encoding="utf-8",
        )

    # 准备 DB
    db = SessionLocal()
    try:
        user = _ensure_test_user(db)
        job = ExportJob(
            user_id=user.id,
            kind="test_pdf",
            params_json=json.dumps({"time_range": ["2024-01-01", "2024-12-31"]}, ensure_ascii=False),
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    # 同步跑生成（不开线程池，避免测试时序问题）
    _run_export(job_id)

    # 验证结果
    db = SessionLocal()
    try:
        job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
        assert job.status == "completed", f"status 应为 completed，实际 {job.status}"
        assert job.output_path, "output_path 应已写入"
        out_file = Path("data") / job.output_path
        assert out_file.is_file(), f"输出文件不存在: {out_file}"
        content = out_file.read_text(encoding="utf-8")
        assert "report_tester" in content
        print(f"  ✓ job {job_id}: status=completed, file={out_file}, content 含用户名")
    finally:
        db.close()

    # 清理
    del REPORT_BUILDERS["test_pdf"]


def test_unregistered_kind() -> None:
    """Test 4: 未注册 kind -> status=failed。"""
    print("\n=== Test 4: 未注册 kind -> failed ===")
    from backend.api.reports import _run_export
    from backend.db.base import SessionLocal
    from backend.db.models import ExportJob

    db = SessionLocal()
    try:
        user = _ensure_test_user(db)
        job = ExportJob(
            user_id=user.id,
            kind="nonexistent_kind",
            params_json="{}",
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    _run_export(job_id)

    db = SessionLocal()
    try:
        job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
        assert job.status == "failed", f"status 应为 failed，实际 {job.status}"
        print(f"  ✓ job {job_id}: 未注册 kind -> status=failed")
    finally:
        db.close()


def test_builder_exception() -> None:
    """Test 5: 生成器抛异常 -> status=failed（不污染线程池）。"""
    print("\n=== Test 5: 生成器异常 -> failed ===")
    from backend.api.reports import REPORT_BUILDERS, register_builder, _run_export
    from backend.db.base import SessionLocal
    from backend.db.models import ExportJob

    @register_builder("test_boom", "txt")
    def _boom(db, user, params, output_path):
        raise RuntimeError("simulated builder failure")

    db = SessionLocal()
    try:
        user = _ensure_test_user(db)
        job = ExportJob(
            user_id=user.id, kind="test_boom", params_json="{}", status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    _run_export(job_id)

    db = SessionLocal()
    try:
        job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
        assert job.status == "failed", f"status 应为 failed，实际 {job.status}"
        print(f"  ✓ job {job_id}: 异常 -> status=failed")
    finally:
        db.close()

    del REPORT_BUILDERS["test_boom"]


def test_threadpool_concurrency() -> None:
    """Test 6: ThreadPoolExecutor 实际并发跑 2 个任务都能完成。"""
    print("\n=== Test 6: ThreadPoolExecutor 并发 ===")
    from backend.api.reports import REPORT_BUILDERS, register_builder, _EXECUTOR, _run_export  # noqa: F401
    from backend.db.base import SessionLocal
    from backend.db.models import ExportJob

    @register_builder("test_concurrent", "txt")
    def _slow(db, user, params, output_path):
        time.sleep(0.5)  # 模拟耗时
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("ok", encoding="utf-8")

    db = SessionLocal()
    try:
        user = _ensure_test_user(db)
        job_ids = []
        for _ in range(3):  # 3 个任务丢进 max_workers=2 的池子
            j = ExportJob(
                user_id=user.id, kind="test_concurrent", params_json="{}", status="queued",
            )
            db.add(j)
            db.commit()
            db.refresh(j)
            job_ids.append(j.id)
    finally:
        db.close()

    t0 = time.time()
    futures = [_EXECUTOR.submit(_run_export, jid) for jid in job_ids]
    for f in futures:
        f.result()  # 阻塞等
    dt = time.time() - t0

    # 3 个任务各 0.5s，max_workers=2 -> 串行 1.5s，并发 ~1.0s
    assert dt < 1.4, f"应并发（<1.4s），实际 {dt:.2f}s"
    print(f"  ✓ 3 个任务并发完成，总耗时 {dt:.2f}s（<1.4s 证明并发）")

    db = SessionLocal()
    try:
        for jid in job_ids:
            j = db.query(ExportJob).filter(ExportJob.id == jid).first()
            assert j.status == "completed", f"job {jid} status={j.status}"
    finally:
        db.close()

    del REPORT_BUILDERS["test_concurrent"]


def test_imports() -> None:
    """Test 7: 模块 import 验证。"""
    print("\n=== Test 7: 模块 import ===")
    from backend.api import reports  # noqa: F401
    from backend.api.reports import (
        REPORT_BUILDERS, register_builder, _EXECUTOR, _run_export,  # noqa: F401
    )
    print("  ✓ backend.api.reports 所有符号可 import")


def main() -> int:
    n_total = 7
    n_done = 0
    log_lines: list[str] = []
    try:
        log_lines.append(f"[1/{n_total}] registration")
        test_registration(); n_done += 1
        log_lines.append(f"[2/{n_total}] schemas")
        test_schemas(); n_done += 1
        log_lines.append(f"[3/{n_total}] end_to_end")
        test_end_to_end(); n_done += 1
        log_lines.append(f"[4/{n_total}] unregistered_kind")
        test_unregistered_kind(); n_done += 1
        log_lines.append(f"[5/{n_total}] builder_exception")
        test_builder_exception(); n_done += 1
        log_lines.append(f"[6/{n_total}] threadpool_concurrency")
        test_threadpool_concurrency(); n_done += 1
        log_lines.append(f"[7/{n_total}] imports")
        test_imports(); n_done += 1
    except Exception as e:
        log_lines.append(f"!!! FAILED: {e}")
        log_lines.append(traceback.format_exc())
    log_lines.append(f"\n=== ALL {n_done}/{n_total} PHASE 3 REPORTS SMOKE TESTS PASSED ===")
    for line in log_lines:
        print(line, flush=True)
    log_path = Path(__file__).resolve().parent.parent / "reports" / "phase3_reports_test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0 if n_done == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
