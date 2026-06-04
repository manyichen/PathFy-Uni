"""成长计划与发展线。"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from app.domains.report.constants import (
    DIM_LABELS,
    MID_TERM_ACTIONS,
    SHORT_TERM_ACTIONS,
    TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH,
)

def _top_gap_dimensions(gaps: Dict[str, float], top_n: int = 3) -> List[str]:
    ordered = sorted(
        [(k, float(v or 0)) for k, v in (gaps or {}).items() if k in DIM_LABELS],
        key=lambda x: x[1],
        reverse=True,
    )
    return [k for k, v in ordered if v > 0][:top_n]


def _build_growth_plan(
    target_insights: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    top_gap_counter: Dict[str, int] = defaultdict(int)
    for insight in target_insights:
        for dim in _top_gap_dimensions((insight.get("match_preview") or {}).get("dimension_gaps") or {}):
            top_gap_counter[dim] += 1
    if not top_gap_counter:
        top_gap_dims = ["cap_req_growth", "cap_req_practice", "cap_req_teamwork"]
    else:
        top_gap_dims = sorted(top_gap_counter.keys(), key=lambda x: top_gap_counter[x], reverse=True)[:3]

    short_term: List[Dict[str, Any]] = []
    mid_term: List[Dict[str, Any]] = []
    for idx, dim in enumerate(top_gap_dims):
        short_term.append(
            {
                "phase": "short_term",
                "order": idx + 1,
                "focus_dimension": dim,
                "focus_label": DIM_LABELS.get(dim, dim),
                "period": "0-3个月",
                "learning_path": SHORT_TERM_ACTIONS.get(dim, [])[:2],
                "practice_plan": SHORT_TERM_ACTIONS.get(dim, [])[1:2] or [],
                "milestone": f"{DIM_LABELS.get(dim, dim)}完成基础补齐并有可展示产出",
            }
        )
        mid_term.append(
            {
                "phase": "mid_term",
                "order": idx + 1,
                "focus_dimension": dim,
                "focus_label": DIM_LABELS.get(dim, dim),
                "period": "3-12个月",
                "learning_path": MID_TERM_ACTIONS.get(dim, [])[:2],
                "practice_plan": MID_TERM_ACTIONS.get(dim, [])[1:2] or [],
                "milestone": f"{DIM_LABELS.get(dim, dim)}达到目标岗位可投递水平",
            }
        )

    metrics = [
        {"code": "dim_gap_reduction", "label": "关键能力缺口收敛率", "cycle": "月度", "target": ">=10%"},
        {"code": "project_completion", "label": "项目/实践任务完成率", "cycle": "月度", "target": ">=80%"},
        {"code": "match_score_change", "label": "目标岗位匹配度变化", "cycle": "月度", "target": "月增>=3分"},
        {"code": "delivery_output", "label": "可展示成果数量", "cycle": "月度", "target": "每月>=1项"},
    ]
    return short_term, mid_term, metrics


def _review_point_progress(
    submitted: Dict[str, Any],
    pass_rate: float,
    line_idx: int,
    target: Dict[str, Any],
) -> float:
    """单次复盘在曲线上的进步度（0–100），各岗位线略错开。"""
    ms_t = float(((target or {}).get("match_preview") or {}).get("match_score") or 0)
    dg = float((submitted or {}).get("dim_gap_reduction") or 0)
    pc = float((submitted or {}).get("project_completion") or 0)
    msc = float((submitted or {}).get("match_score_change") or 0)
    dl = float((submitted or {}).get("delivery_output") or 0)
    msc_c = max(-6.0, min(10.0, msc))
    evidence = min(
        100.0,
        max(10.0, 0.26 * dg + 0.36 * pc + 3.2 * msc_c + 8.5 * min(dl, 5.0)),
    )
    pr = max(0.0, min(1.0, float(pass_rate or 0.0)))
    blended = pr * 100.0 * 0.5 + evidence * 0.5
    blended += (line_idx * 1.25) + (ms_t - 55.0) * 0.08
    return max(7.0, min(100.0, blended))


def _execution_hints_for_replan_action(action: str) -> List[str]:
    a = str(action or "").strip()
    if not a:
        return []
    return [
        f"下一执行月优先事项：{a}",
        "拆解落地：把上面这一条拆成 2–4 个可勾选子任务，按周排进日程；每条任务写清「产出物」与「截止时间」。",
        "与评估对齐：对照本月四项量化指标（缺口收敛、项目完成、匹配变化、成果），复盘时逐条打勾并估算完成度。",
    ]


def _execution_hints_for_initial_item(item: Dict[str, Any]) -> List[str]:
    ms = str(item.get("milestone") or "").strip()
    lp = item.get("learning_path") or []
    pp = item.get("practice_plan") or []
    lp_refs = item.get("learning_path_refs") or []
    pp_refs = item.get("practice_plan_refs") or []
    lines: List[str] = []
    if ms:
        lines.append(f"从第 1 个月起优先推进：{ms}")
    if isinstance(lp_refs, list) and lp_refs:
        for ref in lp_refs[:2]:
            if not isinstance(ref, dict):
                continue
            label = str(ref.get("label") or "").strip()
            url = str(ref.get("url") or "").strip()
            if label:
                lines.append(f"图谱课程：{label}" + (f"（{url}）" if url else ""))
    elif isinstance(lp, list) and lp:
        chunk = "；".join(str(x).strip() for x in lp[:4] if str(x).strip())
        if chunk:
            lines.append(f"学习侧：{chunk}")
    if isinstance(pp_refs, list) and pp_refs:
        for ref in pp_refs[:1]:
            if not isinstance(ref, dict):
                continue
            label = str(ref.get("label") or "").strip()
            url = str(ref.get("url") or "").strip()
            if label:
                lines.append(f"图谱竞赛：{label}" + (f"（{url}）" if url else ""))
    elif isinstance(pp, list) and pp:
        chunk2 = "；".join(str(x).strip() for x in pp[:3] if str(x).strip())
        if chunk2:
            lines.append(f"实践侧：{chunk2}")
    lines.append(
        "节奏说明：第 0 月在画布上固定本方向起点；进入第 1 月提交复盘后，系统会把量化结果写回曲线并刷新下一月安排。"
    )
    return lines


def _seed_month_zero_adjustments(report_obj: Dict[str, Any], *, stamp: str) -> None:
    """报告刚生成时，为每条发展线写入第 0 月可见的「起步执行」菱形节点。"""
    dev_lines = report_obj.get("development_lines")
    if not isinstance(dev_lines, dict):
        return
    lines = dev_lines.get("lines")
    if not isinstance(lines, list):
        return
    adjustments = dev_lines.get("adjustments")
    if not isinstance(adjustments, list):
        adjustments = []
        dev_lines["adjustments"] = adjustments
    growth = report_obj.get("growth_plan") or {}
    short_term = growth.get("short_term") if isinstance(growth.get("short_term"), list) else []
    items = [x for x in short_term if isinstance(x, dict)][:3]
    if not items:
        return
    existing_ids = {str(x.get("id") or "") for x in adjustments if isinstance(x, dict)}
    for li, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        line_id = str(line.get("line_id") or "").strip()
        if not line_id:
            continue
        for ai, item in enumerate(items):
            milestone = str(item.get("milestone") or "").strip()
            focus_label = str(item.get("focus_label") or "短期补齐").strip()
            refs = item.get("learning_path_refs") or []
            lp0 = ""
            if isinstance(refs, list) and refs and isinstance(refs[0], dict):
                lp0 = str(refs[0].get("label") or "").strip()
            if not lp0:
                learning = item.get("learning_path") or []
                lp0 = str(learning[0]).strip() if isinstance(learning, list) and learning else ""
            label_text = (lp0 or milestone or focus_label)[:200]
            aid = f"adj_init0_{stamp}_{line_id}_{ai + 1}"
            if aid in existing_ids:
                continue
            existing_ids.add(aid)
            hints = _execution_hints_for_initial_item(item)
            adjustments.append(
                {
                    "id": aid,
                    "line_id": line_id,
                    "stage": "short_term",
                    "label": label_text,
                    "focus_label": focus_label,
                    "priority": ai + 1,
                    "created_at": stamp,
                    "month": round(0.0 + float(ai) * 0.07 + float(li) * 0.02, 2),
                    "progress": round(2.5 + float(ai) * 2.2 + float(li) * 0.5, 2),
                    "anchor_review_month": 0.0,
                    "plan_month": 1,
                    "kind": "initial_plan",
                    "execution_hints": hints,
                }
            )


def _build_development_lines(
    student_name: str,
    target_insights: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stage_labels = {
        "current": f"{student_name} 当前画像",
        "short_term": "短期能力补齐",
        "mid_term": "中期岗位化实践",
        "target": "目标岗位就绪",
    }
    lines: List[Dict[str, Any]] = []
    for idx, target in enumerate(target_insights):
        line_name = str(target.get("display_title") or target.get("title") or f"目标职业{idx + 1}")
        tid = str(target.get("id") or "").strip()
        nodes: List[Dict[str, Any]] = []
        for stage in ("current", "short_term", "mid_term", "target"):
            sid = f"{stage}_{idx + 1}"
            label = stage_labels[stage] if stage != "target" else line_name
            nodes.append({"id": sid, "label": label, "stage": stage})
        # 未提交动态复盘前不画进步曲线：仅保留时间轴起点 (0,0)
        timeline: List[Dict[str, Any]] = [
            {"month": 0.0, "progress": 0.0, "label": "起点", "kind": "origin"},
        ]
        lines.append(
            {
                "line_id": f"line_{idx + 1}",
                "line_name": line_name,
                "target_job_id": tid,
                "overlay_group": "shared" if idx < 2 else f"custom_{idx + 1}",
                "nodes": nodes,
                "timeline": timeline,
            }
        )
    return {
        "display_mode": "single",
        "axis": {
            "x_unit": "month",
            "x_min": 0.0,
            "x_max": 12.0,
            "x_label": "时间（月）",
            "y_min": 0.0,
            "y_max": 100.0,
            "y_label": "进步度",
        },
        "lines": lines,
        "adjustments": [],
    }


def _rebuild_development_timelines(report_obj: Dict[str, Any], reviews_asc: List[Dict[str, Any]]) -> None:
    """时间线从 (0,0) 起点开始；仅在有复盘记录后追加折线段，时间逐步向右。"""
    dev = report_obj.get("development_lines")
    if not isinstance(dev, dict):
        return
    lines = dev.get("lines")
    targets = report_obj.get("targets") or []
    if not isinstance(lines, list):
        return
    tgt_by_id = {str(t.get("id")): t for t in targets if isinstance(t, dict)}

    for idx, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        tid = str(line.get("target_job_id") or "")
        target = tgt_by_id.get(tid) or {}
        pts: List[Dict[str, Any]] = [
            {"month": 0.0, "progress": 0.0, "label": "起点", "kind": "origin"},
        ]
        prev_month = 0.0
        prev_progress = 0.0
        for i, rev in enumerate(reviews_asc):
            met = rev.get("metrics") or {}
            if not isinstance(met, dict):
                met = {}
            submitted = met.get("submitted") or {}
            if not isinstance(submitted, dict):
                submitted = {}
            ev = met.get("evaluation") or {}
            if not isinstance(ev, dict):
                ev = {}
            pr = float(ev.get("pass_rate") or 0.0)
            rid = int(rev.get("review_id") or 0)
            # 横轴按自然月：第 1 次复盘在第 1 月，第 2 次在第 2 月…（上限 12）
            month = float(min(12, i + 1))
            raw_prog = _review_point_progress(submitted, pr, idx, target)
            month_span = max(0.0, month - prev_month)
            ceiling = prev_progress + TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH * month_span
            prog = min(raw_prog, ceiling)
            prog = max(0.0, min(100.0, prog))
            llm_ex = met.get("llm_extract") or {}
            if not isinstance(llm_ex, dict):
                llm_ex = {}
            detail: Dict[str, Any] = {
                "review_text": str(met.get("review_text") or "")[:4000],
                "submitted": submitted,
                "llm_summary": str(llm_ex.get("summary") or "")[:800],
                "pass_rate": round(pr, 4),
                "all_passed": bool(ev.get("all_passed")),
            }
            pts.append(
                {
                    "month": month,
                    "progress": round(prog, 2),
                    "label": f"第{int(month)}月",
                    "kind": "review",
                    "review_id": rid,
                    "detail": detail,
                }
            )
            prev_month, prev_progress = month, prog
        pts.sort(key=lambda x: float(x.get("month") or 0.0))
        line["timeline"] = pts

    if "axis" not in dev or not isinstance(dev.get("axis"), dict):
        dev["axis"] = {
            "x_unit": "month",
            "x_min": 0.0,
            "x_max": 12.0,
            "x_label": "时间（月）",
            "y_min": 0.0,
            "y_max": 100.0,
            "y_label": "进步度",
        }
    dev["display_mode"] = "single"


