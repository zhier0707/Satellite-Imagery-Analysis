"""
报表生成器自动注册入口
======================

从 `backend.main` 启动时 import 本模块，把 pdf / excel / csv 三个生成器
注册到 `backend.api.reports.REPORT_BUILDERS`。
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def register_all() -> None:
    """注册所有内置生成器。"""
    from backend.api.reports import REPORT_BUILDERS, register_builder
    from backend.reports.csv_builder import build_csv
    from backend.reports.excel_builder import build_excel
    from backend.reports.pdf_builder import build_pdf

    register_builder("pdf", "pdf")(build_pdf)
    register_builder("excel", "xlsx")(build_excel)
    register_builder("csv", "csv")(build_csv)
    log.info("[reports] 已注册生成器: %s", sorted(REPORT_BUILDERS.keys()))
