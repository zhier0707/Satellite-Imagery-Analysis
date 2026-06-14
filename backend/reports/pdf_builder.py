"""
PDF 报表生成器
==============

调用入口：`build_pdf(db, user, params, output_path)`

输出段落：
- 标题（居中大字）
- 元信息（生成时间、用户名、时间范围）
- 汇总表（Platypus Table）：总记录数 / 时间范围 / Top-3 类别
- 饼图（matplotlib 生成临时 PNG 后用 Image 嵌入），各分类占比
- 变化检测列表
- 原始记录前 50 条表

依赖：reportlab、matplotlib（饼图）
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
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
    """按 user_id + (可选)时间范围 + (可选)类别过滤查 classify_records。"""
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


def _fetch_change_jobs(db: Session, user_id: int) -> list:
    from backend.db.models import ChangeJob
    return (
        db.query(ChangeJob)
        .filter(ChangeJob.user_id == user_id)
        .order_by(ChangeJob.created_at.desc())
        .all()
    )


# ==================== 饼图 ====================
def _make_pie_png(class_counter: Counter, tmp_dir: str) -> Optional[str]:
    """生成饼图 PNG，返回文件路径（写入 tmp_dir）；无数据返回 None。"""
    if not class_counter:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")  # 无 GUI 后端
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib 不可用，跳过饼图")
        return None

    labels = list(class_counter.keys())
    sizes = list(class_counter.values())
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    ax.set_title("Class Distribution")
    out = os.path.join(tmp_dir, "pie.png")
    plt.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out


# ==================== 主入口 ====================
def build_pdf(
    db: Session,
    user,
    params: dict[str, Any],
    output_path: Path,
) -> None:
    """生成 PDF 报表，写到 output_path。"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 准备数据
    rows = _fetch_classify_records(
        db, user.id,
        time_range=params.get("time_range"),
        class_filter=params.get("class_filter"),
    )
    change_jobs = _fetch_change_jobs(db, user.id)
    class_counter = Counter(r.top1_label for r in rows)

    # 注册中文字体（避免中文显示成方块）
    try:
        font_path = "C:/Windows/Fonts/msyh.ttc"
        if os.path.isfile(font_path):
            pdfmetrics.registerFont(TTFont("MicrosoftYaHei", font_path))
            font_name = "MicrosoftYaHei"
        else:
            font_name = "Helvetica"
    except Exception as e:
        log.warning("register CJK font failed: %s", e)
        font_name = "Helvetica"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontName=font_name, fontSize=20, alignment=1,  # CENTER
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName=font_name, fontSize=14)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName=font_name, fontSize=10)

    story: list = []
    story.append(Paragraph("Satellite Image Analysis Report", title_style))
    story.append(Spacer(1, 0.5 * cm))

    # 元信息
    meta = [
        ["User", user.username],
        ["Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")],
        ["Time Range", str(params.get("time_range") or "All")],
        ["Class Filter", ", ".join(params.get("class_filter") or []) or "All"],
    ]
    t = Table(meta, colWidths=[3 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name := font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # 汇总
    story.append(Paragraph("Overview", h2))
    summary = [["Total Records", str(len(rows))]]
    if rows:
        top3 = class_counter.most_common(3)
        for i, (name, cnt) in enumerate(top3, 1):
            summary.append([f"Top-{i} Class", f"{name} ({cnt})"])
    t = Table(summary, colWidths=[4 * cm, 11 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # 饼图
    pie = _make_pie_png(class_counter, tempfile.gettempdir())
    if pie:
        story.append(Paragraph("Class Distribution", h2))
        story.append(Image(pie, width=12 * cm, height=9 * cm))
        story.append(Spacer(1, 0.5 * cm))

    # 变化检测列表
    if change_jobs:
        story.append(Paragraph("Change Detection Jobs", h2))
        chg_rows = [["ID", "Created", "A", "B", "Status"]]
        for cj in change_jobs[:50]:
            chg_rows.append([
                str(cj.id),
                cj.created_at.strftime("%Y-%m-%d %H:%M"),
                cj.top1_a,
                cj.top1_b,
                cj.status,
            ])
        t = Table(chg_rows, colWidths=[1.5 * cm, 3.5 * cm, 4 * cm, 4 * cm, 2 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

    # 原始记录（前 50 条）
    if rows:
        story.append(Paragraph("Recent Classify Records (top 50)", h2))
        rec_rows = [["ID", "Time", "Top-1", "Score", "Duration(ms)"]]
        for r in rows[:50]:
            rec_rows.append([
                str(r.id),
                r.created_at.strftime("%Y-%m-%d %H:%M"),
                r.top1_label,
                f"{r.top1_score:.4f}",
                str(r.duration_ms),
            ])
        t = Table(rec_rows, colWidths=[1.5 * cm, 3.5 * cm, 5 * cm, 2.5 * cm, 2.5 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(t)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    doc.build(story)
    log.info("[pdf] %s 已生成（%d 条记录）", output_path, len(rows))
