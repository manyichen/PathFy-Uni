"""生涯报告 PDF / HTML 导出。

导出参数只控制本次渲染，不会写回报告 JSON。所有用户可编辑文本在进入 HTML
前统一转义，接口不接收任意 HTML。
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Dict, Iterable, List


SECTION_DEFAULTS = {
    "overview": True,
    "actions": True,
    "evidence": True,
    "route": True,
    "review": True,
    "resources": True,
    "preference": True,
}
ACTION_SCOPES = {"all", "todo", "done"}


class ReportExportValidationError(ValueError):
    """可安全反馈给客户端的导出参数错误。"""


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return escape(text if text else default)


def _plain_text(value: Any, default: str = "", max_chars: int = 3000) -> str:
    text = str(value if value is not None else default).strip()
    return (text or default)[:max_chars]


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _target_id(target: Dict[str, Any]) -> str:
    return str(target.get("job_id") or target.get("id") or "").strip()


def _target_label(target: Dict[str, Any]) -> str:
    return _plain_text(target.get("display_title") or target.get("title") or _target_id(target), "未命名目标", 160)


def _default_summary(report_obj: Dict[str, Any]) -> str:
    narrative = report_obj.get("narrative") if isinstance(report_obj.get("narrative"), dict) else {}
    return _plain_text(report_obj.get("summary") or report_obj.get("overview") or narrative.get("text"), "", 3000)


def normalize_export_options(
    title: str,
    report_obj: Dict[str, Any],
    export_options: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """校验并归一化结构化导出选项，拒绝空标题、空目标或空章节。"""
    supplied = export_options if isinstance(export_options, dict) else {}
    targets = _dicts(report_obj.get("targets"))
    available_ids = [_target_id(target) for target in targets if _target_id(target)]
    title_source = supplied.get("document_title") if "document_title" in supplied else title or "我的生涯发展档案"
    document_title = _plain_text(title_source, "", 120)
    if not document_title:
        raise ReportExportValidationError("请填写 PDF 标题")

    raw_selected = supplied.get("selected_target_job_ids")
    if raw_selected is None:
        selected_ids = available_ids[:10]
    elif isinstance(raw_selected, list):
        requested = {str(item).strip() for item in raw_selected if str(item).strip()}
        selected_ids = [job_id for job_id in available_ids if job_id in requested][:10]
    else:
        raise ReportExportValidationError("目标岗位参数格式不正确")
    if available_ids and not selected_ids:
        raise ReportExportValidationError("至少选择一个目标岗位")

    raw_sections = supplied.get("sections") if isinstance(supplied.get("sections"), dict) else {}
    sections = {
        key: raw_sections.get(key) if isinstance(raw_sections.get(key), bool) else default
        for key, default in SECTION_DEFAULTS.items()
    }
    if not any(sections.values()):
        raise ReportExportValidationError("至少保留一个报告章节")

    action_scope = str(supplied.get("action_scope") or "all").strip().lower()
    if action_scope not in ACTION_SCOPES:
        raise ReportExportValidationError("行动范围参数不正确")
    return {
        "document_title": document_title,
        "executive_summary": _plain_text(
            supplied.get("executive_summary") if "executive_summary" in supplied else _default_summary(report_obj), "", 3000
        ),
        "closing_note": _plain_text(
            supplied.get("closing_note") if "closing_note" in supplied else "这份档案用于支持下一步行动与复盘，请结合最新经历持续更新。", "", 2000
        ),
        "selected_target_job_ids": selected_ids,
        "sections": sections,
        "action_scope": action_scope,
        "show_source_details": supplied.get("show_source_details") is not False,
        "show_resource_links": supplied.get("show_resource_links") is not False,
    }


def _empty(message: str) -> str:
    return f'<div class="empty">{_safe_text(message)}</div>'


def _section(title: str, eyebrow: str, body: str) -> str:
    return f'<section class="section"><div class="section-heading"><span>{_safe_text(eyebrow)}</span><h2>{_safe_text(title)}</h2></div>{body}</section>'


def _overview_html(targets: List[Dict[str, Any]], summary: str) -> str:
    rows = []
    for index, target in enumerate(targets, 1):
        preview = target.get("match_preview") if isinstance(target.get("match_preview"), dict) else {}
        score = preview.get("match_score") if preview.get("match_score") is not None else target.get("match_score")
        rows.append(
            f"<tr><td>{index:02d}</td><td><strong>{_safe_text(_target_label(target))}</strong></td>"
            f"<td>{_safe_text(target.get('company'), '—')}</td><td>{_safe_text(score, '—')}</td></tr>"
        )
    table = (
        "<table><thead><tr><th>序号</th><th>目标岗位</th><th>公司 / 组织</th><th>匹配参考</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>" if rows else _empty("暂无目标岗位数据")
    )
    return f'<div class="lead-copy">{_safe_text(summary, "暂无摘要")}</div>{table}'


def _action_status(action: Dict[str, Any]) -> str:
    return "done" if bool(action.get("done")) or str(action.get("status") or "").lower() == "done" else "todo"


def _collect_actions(decisions: List[Dict[str, Any]], plans: List[Dict[str, Any]], scope: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for decision in decisions:
        for action in _dicts(decision.get("actions")):
            actions.append({**action, "target_label": decision.get("display_title") or decision.get("job_id")})
    if not actions:
        for plan in plans:
            next_month = plan.get("next_month_plan") if isinstance(plan.get("next_month_plan"), dict) else {}
            for item in _dicts(next_month.get("items")):
                for action in _dicts(item.get("custom_actions")):
                    actions.append({
                        **action,
                        "title": action.get("title") or action.get("text"),
                        "target_label": plan.get("display_title") or plan.get("job_id"),
                        "focus_label": item.get("focus_label"),
                        "deliverable": action.get("deliverable") or item.get("milestone"),
                    })
    if scope == "done":
        return [action for action in actions if _action_status(action) == "done"]
    if scope == "todo":
        return [action for action in actions if _action_status(action) != "done"]
    return actions


def _actions_html(decisions: List[Dict[str, Any]], plans: List[Dict[str, Any]], scope: str) -> str:
    cards = []
    for index, action in enumerate(_collect_actions(decisions, plans, scope)[:50], 1):
        acceptance = action.get("acceptance_criteria") or action.get("acceptance_rule") or []
        acceptance_text = "；".join(str(item) for item in acceptance) if isinstance(acceptance, list) else str(acceptance or "")
        done = _action_status(action) == "done"
        cards.append(f"""
        <article class="action-card {'is-done' if done else ''}"><div class="action-no">{index:02d}</div><div>
          <div class="card-meta">{_safe_text(action.get('target_label'), '目标岗位')} · {_safe_text(action.get('focus_label') or action.get('kind'), '行动')}</div>
          <h3>{_safe_text(action.get('title') or action.get('text'), '未命名行动')}</h3>
          <p><strong>交付物：</strong>{_safe_text(action.get('deliverable'), '待补充')}</p>
          <p><strong>验收：</strong>{_safe_text(acceptance_text, '待补充')}</p>
          <div class="action-tags"><span>{'已完成' if done else '待推进'}</span><span>{_safe_text(action.get('deadline'), '未设截止')}</span><span>{_safe_text(action.get('effort_hours'), '—')} 小时</span></div>
        </div></article>""")
    return '<div class="action-list">' + "".join(cards) + "</div>" if cards else _empty("当前筛选范围内暂无行动")


def _evidence_html(decisions: List[Dict[str, Any]], show_details: bool) -> str:
    cards = []
    kind_labels = {"strength": "优势", "gap": "差距", "risk": "风险", "opportunity": "机会"}
    for decision in decisions:
        for claim in _dicts(decision.get("claims"))[:16]:
            source_html = ""
            facts = _dicts(claim.get("facts"))
            if show_details and facts:
                fact_rows = "".join(
                    f"<li><strong>{_safe_text(fact.get('label'), '事实')}</strong>：{_safe_text(fact.get('value'), '—')}{_safe_text(fact.get('unit'))}"
                    f" <span>{_safe_text(fact.get('source_label'), '来源未标注')} · {_safe_text(fact.get('evidence_grade'), '—')} 级</span></li>"
                    for fact in facts[:8]
                )
                source_html = f'<ul class="fact-list">{fact_rows}</ul>'
            kind = str(claim.get("kind") or "gap")
            cards.append(f"""
            <article class="evidence-card tone-{_safe_text(kind)}"><div class="card-meta">{_safe_text(decision.get('display_title') or decision.get('job_id'))} / {kind_labels.get(kind, '判断')}</div>
              <h3>{_safe_text(claim.get('title'), '未命名判断')}</h3><p>{_safe_text(claim.get('summary'), '暂无说明')}</p>
              <p class="impact"><strong>意味着：</strong>{_safe_text(claim.get('impact'), '待进一步验证')}</p>{source_html}
            </article>""")
    return '<div class="card-grid">' + "".join(cards) + "</div>" if cards else _empty("暂无可核对的判断依据")


def _route_html(plans: List[Dict[str, Any]], report_obj: Dict[str, Any], selected_ids: set[str]) -> str:
    development = report_obj.get("development_lines") if isinstance(report_obj.get("development_lines"), dict) else {}
    lines = [line for line in _dicts(development.get("lines")) if str(line.get("target_job_id") or "") in selected_ids]
    adjustments = [item for item in _dicts(development.get("adjustments")) if str(item.get("target_job_id") or "") in selected_ids]
    blocks = []
    for plan in plans:
        job_id = str(plan.get("job_id") or "")
        phases = plan.get("phases") if isinstance(plan.get("phases"), dict) else {}
        phase_rows = []
        for phase in phases.values():
            if not isinstance(phase, dict):
                continue
            milestones = [str(item.get("milestone") or "").strip() for item in _dicts(phase.get("items"))]
            phase_rows.append(
                f"<div class='route-row'><b>{_safe_text(phase.get('period'), '阶段')}</b><div><strong>{_safe_text(phase.get('label'), '推进阶段')}</strong>"
                f"<p>{_safe_text(phase.get('summary') or '；'.join(filter(None, milestones)), '暂无阶段说明')}</p></div></div>"
            )
        line = next((item for item in lines if str(item.get("target_job_id") or "") == job_id), {})
        actual_rows = []
        for point in _dicts(line.get("timeline")):
            detail = point.get("detail") if isinstance(point.get("detail"), dict) else {}
            if not (point.get("review_id") or detail or str(point.get("kind") or "") == "origin"):
                continue
            actual_rows.append(
                f"<li><b>{_safe_text(point.get('month'), '0')} 月 · {_safe_text(point.get('label'), '记录')}</b>"
                f"<span>{_safe_text(detail.get('llm_summary') or detail.get('review_text'), '报告起点')}</span></li>"
            )
        adjustment_rows = [
            f"<li><b>{_safe_text(item.get('plan_month') or item.get('month'), '—')} 月 · 计划调整</b><span>{_safe_text(item.get('label'), '调整推进重点')}</span></li>"
            for item in adjustments if str(item.get("target_job_id") or "") == job_id
        ]
        blocks.append(f"""
        <article class="route-block"><h3>{_safe_text(plan.get('display_title') or job_id, '目标岗位')}</h3><div class="route-grid">
          <div><div class="subheading">阶段计划</div>{''.join(phase_rows) or _empty('暂无阶段计划')}</div>
          <div><div class="subheading">真实节点与调整</div><ul class="event-list">{''.join(actual_rows + adjustment_rows) or '<li><span>尚无已确认复盘节点</span></li>'}</ul></div>
        </div></article>""")
    return "".join(blocks) if blocks else _empty("暂无推进路线")


def _review_html(report_obj: Dict[str, Any], selected_ids: set[str]) -> str:
    evaluation = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
    review = evaluation.get("latest_review") if isinstance(evaluation.get("latest_review"), dict) else {}
    review_job_id = str(review.get("job_id") or "")
    if selected_ids and review_job_id and review_job_id not in selected_ids:
        by_target = evaluation.get("latest_reviews_by_target") if isinstance(evaluation.get("latest_reviews_by_target"), dict) else {}
        candidates = [by_target.get(job_id) for job_id in selected_ids if isinstance(by_target.get(job_id), dict)]
        review = max(candidates, key=lambda item: int(item.get("review_id") or 0), default={})
    insights = report_obj.get("longitudinal_insights") if isinstance(report_obj.get("longitudinal_insights"), dict) else {}
    execution = insights.get("execution_profile") if isinstance(insights.get("execution_profile"), dict) else {}
    if not review and not execution:
        return _empty("尚无已确认复盘；草稿不会作为事实写入 PDF")
    metric = review.get("evaluation") if isinstance(review.get("evaluation"), dict) else {}
    rate = metric.get("pass_rate")
    rate_text = f"{round(float(rate) * 100)}%" if isinstance(rate, (int, float)) and float(rate) <= 1 else _plain_text(rate, "—", 20)
    personalization = insights.get("personalization") if isinstance(insights.get("personalization"), dict) else {}
    return f"""
    <div class="review-summary"><div><span>最近确认复盘</span><strong>#{_safe_text(review.get('review_id'), '—')}</strong></div>
      <div><span>指标达成率</span><strong>{_safe_text(rate_text, '—')}</strong></div>
      <div><span>当前执行判断</span><strong>{_safe_text(execution.get('diagnosis_label'), '数据积累中')}</strong></div></div>
    <div class="lead-copy"><strong>复盘原始记录</strong><br>{_safe_text(review.get('review_text'), '暂无已确认复盘文本')}</div>
    <div class="note"><strong>校准建议：</strong>{_safe_text(personalization.get('focus'), '继续记录可核对的行动结果，再决定是否调整计划。')}</div>"""


def _resource_items(plans: List[Dict[str, Any]], report_obj: Dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    sets: List[Dict[str, Any]] = []
    for plan in plans:
        if isinstance(plan.get("recommendations"), dict):
            sets.append(plan["recommendations"])
    recommendations = report_obj.get("recommendations") if isinstance(report_obj.get("recommendations"), dict) else {}
    sets.extend(_dicts(recommendations.get("by_target")))
    seen = set()
    for recommendation in sets:
        for kind, key, name_key, url_key in (
            ("学习资源", "learning_resources", "resource_name", "resource_url"),
            ("竞赛实践", "competitions", "competition_name", "official_url"),
        ):
            for item in _dicts(recommendation.get(key)):
                name = _plain_text(item.get(name_key) or item.get("label"), "未命名资源", 240)
                url = _plain_text(item.get(url_key) or item.get("url"), "", 1000)
                marker = (kind, name, url)
                if marker in seen:
                    continue
                seen.add(marker)
                yield kind, name, url


def _resources_html(plans: List[Dict[str, Any]], report_obj: Dict[str, Any], show_links: bool) -> str:
    rows = []
    for kind, name, url in list(_resource_items(plans, report_obj))[:40]:
        link = f'<br><span class="resource-link">{_safe_text(url)}</span>' if show_links and url else ""
        rows.append(f"<tr><td>{_safe_text(kind)}</td><td><strong>{_safe_text(name)}</strong>{link}</td></tr>")
    return f"<table><thead><tr><th>类型</th><th>资源</th></tr></thead><tbody>{''.join(rows)}</tbody></table>" if rows else _empty("暂无资源推荐")


def _preference_html(report_obj: Dict[str, Any]) -> str:
    strategy = report_obj.get("preference_strategy") if isinstance(report_obj.get("preference_strategy"), dict) else {}
    cards = []
    for item in _dicts(strategy.get("sections")):
        cards.append(f"""<article class="preference-card"><h3>{_safe_text(item.get('title'), '执行方式')}</h3>
          <p>{_safe_text(item.get('recommendation'), '暂无建议')}</p><small>依据：{_safe_text(item.get('rationale'), '—')}<br>备选：{_safe_text(item.get('alternative'), '—')}</small></article>""")
    disclaimer = _safe_text(strategy.get("disclaimer"), "执行偏好只用于安排方式，不等同于能力评价。")
    return ('<div class="card-grid">' + "".join(cards) + f'</div><p class="disclaimer">{disclaimer}</p>') if cards else _empty("暂无执行偏好建议")


def build_report_export_html(
    report_id: int,
    title: str,
    report_obj: Dict[str, Any],
    export_options: Dict[str, Any] | None = None,
) -> str:
    options = normalize_export_options(title, report_obj, export_options)
    selected_ids = set(options["selected_target_job_ids"])
    targets = [item for item in _dicts(report_obj.get("targets")) if not selected_ids or _target_id(item) in selected_ids]
    plans = [item for item in _dicts(report_obj.get("plans_by_target")) if not selected_ids or str(item.get("job_id") or "") in selected_ids]
    support = report_obj.get("decision_support") if isinstance(report_obj.get("decision_support"), dict) else {}
    decisions = [item for item in _dicts(support.get("target_decisions")) if not selected_ids or str(item.get("job_id") or "") in selected_ids]
    sections = options["sections"]
    rendered_sections = []
    section_number = 0

    def add(enabled: bool, heading: str, body: str) -> None:
        nonlocal section_number
        if enabled:
            section_number += 1
            rendered_sections.append(_section(heading, f"{section_number:02d} / REPORT", body))

    add(sections["overview"], "当前判断", _overview_html(targets, options["executive_summary"]))
    add(sections["actions"], "本月行动", _actions_html(decisions, plans, options["action_scope"]))
    add(sections["evidence"], "判断依据", _evidence_html(decisions, options["show_source_details"]))
    add(sections["route"], "推进路线", _route_html(plans, report_obj, selected_ids))
    add(sections["review"], "复盘与校准", _review_html(report_obj, selected_ids))
    add(sections["resources"], "资源清单", _resources_html(plans, report_obj, options["show_resource_links"]))
    add(sections["preference"], "执行方式建议", _preference_html(report_obj))
    target_names = " / ".join(_target_label(target) for target in targets) or "未设置目标"
    closing = _safe_text(options["closing_note"], "")
    closing_html = f'<section class="closing"><span>EXPORT NOTE</span><p>{closing}</p></section>' if closing else ""

    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><title>career_report_{report_id}</title>
<style>
@page{{size:A4;margin:15mm 13mm 18mm}}:root{{--ink:#26363a;--muted:#65757b;--teal:#087f77;--blue:#2563eb;--line:#d8e2e5;--paper:#fffdf7;--soft:#eff6f7}}
*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;font-size:11px;line-height:1.65;-webkit-print-color-adjust:exact;print-color-adjust:exact}}.sheet{{width:100%}}
.cover{{position:relative;min-height:232mm;border:1px solid #d8d4c8;background:repeating-linear-gradient(90deg,transparent 0 27px,rgba(49,65,64,.035) 28px),var(--paper);padding:18mm 14mm;page-break-after:always}}.cover:after{{position:absolute;right:0;top:0;width:30mm;height:30mm;background:linear-gradient(225deg,#d8dfd6 0 50%,transparent 51%);content:""}}.cover-head,.cover-foot{{display:flex;justify-content:space-between;border-bottom:1px solid rgba(38,54,58,.2);padding-bottom:4mm;color:#839095;font:600 9px/1.4 monospace;letter-spacing:.08em}}.cover-main{{margin-top:32mm}}.cover-kicker{{color:var(--teal);font-weight:800;letter-spacing:.06em}}.cover h1{{max-width:150mm;margin:3mm 0 5mm;font-size:30px;line-height:1.15;letter-spacing:-.04em}}.cover-summary{{max-width:150mm;color:var(--muted);font-size:12px;white-space:pre-wrap}}.target-band{{margin-top:12mm;border-block:1px solid rgba(38,54,58,.16);padding:5mm 0;font-weight:700}}.cover-foot{{position:absolute;right:14mm;bottom:13mm;left:14mm;border-top:1px solid rgba(38,54,58,.2);border-bottom:0;padding-top:4mm;padding-bottom:0}}
.section{{margin:0 0 9mm;break-inside:auto}}.section-heading{{display:grid;grid-template-columns:32mm 1fr;align-items:end;border-bottom:1px solid var(--line);margin-bottom:4mm;padding-bottom:2mm}}.section-heading span{{color:var(--teal);font:800 9px/1 monospace;letter-spacing:.08em}}.section-heading h2{{margin:0;font-size:20px;line-height:1.2;letter-spacing:-.03em}}.lead-copy{{margin-bottom:4mm;border-left:3px solid var(--teal);background:var(--soft);padding:3mm 4mm;white-space:pre-wrap}}table{{width:100%;border-collapse:collapse;break-inside:auto}}thead{{display:table-header-group}}tr{{break-inside:avoid}}th,td{{border-bottom:1px solid var(--line);padding:2.4mm;text-align:left;vertical-align:top}}th{{background:#edf4f6;color:#49616b;font-size:9px;letter-spacing:.04em}}
.action-list,.card-grid{{display:grid;grid-template-columns:1fr 1fr;gap:3mm}}.action-card,.evidence-card,.preference-card{{display:grid;grid-template-columns:9mm 1fr;gap:2mm;border:1px solid var(--line);border-radius:3mm;padding:3mm;break-inside:avoid}}.action-card.is-done{{background:#eef8f4}}.action-no{{color:var(--teal);font:800 9px/1.5 monospace}}h3{{margin:1mm 0 2mm;font-size:12px;line-height:1.4}}p{{margin:1mm 0}}.card-meta{{color:var(--teal);font-size:8px;font-weight:750;letter-spacing:.04em}}.action-tags{{display:flex;flex-wrap:wrap;gap:1.5mm;margin-top:2mm}}.action-tags span{{border-radius:99px;background:#e7eef2;padding:.5mm 2mm;color:#52646d;font-size:8px}}.evidence-card,.preference-card{{display:block}}.evidence-card{{border-top:3px solid #65a7d8}}.evidence-card.tone-strength{{border-top-color:#2cb7a5}}.evidence-card.tone-risk{{border-top-color:#e38962}}.impact{{background:#f3f6f7;padding:2mm}}.fact-list{{margin:2mm 0 0;padding-left:4mm}}.fact-list span{{color:var(--muted);font-size:8px}}
.route-block{{margin-bottom:5mm;border:1px solid var(--line);border-radius:3mm;padding:4mm;break-inside:avoid}}.route-block>h3{{font-size:15px}}.route-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5mm}}.subheading{{margin-bottom:2mm;color:var(--teal);font-size:9px;font-weight:800;letter-spacing:.05em}}.route-row{{display:grid;grid-template-columns:22mm 1fr;gap:2mm;border-top:1px solid var(--line);padding:2mm 0}}.route-row>b{{color:var(--teal)}}.event-list{{margin:0;padding:0;list-style:none}}.event-list li{{display:grid;gap:.5mm;border-top:1px solid var(--line);padding:2mm 0}}.event-list span{{color:var(--muted)}}.review-summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm;margin-bottom:4mm}}.review-summary div{{display:grid;gap:1mm;background:#edf4f6;padding:4mm}}.review-summary span{{color:var(--muted);font-size:9px}}.review-summary strong{{font-size:15px}}.note{{border:1px solid #ead28b;background:#fff7d7;padding:3mm}}.resource-link{{color:var(--blue);font-size:8px;word-break:break-all}}.preference-card small,.disclaimer{{color:var(--muted)}}.empty{{border:1px dashed var(--line);padding:5mm;color:var(--muted);text-align:center}}.closing{{margin-top:8mm;border-top:1px solid var(--line);padding-top:4mm;break-inside:avoid}}.closing span{{color:var(--teal);font:800 8px/1 monospace;letter-spacing:.08em}}.closing p{{white-space:pre-wrap}}.disclosure{{margin-top:7mm;color:var(--muted);font-size:8px}}
</style></head><body><main class="sheet">
<section class="cover"><div class="cover-head"><span>PATHFY / CAREER ARCHIVE</span><span>#{report_id}</span></div><div class="cover-main"><p class="cover-kicker">持续更新的生涯行动档案</p><h1>{_safe_text(options['document_title'])}</h1><p class="cover-summary">{_safe_text(options['executive_summary'], '暂无摘要')}</p><div class="target-band">当前目标 · {_safe_text(target_names)}</div></div><div class="cover-foot"><span>来源：报告事实 × 行动记录 × 已确认复盘</span><span>{datetime.now().strftime('%Y-%m-%d')}</span></div></section>
{''.join(rendered_sections)}{closing_html}<p class="disclosure">说明：这是基于报告 #{report_id} 生成的导出副本。编辑项仅影响本次 PDF，不会回写原报告；AI 生成内容仅作生涯决策参考，请结合真实经历核对。</p>
</main></body></html>"""


def render_pdf_with_playwright(html: str) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "未安装 Python 包 `playwright`。请在 backend 虚拟环境中执行："
            "`pip install playwright`，然后执行：`python -m playwright install chromium`。"
        ) from exc
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4", print_background=True, display_header_footer=True,
                header_template="<span></span>",
                footer_template='<div style="font-size:8px;color:#7b8a90;width:100%;padding:0 13mm;text-align:right;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                margin={"top": "10mm", "right": "8mm", "bottom": "14mm", "left": "8mm"},
            )
            browser.close()
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "executable" in message or "browser" in message or "chromium" in message:
            raise RuntimeError("Playwright 未下载 Chromium 浏览器。请在 backend 环境中执行：`python -m playwright install chromium`。") from exc
        raise
    return pdf_bytes
