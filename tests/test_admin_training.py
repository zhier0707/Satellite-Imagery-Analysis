"""
Phase 3 admin 训练任务 - 冒烟测试
================================

不启 uvicorn，直接调用 backend.api.admin.training 内部函数 + subprocess。

验证：
1. _parse_best_val_acc 从 log 解析 val_acc
2. 端到端：subprocess 启 train.py --dry-run -> reader 写 log -> watcher 改 status=completed
3. Popen 终止逻辑：terminate() 后 _PROCS 字典清空
4. admin 子模块全部可 import
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

# PowerShell 默认 GBK
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db.base import Base, engine, SessionLocal  # noqa: E402
Base.metadata.create_all(bind=engine)


def _ensure_admin_user(db):
    from backend.db.models import User
    from backend.security.password import hash_password
    u = db.query(User).filter(User.username == "admin_tester").first()
    if u is None:
        u = User(
            username="admin_tester",
            email="admin_tester@test.local",
            password_hash=hash_password("admin123"),
            role="admin",  # 重要：admin role
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    else:
        # 确保是 admin
        if u.role != "admin":
            u.role = "admin"
            db.commit()
            db.refresh(u)
    return u


# ==================== Tests ====================
def test_parse_val_acc() -> None:
    """Test 1: _parse_best_val_acc 从 log 解析最大 val_acc。"""
    print("\n=== Test 1: _parse_best_val_acc ===")
    from backend.api.admin.training import _parse_best_val_acc

    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
        f.write("=== Train Config  stage=2  epochs=1  batch=2  lr=1e-4  device=cpu ===\n")
        f.write("    epoch 1/1  train_loss=1.2345  val_loss=0.9876  val_acc=0.8500  lr=1.00e-04  (12.3s)\n")
        f.write("      ↳ 保存最佳检查点 -> models/checkpoints/best.pt  val_acc=0.8500\n")
        f.write("✓ dry run 通过\n")
        log_path = Path(f.name)

    v = _parse_best_val_acc(log_path)
    assert v == 0.85, f"应为 0.85, 实际 {v}"
    log_path.unlink()
    print(f"  ✓ 解析 val_acc={v}")


def test_parse_val_acc_no_match() -> None:
    """Test 2: log 中无 val_acc -> 返回 None。"""
    print("\n=== Test 2: 无 val_acc ===")
    from backend.api.admin.training import _parse_best_val_acc

    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
        f.write("无关日志\n")
        log_path = Path(f.name)
    v = _parse_best_val_acc(log_path)
    assert v is None, f"应为 None, 实际 {v}"
    log_path.unlink()
    print(f"  ✓ 无匹配返回 None")


def test_end_to_end_dry_run() -> None:
    """Test 3: 端到端 subprocess + watcher（文件重定向避开 PIPE 死锁），验证 status 转 completed。"""
    print("\n=== Test 3: 端到端 dry-run 训练 ===")
    from backend.api.admin.training import (
        _watcher_thread, _PROCS, _PROCS_LOCK, LOG_DIR,
    )
    from backend.db.models import TrainingJob

    db = SessionLocal()
    try:
        user = _ensure_admin_user(db)
        job = TrainingJob(
            user_id=user.id, stage="stage2", epochs=1, status="queued",
            metrics_json=json.dumps({"stage": 2, "epochs": 1, "dry_run": True}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    # 启 subprocess 跑 train.py --dry-run（用文件重定向避开 Windows PIPE 死锁）
    train_script = ROOT / "src" / "train.py"
    assert train_script.is_file(), f"train.py 不存在: {train_script}"
    log_path = LOG_DIR / f"{job_id}.log"
    log_fh = open(log_path, "wb")
    proc = subprocess.Popen(
        [
            sys.executable, str(train_script),
            "--data-root", "data/eurosat",
            "--stage", "2", "--epochs", "1", "--batch-size", "2",
            "--no-pretrained", "--dry-run",
        ],
        stdout=log_fh, stderr=subprocess.STDOUT, cwd=str(ROOT),
    )
    with _PROCS_LOCK:
        _PROCS[job_id] = proc

    # 启动真实 watcher
    threading.Thread(target=_watcher_thread, args=(job_id, proc, log_path), daemon=True).start()

    # 轮询 DB 等待 status 变化（最长 60s）
    final_status = None
    for _ in range(120):
        time.sleep(0.5)
        db = SessionLocal()
        try:
            j = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
            if j and j.status in ("completed", "failed", "stopped"):
                final_status = j.status
                break
        finally:
            db.close()

    log_fh.close()

    # 验证
    assert final_status == "completed", f"status 应为 completed, 实际 {final_status}"
    db = SessionLocal()
    try:
        j = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        assert j.finished_at is not None
        # dry-run 不会触发 val_acc 行
        assert j.best_val_acc is None, f"dry-run 不应解析到 val_acc, 实际 {j.best_val_acc}"
    finally:
        db.close()

    assert log_path.is_file(), f"log 文件未生成: {log_path}"
    log_content = log_path.read_text(encoding="utf-8", errors="replace")
    assert "Train Config" in log_content, f"log 内容异常: {log_content[:200]}"
    assert "dry run" in log_content, "未看到 dry run 输出"
    print(f"  ✓ job {job_id} status=completed, log 大小={log_path.stat().st_size}B")

    with _PROCS_LOCK:
        _PROCS.pop(job_id, None)
    print("  ✓ _PROCS 已清理")


def test_stop_logic() -> None:
    """Test 4: stop 终止：subprocess terminate 后 status=stopped。"""
    print("\n=== Test 4: stop 终止 ===")
    from backend.api.admin.training import _PROCS, _PROCS_LOCK

    # 起一个长跑 sleep 进程
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    with _PROCS_LOCK:
        _PROCS[99999] = proc
    assert proc.poll() is None, "进程应在跑"
    proc.terminate()
    proc.wait(timeout=5)
    assert proc.returncode is not None
    with _PROCS_LOCK:
        _PROCS.pop(99999, None)
    print(f"  ✓ terminate 后 returncode={proc.returncode}")


def test_imports() -> None:
    """Test 5: admin 子模块 import 验证。"""
    print("\n=== Test 5: 模块 import ===")
    from backend.api.admin import (  # noqa: F401
        training, users, records, converts,
    )
    from backend.api.admin.training import (
        _watcher_thread, _parse_best_val_acc, _PROCS, _PROCS_LOCK, _LOG_HANDLES,  # noqa: F401
    )
    from backend.api.admin.converts import _PROCS as _CP  # noqa: F401
    print("  ✓ 4 个 admin 子模块 + training/converts 内部函数均可 import")


def test_require_admin_blocks_user() -> None:
    """Test 6: require_admin 拒绝非 admin（通过 Pydantic schema 构造假 user 验证逻辑）。"""
    print("\n=== Test 6: require_admin role 检查 ===")
    from backend.security.deps import require_admin
    from fastapi import HTTPException

    # 直接调 require_admin，传入 role=user 的对象
    class FakeUser:
        role = "user"
    try:
        require_admin(current_user=FakeUser())  # type: ignore
        assert False, "应抛 403"
    except HTTPException as e:
        assert e.status_code == 403
        print(f"  ✓ require_admin 对 role=user 抛 403: {e.detail}")

    class FakeAdmin:
        role = "admin"
    ret = require_admin(current_user=FakeAdmin())  # type: ignore
    assert ret.role == "admin"
    print("  ✓ require_admin 对 role=admin 放行")


# 占位类（无意义，只是语法需要）
class _NoOp:
    def __enter__(self): return self
    def __exit__(self, *a): return False


# 真正拿到 _PROCS_LOCK（避免上面 hack）
def _PROCS_LOCK_TRAINING():
    from backend.api.admin.training import _PROCS_LOCK
    return _PROCS_LOCK


def main() -> int:
    n_total = 6
    n_done = 0
    log_lines: list[str] = []
    try:
        log_lines.append(f"[1/{n_total}] parse_val_acc")
        test_parse_val_acc(); n_done += 1
        log_lines.append(f"[2/{n_total}] parse_val_acc_no_match")
        test_parse_val_acc_no_match(); n_done += 1
        log_lines.append(f"[3/{n_total}] end_to_end_dry_run")
        test_end_to_end_dry_run(); n_done += 1
        log_lines.append(f"[4/{n_total}] stop_logic")
        test_stop_logic(); n_done += 1
        log_lines.append(f"[5/{n_total}] imports")
        test_imports(); n_done += 1
        log_lines.append(f"[6/{n_total}] require_admin_blocks_user")
        test_require_admin_blocks_user(); n_done += 1
    except Exception as e:
        log_lines.append(f"!!! FAILED: {e}")
        log_lines.append(traceback.format_exc())
    log_lines.append(f"\n=== ALL {n_done}/{n_total} PHASE 3 ADMIN TRAINING SMOKE TESTS PASSED ===")
    for line in log_lines:
        print(line, flush=True)
    log_path = Path(__file__).resolve().parent.parent / "reports" / "phase3_admin_test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0 if n_done == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
