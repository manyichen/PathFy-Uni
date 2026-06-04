"""按目标岗位生成独立三阶段成长计划。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.domains.report.constants import DIM_LABELS, MID_TERM_ACTIONS, SHORT_TERM_ACTIONS
from app.domains.report.growth import _top_gap_dimensions
from app.domains.report.recommendations import _DIM_HINTS, _text_blob


def _build_phase_items_for_target(
    insight: Dict[str, Any],
    *,
    phase: str,
) -> List[Dict[str, Any]]:
    gaps = (insight.get("match_preview") or {}).get("dimension_gaps") or {}
    top_dims = _top_gap_dimensions(gaps, 3)
    if not top_dims:
        top_dims = ["cap_req_growth", "cap_req_practice", "cap_req_teamwork"]

    actions_map = SHORT_TERM_ACTIONS if phase == "early" else MID_TERM_ACTIONS
    period = "0-3个月" if phase == "early" else "3-9个月"
    phase_key = "short_term" if phase == "early" else "mid_term"
    items: List[Dict[str, Any]] = []
    for idx, dim in enumerate(top_dims):
        items.append(
            {
                "phase": phase_key,
                "order": idx + 1,
                "focus_dimension": dim,
                "focus_label": DIM_LABELS.get(dim, dim),
                "period": period,
                "learning_path": actions_map.get(dim, [])[:2],
                "practice_plan": actions_map.get(dim, [])[1:2] or [],
                "milestone": (
                    f"{DIM_LABELS.get(dim, dim)}完成基础补齐并有可展示产出"
                    if phase == "early"
                    else f"{DIM_LABELS.get(dim, dim)}达到目标岗位可投递水平"
                ),
                "learning_path_refs": [],
                "practice_plan_refs": [],
            }
        )
    return items


def _late_phase_items(insight: Dict[str, Any]) -> List[Dict[str, Any]]:
    title = str(insight.get("title") or "目标岗位")
    company = str(insight.get("company") or "目标公司")
    ms = float((insight.get("match_preview") or {}).get("match_score") or 0)
    return [
        {
            "phase": "late",
            "order": 1,
            "focus_dimension": "cap_req_growth",
            "focus_label": "岗位就绪",
            "period": "9-12个月",
            "milestone": f"面向「{title} · {company}」完成简历/作品集/面试准备，匹配度稳定在 {ms:.0f} 分以上",
            "learning_path": [
                "整理 3 个可面试讲解的项目案例（含技术栈与个人贡献）",
                "完成 2 次模拟面试并记录改进点",
            ],
            "practice_plan": ["投递目标公司同类型岗位并跟踪反馈"],
            "learning_path_refs": [],
            "practice_plan_refs": [],
        }
    ]


def _attach_refs_to_items(
    items: List[Dict[str, Any]],
    *,
    rec_block: Dict[str, Any],
    phase_filter: str,
) -> None:
    lr_all = rec_block.get("learning_resources") or []
    cp_all = rec_block.get("competitions") or []

    for item in items:
        if not isinstance(item, dict):
            continue
        dim = str(item.get("focus_dimension") or "")
        hints = _DIM_HINTS.get(dim, [])
        lr_hits = []
        for lr in lr_all:
            if phase_filter == "early" and str(lr.get("phase") or "") == "mid_term":
                continue
            blob = _text_blob(lr.get("skill_tag"), lr.get("resource_name"))
            if any(h.lower() in blob for h in hints) or not hints:
                lr_hits.append(lr)
        lr_hits.sort(key=lambda x: -float(x.get("score") or 0))
        cp_hits = []
        for cp in cp_all:
            if phase_filter == "early":
                continue
            if dim in (cp.get("cap_tags") or []):
                cp_hits.append(cp)
            else:
                blob = _text_blob(cp.get("competition_name"), cp.get("competition_desc"))
                if any(h.lower() in blob for h in hints):
                    cp_hits.append(cp)
        cp_hits.sort(key=lambda x: -float(x.get("score") or 0))

        item["learning_path_refs"] = [
            {
                "kind": "learning_resource",
                "id": lr.get("resource_id"),
                "label": lr.get("resource_name"),
                "url": lr.get("resource_url"),
                "resource_type": lr.get("resource_type"),
                "difficulty": lr.get("difficulty"),
                "skill_tag": lr.get("skill_tag"),
                "rationale": lr.get("rationale"),
            }
            for lr in lr_hits[:3]
        ]
        item["practice_plan_refs"] = [
            {
                "kind": "competition",
                "id": cp.get("competition_id"),
                "label": cp.get("competition_name"),
                "url": cp.get("official_url"),
                "rationale": cp.get("rationale"),
            }
            for cp in cp_hits[:2]
        ]
        if lr_hits and isinstance(item.get("learning_path"), list):
            names = [str(x.get("resource_name") or "") for x in lr_hits[:2] if x.get("resource_name")]
            if names:
                item["learning_path"] = [f"优先学习：{'、'.join(names)}"] + (item.get("learning_path") or [])[:1]
        if cp_hits and isinstance(item.get("practice_plan"), list) and phase_filter != "early":
            cname = str(cp_hits[0].get("competition_name") or "")
            if cname:
                item["practice_plan"] = [f"建议参赛：{cname}"] + (item.get("practice_plan") or [])[:1]


def _narrative_snippet_for_target(
    insight: Dict[str, Any],
    *,
    early_items: List[Dict[str, Any]],
    rec_block: Dict[str, Any],
) -> Dict[str, str]:
    gaps = (insight.get("match_preview") or {}).get("dimension_gaps") or {}
    top_dims = _top_gap_dimensions(gaps, 2)
    gap_labels = [DIM_LABELS.get(d, d) for d in top_dims]
    ms = float((insight.get("match_preview") or {}).get("match_score") or 0)
    title = str(insight.get("display_title") or insight.get("title") or "目标岗位")
    lr_names = [
        str(x.get("resource_name") or "")
        for x in (rec_block.get("learning_resources") or [])[:2]
        if x.get("resource_name")
    ]
    cp_names = [
        str(x.get("competition_name") or "")
        for x in (rec_block.get("competitions") or [])[:1]
        if x.get("competition_name")
    ]
    focus = "、".join(gap_labels) if gap_labels else "核心能力"
    res_hint = ""
    if lr_names:
        res_hint = f"前期可优先{'、'.join(lr_names)}"
    if cp_names:
        res_hint = (res_hint + f"；中期关注{'、'.join(cp_names)}").strip("；")
    path = (
        f"面向{title}（当前匹配约 {ms:.0f} 分），建议先补齐{focus}，"
        f"按前期—中期—后期分步推进。"
    )
    if res_hint:
        path += res_hint + "。"
    exec_rem = (
        f"以月度复盘跟踪缺口收敛与成果产出；"
        f"前期里程碑：{early_items[0].get('milestone', '完成基础补齐') if early_items else '完成基础补齐'}。"
    )
    return {"path_advice": path[:220], "execution_reminder": exec_rem[:220]}


def build_plans_by_target(
    target_insights: List[Dict[str, Any]],
    recommendations: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rec_map: Dict[str, Dict[str, Any]] = {}
    for block in recommendations.get("by_target") or []:
        if isinstance(block, dict):
            jid = str(block.get("job_id") or "").strip()
            if jid:
                rec_map[jid] = block

    plans: List[Dict[str, Any]] = []
    for insight in target_insights:
        jid = str(insight.get("id") or "").strip()
        if not jid:
            continue
        rec_block = rec_map.get(jid) or {
            "job_id": jid,
            "job_title_name": str(insight.get("title") or ""),
            "learning_resources": [],
            "competitions": [],
        }
        gaps = (insight.get("match_preview") or {}).get("dimension_gaps") or {}
        top_gaps = _top_gap_dimensions(gaps, 3)

        early_items = _build_phase_items_for_target(insight, phase="early")
        mid_items = _build_phase_items_for_target(insight, phase="mid")
        late_items = _late_phase_items(insight)
        _attach_refs_to_items(early_items, rec_block=rec_block, phase_filter="early")
        _attach_refs_to_items(mid_items, rec_block=rec_block, phase_filter="mid")

        plans.append(
            {
                "job_id": jid,
                "display_title": str(insight.get("display_title") or insight.get("title") or jid),
                "job_title_name": str(rec_block.get("job_title_name") or insight.get("title") or ""),
                "company": str(insight.get("company") or ""),
                "location": str(insight.get("location") or ""),
                "match_score": float((insight.get("match_preview") or {}).get("match_score") or 0),
                "top_gaps": top_gaps,
                "top_gap_labels": [DIM_LABELS.get(d, d) for d in top_gaps],
                "dimension_gaps": gaps,
                "phases": {
                    "early": {
                        "key": "early",
                        "label": "前期",
                        "period": "0-3个月",
                        "summary": "补齐关键能力缺口，完成入门学习与小型实践。",
                        "items": early_items,
                    },
                    "mid": {
                        "key": "mid",
                        "label": "中期",
                        "period": "3-9个月",
                        "summary": "岗位化项目与竞赛实践，形成可展示成果。",
                        "items": mid_items,
                    },
                    "late": {
                        "key": "late",
                        "label": "后期",
                        "period": "9-12个月",
                        "summary": "简历、作品集与面试准备，达到可投递就绪状态。",
                        "items": late_items,
                    },
                },
                "recommendations": {
                    "learning_resources": rec_block.get("learning_resources") or [],
                    "competitions": rec_block.get("competitions") or [],
                },
                "narrative": _narrative_snippet_for_target(
                    insight, early_items=early_items, rec_block=rec_block
                ),
            }
        )

    return plans


def bind_plan_line_ids(
    plans: List[Dict[str, Any]],
    development_lines: Dict[str, Any],
) -> None:
    """将 plans 与 development_lines.lines 按顺序对齐 line_id。"""
    line_list = development_lines.get("lines") if isinstance(development_lines, dict) else []
    if not isinstance(line_list, list):
        return
    for i, plan in enumerate(plans):
        if not isinstance(plan, dict):
            continue
        if i < len(line_list) and isinstance(line_list[i], dict):
            plan["line_id"] = str(line_list[i].get("line_id") or f"line_{i + 1}")
        else:
            plan["line_id"] = f"line_{i + 1}"
