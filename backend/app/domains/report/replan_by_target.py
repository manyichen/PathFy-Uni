"""分岗动态规划：按月写回 plans_by_target，与发展线菱形节点对齐。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from app.domains.report.constants import DIM_LABELS, METRIC_FAIL_HINTS, metric_label, sanitize_plan_item_user_text, sanitize_user_facing_text
from app.domains.report.growth import (
    _execution_hints_for_initial_item,
    _execution_hints_for_replan_action,
    timeline_progress_after_review,
)
from app.domains.report.plan_item_enrichment import (
    action_kind_label,
    enrich_plan_item,
)

_PHASE_LABELS = {"early": "前期", "mid": "中期", "late": "后期"}
_PHASE_TO_STAGE = {"early": "short_term", "mid": "mid_term", "late": "late"}


def phase_key_for_plan_month(plan_month: int) -> str:
    m = max(1, min(12, int(plan_month)))
    if m <= 3:
        return "early"
    if m <= 9:
        return "mid"
    return "late"


def find_plan_for_job_id(report_obj: Dict[str, Any], job_id: str) -> Optional[Dict[str, Any]]:
    jid = str(job_id or "").strip()
    if not jid:
        return None
    for p in report_obj.get("plans_by_target") or []:
        if isinstance(p, dict) and str(p.get("job_id") or "").strip() == jid:
            return p
    return None


def find_plan_for_line_id(report_obj: Dict[str, Any], line_id: str) -> Optional[Dict[str, Any]]:
    lid = str(line_id or "").strip()
    if not lid:
        return None
    dev = report_obj.get("development_lines") or {}
    for line in dev.get("lines") or []:
        if not isinstance(line, dict) or str(line.get("line_id") or "") != lid:
            continue
        return find_plan_for_job_id(report_obj, str(line.get("target_job_id") or ""))
    return None


def phase_items(plan: Dict[str, Any], phase_key: str) -> List[Dict[str, Any]]:
    phases = plan.get("phases") if isinstance(plan.get("phases"), dict) else {}
    block = phases.get(phase_key) if isinstance(phases.get(phase_key), dict) else {}
    raw = block.get("items") if isinstance(block.get("items"), list) else []
    return [x for x in raw if isinstance(x, dict)]


def pick_items_for_plan_month(
    plan: Dict[str, Any],
    plan_month: int,
    *,
    count: int = 2,
    rotate: bool = True,
) -> List[Dict[str, Any]]:
    """从对应阶段 items 中选取下月重点（按月份轮换）。"""
    pk = phase_key_for_plan_month(plan_month)
    items = phase_items(plan, pk)
    if not items:
        return []
    if not rotate or len(items) <= count:
        return items[:count]
    start = (max(0, plan_month - 1)) % len(items)
    picked: List[Dict[str, Any]] = []
    for i in range(min(count, len(items))):
        picked.append(copy.deepcopy(items[(start + i) % len(items)]))
    return picked


def item_label_for_adjustment(item: Dict[str, Any]) -> str:
    refs = item.get("learning_path_refs") or []
    if isinstance(refs, list) and refs and isinstance(refs[0], dict):
        lbl = str(refs[0].get("label") or "").strip()
        if lbl:
            return lbl[:200]
    actions = item.get("custom_actions") or []
    if isinstance(actions, list) and actions and isinstance(actions[0], dict):
        txt = str(actions[0].get("text") or "").strip()
        if txt:
            return txt[:200]
    lp = item.get("learning_path") or []
    if isinstance(lp, list) and lp:
        return str(lp[0]).strip()[:200]
    return str(item.get("milestone") or item.get("focus_label") or "下月任务")[:200]


def execution_hints_from_plan_item(
    item: Dict[str, Any],
    *,
    plan_month: int,
    phase_key: str,
    replan_mode: str,
) -> List[str]:
    lines = _execution_hints_for_initial_item(item) if replan_mode == "continue" else []
    growth_note = str(item.get("growth_rationale") or "").strip()
    if growth_note:
        lines.append(f"成长聚焦：{growth_note}")
    if not lines:
        ms = str(item.get("milestone") or "").strip()
        phase_label = _PHASE_LABELS.get(phase_key, phase_key)
        lines.append(
            f"第 {plan_month} 月（{phase_label}）：{ms or item.get('focus_label') or '按本岗计划推进'}"
        )
    for act in (item.get("custom_actions") or [])[:5]:
        if isinstance(act, dict) and act.get("text"):
            kind = action_kind_label(str(act.get("kind") or "practice"))
            lines.append(f"【{kind}】{act.get('text')}")
    refs = item.get("learning_path_refs") or []
    if isinstance(refs, list):
        for ref in refs[:2]:
            if not isinstance(ref, dict):
                continue
            label = str(ref.get("label") or "").strip()
            url = str(ref.get("url") or "").strip()
            if label:
                lines.append(f"图谱课程：{label}" + (f"（{url}）" if url else ""))
    cps = item.get("practice_plan_refs") or []
    if isinstance(cps, list):
        for ref in cps[:1]:
            if not isinstance(ref, dict):
                continue
            label = str(ref.get("label") or "").strip()
            url = str(ref.get("url") or "").strip()
            if label:
                lines.append(f"实践/竞赛：{label}" + (f"（{url}）" if url else ""))
    labels = item.get("metric_target_labels") or []
    if not labels:
        labels = [
            METRIC_FAIL_HINTS.get(str(c), "") or metric_label(str(c))
            for c in (item.get("metric_targets") or [])
            if str(c).strip()
        ]
    labels = [str(x) for x in labels if str(x).strip()][:4]
    if labels:
        lines.append(f"上月可加强：{'、'.join(labels)}")
    lines.append(
        f"阶段对齐：当前处于总体规划的「{_PHASE_LABELS.get(phase_key, phase_key)}」（第 {plan_month} 月）。"
    )
    if replan_mode == "strong":
        lines.append("本月评估未连续达标，已加强下月任务密度，请优先完成带图谱链接的事项。")
    elif replan_mode == "light":
        lines.append("本月部分指标未达标，下月任务已微调，请对照四项评估指标逐项落实。")
    else:
        lines.append("本月评估达标，下月按阶段计划继续推进即可。")
    return lines[:14]


def merge_llm_item_into_plan_item(base: Dict[str, Any], llm_item: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    ms = str(llm_item.get("milestone") or "").strip()
    if ms:
        out["milestone"] = ms[:200]
    actions: List[Dict[str, str]] = []
    for act in llm_item.get("custom_actions") or []:
        if not isinstance(act, dict):
            continue
        text = str(act.get("text") or "").strip()
        if not text:
            continue
        kind = str(act.get("kind") or "practice").strip().lower()
        if kind not in ("learn", "practice", "deliverable"):
            kind = "practice"
        actions.append({"kind": kind, "text": text[:150]})
    if actions:
        out["custom_actions"] = actions[:4]
    sanitize_plan_item_user_text(out)
    return out


def _item_pick_count(replan_mode: str) -> int:
    if replan_mode == "strong":
        return 2
    if replan_mode == "light":
        return 2
    if replan_mode == "continue":
        return 2
    return 2


def build_next_month_plan_for_job(
    plan: Dict[str, Any],
    *,
    plan_month: int,
    replan_mode: str,
    global_actions: List[str],
    llm_job_item: Optional[Dict[str, Any]] = None,
    failed_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    phase_key = phase_key_for_plan_month(plan_month)
    company = str(plan.get("company") or "")
    job_title = str(plan.get("job_title_name") or plan.get("display_title") or "")
    match_score = float(plan.get("match_score") or 0) or None
    picked = pick_items_for_plan_month(plan, plan_month, count=_item_pick_count(replan_mode))
    items_out: List[Dict[str, Any]] = []
    if picked:
        primary = picked[0]
        if llm_job_item and replan_mode in ("strong", "light"):
            primary = merge_llm_item_into_plan_item(primary, llm_job_item)
        elif replan_mode in ("strong", "light") and global_actions:
            primary = copy.deepcopy(primary)
            extra = [a for a in global_actions if a][:2]
            if extra:
                primary["custom_actions"] = [
                    {"kind": "practice", "text": t[:150]} for t in extra
                ] + (primary.get("custom_actions") or [])[:2]
        primary = enrich_plan_item(
            primary,
            plan_month=plan_month,
            phase_key=phase_key,
            replan_mode=replan_mode,
            company=company,
            job_title=job_title,
            match_score=match_score,
            failed_rows=failed_rows,
        )
        items_out.append(primary)
        for secondary in picked[1:]:
            items_out.append(
                enrich_plan_item(
                    copy.deepcopy(secondary),
                    plan_month=plan_month,
                    phase_key=phase_key,
                    replan_mode=replan_mode,
                    company=company,
                    job_title=job_title,
                    match_score=match_score,
                    failed_rows=None,
                )
            )
    elif global_actions:
        dim = "cap_req_growth"
        fallback = {
            "focus_dimension": dim,
            "focus_label": DIM_LABELS.get(dim, dim),
            "milestone": global_actions[0][:200],
            "custom_actions": [{"kind": "practice", "text": t[:150]} for t in global_actions[:3]],
            "learning_path_refs": [],
            "practice_plan_refs": [],
        }
        items_out.append(
            enrich_plan_item(
                fallback,
                plan_month=plan_month,
                phase_key=phase_key,
                replan_mode=replan_mode,
                company=company,
                job_title=job_title,
                match_score=match_score,
                failed_rows=failed_rows,
            )
        )
    return {
        "plan_month": plan_month,
        "phase_key": phase_key,
        "phase_label": _PHASE_LABELS.get(phase_key, phase_key),
        "replan_mode": replan_mode,
        "items": items_out,
    }


def resolve_replan_mode(
    *,
    all_passed: bool,
    failed_codes: List[str],
    consecutive_fail_months: int,
) -> str:
    if all_passed and not failed_codes:
        return "continue"
    if consecutive_fail_months >= 2:
        return "strong"
    return "light"


def apply_replan_after_review(
    report_obj: Dict[str, Any],
    adjust_detail: Dict[str, Any],
    *,
    stamp: str,
    review_anchor_month: float,
    replan_mode: str,
    metric_eval: Dict[str, Any],
) -> None:
    """写回 plans_by_target.next_month_plan，并刷新 development_lines.adjustments。"""
    if not adjust_detail.get("triggered"):
        return

    global_actions = [str(x).strip() for x in (adjust_detail.get("extra_actions") or []) if str(x).strip()]
    focus_dims = [str(x).strip() for x in (adjust_detail.get("focus_dimensions") or []) if str(x).strip()]
    focus_labels = [str(x).strip() for x in (adjust_detail.get("focus_labels") or []) if str(x).strip()]
    llm_by_job: Dict[str, Dict[str, Any]] = {}
    for block in adjust_detail.get("by_job") or []:
        if isinstance(block, dict):
            jid = str(block.get("job_id") or "").strip()
            if jid:
                llm_by_job[jid] = block

    eval_e = report_obj.get("evaluation") or {}
    lr = eval_e.get("latest_review") or {}
    submitted_adj = lr.get("submitted_metrics") or {}
    if not isinstance(submitted_adj, dict):
        submitted_adj = {}
    ev_lr = lr.get("evaluation") or {}
    pass_adj = float((ev_lr or {}).get("pass_rate") or 0.0)
    failed_rows = [r for r in (metric_eval.get("rows") or []) if isinstance(r, dict) and not r.get("passed")]

    am_int = int(min(12, max(0, int(round(float(review_anchor_month))))))
    plan_month = int(min(12, am_int + 1))

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
    existing_adjust_ids = {str(x.get("id") or "") for x in adjustments if isinstance(x, dict)}

    for li, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        line_id = str(line.get("line_id") or "").strip()
        job_id = str(line.get("target_job_id") or "").strip()
        if not line_id or not job_id:
            continue
        plan = find_plan_for_job_id(report_obj, job_id)
        if not plan:
            continue
        llm_job = llm_by_job.get(job_id) or {}
        llm_items = llm_job.get("items") if isinstance(llm_job.get("items"), list) else []
        llm_item = llm_items[0] if llm_items and isinstance(llm_items[0], dict) else None

        next_plan = build_next_month_plan_for_job(
            plan,
            plan_month=plan_month,
            replan_mode=replan_mode,
            global_actions=global_actions,
            llm_job_item=llm_item,
            failed_rows=failed_rows,
        )
        plan["next_month_plan"] = {**next_plan, "updated_at": stamp, "review_anchor_month": am_int}
        plan["current_plan_month"] = plan_month

        prev_progress = 0.0
        prev_month = 0.0
        for pt in line.get("timeline") or []:
            if not isinstance(pt, dict):
                continue
            pm = float(pt.get("month") or 0)
            if pm < float(am_int):
                prev_month = max(prev_month, pm)
                prev_progress = max(prev_progress, float(pt.get("progress") or 0))
        month_span = max(1.0, float(am_int) - prev_month)
        base_p = timeline_progress_after_review(
            submitted=submitted_adj,
            pass_rate=pass_adj,
            prev_progress=prev_progress,
            month_span=month_span,
        )
        phase_key = next_plan.get("phase_key") or phase_key_for_plan_month(plan_month)
        stage = _PHASE_TO_STAGE.get(str(phase_key), "short_term")
        items_out = [x for x in (next_plan.get("items") or []) if isinstance(x, dict)]
        if not items_out:
            continue

        merged_hints: List[str] = []
        label_parts: List[str] = []
        for item in items_out:
            label_parts.append(item_label_for_adjustment(item))
            merged_hints.extend(
                execution_hints_from_plan_item(
                    item,
                    plan_month=plan_month,
                    phase_key=str(phase_key),
                    replan_mode=replan_mode,
                )
            )
        seen_hint = set()
        hints_dedup: List[str] = []
        for h in merged_hints:
            if h in seen_hint:
                continue
            seen_hint.add(h)
            hints_dedup.append(h)
        combined_label = label_parts[0] if len(label_parts) == 1 else f"{label_parts[0]} 等{len(label_parts)}项"
        focus_labels = [str(x.get("focus_label") or "") for x in items_out if x.get("focus_label")]

        aid = f"adj_{stamp}_{line_id}"
        if aid in existing_adjust_ids:
            continue
        # 与当月复盘点共用横轴月份（anchor），纵轴与复盘进步度对齐
        adj_month = float(am_int)
        prog_marker = round(min(100.0, max(0.0, base_p)), 2)
        adjustments.append(
            {
                "id": aid,
                "line_id": line_id,
                "target_job_id": job_id,
                "stage": stage,
                "phase_key": phase_key,
                "label": combined_label[:200],
                "focus_label": focus_labels[0] if focus_labels else "能力补齐",
                "priority": 1,
                "created_at": stamp,
                "month": adj_month,
                "progress": prog_marker,
                "anchor_review_month": float(am_int),
                "plan_month": plan_month,
                "kind": "replan" if replan_mode != "continue" else "monthly_plan",
                "replan_mode": replan_mode,
                "execution_hints": hints_dedup[:16],
                "plan_items": [copy.deepcopy(x) for x in items_out],
                "failed_rows": failed_rows if replan_mode != "continue" else [],
            }
        )
        existing_adjust_ids.add(aid)


def ensure_next_month_plans_for_report(report_obj: Dict[str, Any], *, stamp: str) -> None:
    """为缺少下月计划的岗位写入第 1 月起步任务（不重复追加 adjustments）。"""
    for plan in report_obj.get("plans_by_target") or []:
        if not isinstance(plan, dict):
            continue
        nmp = plan.get("next_month_plan")
        if isinstance(nmp, dict) and (nmp.get("items") or []):
            continue
        items = pick_items_for_plan_month(plan, 1, count=2, rotate=False)
        if not items:
            continue
        plan["current_plan_month"] = 1
        merged_items = [
            enrich_plan_item(
                copy.deepcopy(x),
                plan_month=1,
                phase_key="early",
                replan_mode="initial",
                company=str(plan.get("company") or ""),
                job_title=str(plan.get("job_title_name") or plan.get("display_title") or ""),
                match_score=float(plan.get("match_score") or 0) or None,
            )
            for x in items[:2]
        ]
        plan["next_month_plan"] = {
            "plan_month": 1,
            "phase_key": "early",
            "phase_label": "前期",
            "replan_mode": "initial",
            "items": [copy.deepcopy(x) for x in merged_items],
            "updated_at": stamp,
            "review_anchor_month": 0,
        }


def seed_month_zero_from_plans(report_obj: Dict[str, Any], *, stamp: str) -> None:
    """第 0 月起步节点：每条发展线使用该岗 plans_by_target.early 的首项。"""
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
    existing_ids = {str(x.get("id") or "") for x in adjustments if isinstance(x, dict)}

    for li, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        line_id = str(line.get("line_id") or "").strip()
        job_id = str(line.get("target_job_id") or "").strip()
        if not line_id:
            continue
        plan = find_plan_for_job_id(report_obj, job_id) if job_id else None
        if not plan:
            continue
        items = pick_items_for_plan_month(plan, 1, count=2, rotate=False)
        if not items:
            continue
        plan["current_plan_month"] = 1
        merged_items = [
            enrich_plan_item(
                copy.deepcopy(x),
                plan_month=1,
                phase_key="early",
                replan_mode="initial",
                company=str(plan.get("company") or ""),
                job_title=str(plan.get("job_title_name") or plan.get("display_title") or ""),
                match_score=float(plan.get("match_score") or 0) or None,
            )
            for x in items[:2]
        ]
        plan["next_month_plan"] = {
            "plan_month": 1,
            "phase_key": "early",
            "phase_label": "前期",
            "replan_mode": "initial",
            "items": [copy.deepcopy(x) for x in merged_items],
            "updated_at": stamp,
            "review_anchor_month": 0,
        }
        merged_hints: List[str] = []
        label_parts: List[str] = []
        for item in merged_items:
            label_parts.append(item_label_for_adjustment(item))
            merged_hints.extend(
                execution_hints_from_plan_item(
                    item,
                    plan_month=1,
                    phase_key="early",
                    replan_mode="continue",
                )
            )
        seen_hint = set()
        hints_dedup: List[str] = []
        for h in merged_hints:
            if h in seen_hint:
                continue
            seen_hint.add(h)
            hints_dedup.append(h)
        combined_label = label_parts[0] if len(label_parts) == 1 else f"{label_parts[0]} 等{len(label_parts)}项"
        aid = f"adj_init0_{stamp}_{line_id}"
        if aid in existing_ids:
            continue
        existing_ids.add(aid)
        focus_labels = [str(x.get("focus_label") or "") for x in merged_items if x.get("focus_label")]
        adjustments.append(
            {
                "id": aid,
                "line_id": line_id,
                "target_job_id": job_id,
                "stage": "short_term",
                "phase_key": "early",
                "label": combined_label[:200],
                "focus_label": focus_labels[0] if focus_labels else "短期补齐",
                "priority": 1,
                "created_at": stamp,
                "month": 0.0,
                "progress": 0.0,
                "anchor_review_month": 0.0,
                "plan_month": 1,
                "kind": "initial_plan",
                "replan_mode": "initial",
                "execution_hints": hints_dedup[:16],
                "plan_items": merged_items,
            }
        )
