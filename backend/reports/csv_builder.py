"""
CSV 报表生成器
==============

调用入口：`build_csv(db, user, params, output_path)`

字段：id, created_at, top1_label, top1_score, image_path
输出：UTF-8 BOM（兼容 Excel 中文）

仅写 classify_records，无变化检测 / 汇总段。
"""
from __future__ import annotations

import csv
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


# ==================== 数据查询 ====================
def _fetch_classify_records(
    db: Session, user_id: int,
    time_range: Optional[list[str]] = None,
    class_filter: Optional[list[str]] = None,
) -> list:
    from backend.db.models import ClassifyRecord
    q = db.query(ClassifyRecord).filter(ClassifyRecord.user_id == user_id)
    if time_range and len(time_range) == 2:
        try:
            t0 = datetime.fromisoformat(time_range[0])
            t1 = datetime.fromisoformat(time_range[1])
            q = q.filter(and_(
                ClassifyRecord.created_at >= t0,
                ClassifyRecord.created_at <= t1,
            ))
        except ValueError as e:
            log.warning("invalid time_range %s: %s", time_range, e)
    rows = q.order_by(ClassifyRecord.created_at.desc()).all()
    if class_filter:
        rows = [r for r in rows if r.top1_label in class_filter]
    return rows


# ==================== 主入口 ====================
def build_csv(
    db: Session,
    user,
    params: dict[str, Any],
    output_path: Path,
) -> None:
    """生成 csv 报表，写到 output_path。UTF-8 BOM 兼容 Excel。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _fetch_classify_records(
        db, user.id,
        time_range=params.get("time_range"),
        class_filter=params.get("class_filter"),
    )

    fieldnames = ["id", "created_at", "top1_label", "top1_score", "image_path"]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        # utf-8-sig = 带 BOM，Excel 打开中文不乱码
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "id": r.id,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "top1_label": r.top1_label,
                "top1_score": round(r.top1_score, 4),
                "image_path": r.image_path,
            })

    log.info("[csv] %s 已生成（%d 条记录）", output_path, len(rows))
