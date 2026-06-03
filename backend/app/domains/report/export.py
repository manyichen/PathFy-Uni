"""生涯报告 PDF / HTML 导出。"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Dict, List


def _safe_text(v: Any, default: str = "") -> str:
    s = str(v if v is not None else default).strip()
    return escape(s if s else default)


def build_report_export_html(report_id: int, title: str, report_obj: Dict[str, Any]) -> str:
    student = report_obj.get("student") or {}
    targets = report_obj.get("targets") or []
    growth = report_obj.get("growth_plan") or {}
    short_term = growth.get("short_term") or []
    mid_term = growth.get("mid_term") or []
    evaluation = report_obj.get("evaluation") or {}
    metrics = evaluation.get("metrics") or []
    narrative = (report_obj.get("narrative") or {}).get("text") or ""

    target_rows = "".join(
        [
            (
                "<tr>"
                f"<td>{idx + 1}</td>"
                f"<td>{_safe_text(t.get('title'), '未命名岗位')}</td>"
                f"<td>{_safe_text(t.get('company'), '未知公司')}</td>"
                f"<td>{_safe_text((t.get('match_preview') or {}).get('match_score'), '0')}</td>"
                "</tr>"
            )
            for idx, t in enumerate(targets[:30])
        ]
    )
    if not target_rows:
        target_rows = '<tr><td colspan="4">暂无目标职业数据</td></tr>'

    def _plan_items(items: List[Dict[str, Any]]) -> str:
        rows = []
        for item in items[:20]:
            rows.append(
                "<li>"
                f"<strong>{_safe_text(item.get('focus_label'), '重点能力')}</strong>："
                f"{_safe_text(item.get('milestone'), '里程碑待补充')}"
                "</li>"
            )
        if not rows:
            rows.append("<li>暂无</li>")
        return "".join(rows)

    metric_rows = "".join(
        [
            (
                "<tr>"
                f"<td>{_safe_text(m.get('label') or m.get('code'), '指标')}</td>"
                f"<td>{_safe_text(m.get('cycle'), '-')}</td>"
                f"<td>{_safe_text(m.get('target'), '-')}</td>"
                "</tr>"
            )
            for m in metrics[:30]
            if isinstance(m, dict)
        ]
    )
    if not metric_rows:
        metric_rows = '<tr><td colspan="3">暂无评估指标</td></tr>'

    return f"""
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>career_report_{report_id}</title>
    <style>
        @page {{
            size: A4;
            margin: 16mm 12mm 18mm;
        }}
        :root {{
            --fg: #1f2937;
            --muted: #6b7280;
            --brand: #1d4ed8;
            --line: #dbe3f0;
            --soft: #f5f8ff;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            color: var(--fg);
            font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
            font-size: 13px;
            line-height: 1.65;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        .sheet {{ width: 100%; }}
        .header {{ border-bottom: 2px solid var(--brand); padding-bottom: 8px; margin-bottom: 14px; }}
        .title {{ margin: 0; font-size: 22px; color: #0f2f72; letter-spacing: 0.5px; }}
        .sub {{ margin-top: 6px; color: var(--muted); font-size: 12px; }}
        .section {{ margin-top: 14px; break-inside: avoid; }}
        .section-title {{
            background: linear-gradient(90deg, #e8f0ff, #f7faff);
            border-left: 4px solid var(--brand);
            padding: 6px 10px;
            font-size: 14px;
            font-weight: 700;
            color: #1e3a8a;
            margin: 0 0 8px;
        }}
        .kv {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; }}
        .chip {{ background: var(--soft); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }}
        table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
        th, td {{ border: 1px solid var(--line); padding: 7px 8px; vertical-align: top; word-break: break-word; }}
        th {{ background: #eff4ff; text-align: left; }}
        ul {{ margin: 6px 0 0; padding-left: 18px; }}
        li {{ margin: 4px 0; }}
        .narrative {{ white-space: pre-wrap; background: #fafcff; border: 1px solid var(--line); border-radius: 8px; padding: 10px; }}
        .footer-note {{ margin-top: 16px; color: var(--muted); font-size: 11px; }}
    </style>
</head>
<body>
    <div class="sheet">
        <header class="header">
            <h1 class="title">PathFy 生涯发展报告</h1>
            <div class="sub">报告编号：#{report_id} ｜ 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <div class="sub">报告标题：{_safe_text(title, '未命名报告')}</div>
        </header>

        <section class="section">
            <h2 class="section-title">一、学生画像</h2>
            <div class="kv">
                <div class="chip">姓名：{_safe_text(student.get('display_name'), '未知')}</div>
                <div class="chip">画像均分：{_safe_text(student.get('score_avg'), '0')}</div>
                <div class="chip" style="grid-column: 1 / -1;">教育背景：{_safe_text(student.get('education'), '未提供')}</div>
            </div>
        </section>

        <section class="section">
            <h2 class="section-title">二、目标职业</h2>
            <table>
                <thead><tr><th style="width:56px">序号</th><th>岗位</th><th style="width:160px">公司</th><th style="width:90px">匹配分</th></tr></thead>
                <tbody>{target_rows}</tbody>
            </table>
        </section>

        <section class="section">
            <h2 class="section-title">三、成长计划</h2>
            <div class="chip"><strong>短期计划（0-3个月）</strong><ul>{_plan_items(short_term)}</ul></div>
            <div style="height:8px"></div>
            <div class="chip"><strong>中期计划（3-12个月）</strong><ul>{_plan_items(mid_term)}</ul></div>
        </section>

        <section class="section">
            <h2 class="section-title">四、评估指标</h2>
            <table>
                <thead><tr><th>指标</th><th style="width:120px">周期</th><th style="width:180px">目标</th></tr></thead>
                <tbody>{metric_rows}</tbody>
            </table>
        </section>

        <section class="section">
            <h2 class="section-title">五、报告建议</h2>
            <div class="narrative">{_safe_text(narrative, '暂无建议')}</div>
        </section>

        <div class="footer-note">说明：本报告基于当前画像、目标岗位与阶段计划自动生成，建议结合导师反馈进行周期复盘。</div>
    </div>
</body>
</html>
"""


def render_pdf_with_playwright(html: str) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "未安装 Python 包 `playwright`。请在 backend 虚拟环境中执行："
            "`pip install playwright`，然后执行：`python -m playwright install chromium`。"
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                footer_template=(
                    '<div style="font-size:9px;color:#6b7280;width:100%;text-align:center;">'
                    '<span class="pageNumber"></span> / <span class="totalPages"></span>'
                    "</div>"
                ),
                margin={"top": "10mm", "right": "8mm", "bottom": "14mm", "left": "8mm"},
            )
            browser.close()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "executable" in msg or "browser" in msg or "chromium" in msg:
            raise RuntimeError(
                "Playwright 未下载 Chromium 浏览器。请在 backend 环境中执行："
                "`python -m playwright install chromium`。"
            ) from exc
        raise
    return pdf_bytes


_build_report_export_html = build_report_export_html
_render_pdf_with_playwright = render_pdf_with_playwright
