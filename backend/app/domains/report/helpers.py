"""兼容转发：新代码请直接用 utils / export。"""
from app.domains.report.export import (
    _build_report_export_html,
    _render_pdf_with_playwright,
    build_report_export_html,
    render_pdf_with_playwright,
)
from app.domains.report.utils import (
    _clamp_int,
    _json_dumps,
    _parse_metric_target,
    _to_float,
    _truthy,
    clamp_int,
    json_dumps,
    parse_metric_target,
    to_float,
    truthy,
)
