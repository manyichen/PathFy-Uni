"""按目标岗位生成独立三阶段成长计划。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.domains.report.constants import DIM_LABELS, MID_TERM_ACTIONS, SHORT_TERM_ACTIONS
from app.domains.report.growth import _top_gap_dimensions
from app.domains.report.plan_item_enrichment import build_skeleton_custom_actions
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


def _lr_matches_dimension(lr: Dict[str, Any], dim: str) -> bool:
    hints = _DIM_HINTS.get(dim, [])
    if not hints:
        return False
    blob = _text_blob(lr.get("skill_tag"), lr.get("resource_name"), lr.get("resource_desc"))
    return any(h.lower() in blob for h in hints)


def _cp_matches_dimension(cp: Dict[str, Any], dim: str) -> bool:
    hints = _DIM_HINTS.get(dim, [])
    if dim in (cp.get("cap_tags") or []):
        return True
    if not hints:
        return False
    blob = _text_blob(cp.get("competition_name"), cp.get("competition_desc"))
    return any(h.lower() in blob for h in hints)


def _serialize_lr_ref(lr: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "learning_resource",
        "id": lr.get("resource_id"),
        "label": lr.get("resource_name"),
        "url": lr.get("resource_url"),
        "resource_type": lr.get("resource_type"),
        "difficulty": lr.get("difficulty"),
        "skill_tag": lr.get("skill_tag"),
        "rationale": lr.get("rationale"),
    }


def _serialize_cp_ref(cp: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "competition",
        "id": cp.get("competition_id"),
        "label": cp.get("competition_name"),
        "url": cp.get("official_url"),
        "rationale": cp.get("rationale"),
    }


def _attach_refs_deduped_per_job(
    early_items: List[Dict[str, Any]],
    mid_items: List[Dict[str, Any]],
    *,
    rec_block: Dict[str, Any],
) -> None:
    """同 job_id 内每个 learning_resource / competition 只绑定到一个 focus 维。"""
    lr_all = sorted(
        [x for x in (rec_block.get("learning_resources") or []) if isinstance(x, dict)],
        key=lambda x: -float(x.get("score") or 0),
    )
    cp_all = sorted(
        [x for x in (rec_block.get("competitions") or []) if isinstance(x, dict)],
        key=lambda x: -float(x.get("score") or 0),
    )
    used_lr: set[str] = set()
    used_cp: set[str] = set()

    for item in early_items:
        if not isinstance(item, dict):
            continue
        dim = str(item.get("focus_dimension") or "")
        best_lr = None
        best_score = -1.0
        for lr in lr_all:
            rid = str(lr.get("resource_id") or "").strip()
            if not rid or rid in used_lr:
                continue
            if str(lr.get("phase") or "") == "mid_term":
                continue
            if not _lr_matches_dimension(lr, dim):
                continue
            sc = float(lr.get("score") or 0)
            if sc > best_score:
                best_score = sc
                best_lr = lr
        item["learning_path_refs"] = [_serialize_lr_ref(best_lr)] if best_lr else []
        if best_lr:
            used_lr.add(str(best_lr.get("resource_id") or ""))

    for item in mid_items:
        if not isinstance(item, dict):
            continue
        dim = str(item.get("focus_dimension") or "")
        best_lr = None
        best_score = -1.0
        for lr in lr_all:
            rid = str(lr.get("resource_id") or "").strip()
            if not rid or rid in used_lr:
                continue
            if not _lr_matches_dimension(lr, dim):
                continue
            sc = float(lr.get("score") or 0)
            if sc > best_score:
                best_score = sc
                best_lr = lr
        item["learning_path_refs"] = [_serialize_lr_ref(best_lr)] if best_lr else []
        if best_lr:
            used_lr.add(str(best_lr.get("resource_id") or ""))

        best_cp = None
        best_cp_score = -1.0
        for cp in cp_all:
            cid = str(cp.get("competition_id") or "").strip()
            if not cid or cid in used_cp:
                continue
            if not _cp_matches_dimension(cp, dim):
                continue
            sc = float(cp.get("score") or 0)
            if sc > best_cp_score:
                best_cp_score = sc
                best_cp = cp
        item["practice_plan_refs"] = [_serialize_cp_ref(best_cp)] if best_cp else []
        if best_cp:
            used_cp.add(str(best_cp.get("competition_id") or ""))


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
        f"面向「{title}」，建议先补齐{focus}，"
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
        _attach_refs_deduped_per_job(early_items, mid_items, rec_block=rec_block)

        company = str(insight.get("company") or "")
        job_title = str(rec_block.get("job_title_name") or insight.get("title") or "")
        for ph_key, ph_items in (("early", early_items), ("mid", mid_items), ("late", late_items)):
            for it in ph_items:
                if isinstance(it, dict) and not it.get("custom_actions"):
                    it["custom_actions"] = build_skeleton_custom_actions(
                        it,
                        company=company,
                        job_title=job_title,
                        plan_month=1 if ph_key == "early" else (5 if ph_key == "mid" else 10),
                        phase_key=ph_key,
                    )

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
