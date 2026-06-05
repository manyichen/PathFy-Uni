"""分岗计划条目：默认行动、成长性说明与未达标指标对齐。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.domains.report.constants import (
    DIM_LABELS,
    METRIC_FAIL_HINTS,
    MID_TERM_ACTIONS,
    SHORT_TERM_ACTIONS,
    metric_label,
    sanitize_plan_item_user_text,
    sanitize_user_facing_text,
)

_ACTION_KIND_LABELS = {"learn": "学习", "practice": "实践", "deliverable": "成果"}

# 四项月度评估指标 → 可执行补救动作
_METRIC_REMEDIATION: Dict[str, Dict[str, str]] = {
    "dim_gap_reduction": {
        "kind": "practice",
        "text": "对照报告缺口维度做1次前后自测（基线→本周），记录收敛幅度，目标≥10%",
    },
    "project_completion": {
        "kind": "practice",
        "text": "将本月计划拆成4个周任务并逐项勾选，未完成项写入下月第1周优先队列，目标完成率≥80%",
    },
    "match_score_change": {
        "kind": "deliverable",
        "text": "更新简历/项目描述中3条与目标岗JD对齐的表述，并估算匹配分变化，目标月增≥3分",
    },
    "delivery_output": {
        "kind": "deliverable",
        "text": "新增1项可验证成果（作品链接/证书/项目README），写清个人贡献与可展示材料",
    },
}


def action_kind_label(kind: str) -> str:
    return _ACTION_KIND_LABELS.get(str(kind or "").strip().lower(), "实践")


def build_skeleton_custom_actions(
    item: Dict[str, Any],
    *,
    company: str = "",
    job_title: str = "",
    plan_month: int = 1,
    phase_key: str = "early",
) -> List[Dict[str, str]]:
    """从图谱资源与阶段模板生成可执行行动（无 LLM 时的兜底）。"""
    actions: List[Dict[str, str]] = []
    seen: set[str] = set()
    dim = str(item.get("focus_dimension") or "")
    focus_label = str(item.get("focus_label") or DIM_LABELS.get(dim, dim))
    comp = (company or "目标公司").strip()
    title = (job_title or "目标岗位").strip()
    ctx = f"（对齐 {comp}·{title}）" if comp or title else ""

    def _add(kind: str, text: str) -> None:
        t = str(text or "").strip()
        if not t or t in seen:
            return
        seen.add(t)
        k = kind if kind in _ACTION_KIND_LABELS else "practice"
        actions.append({"kind": k, "text": t[:150]})

    for ref in item.get("learning_path_refs") or []:
        if not isinstance(ref, dict):
            continue
        label = str(ref.get("label") or "").strip()
        if label:
            _add(
                "learn",
                f"学习「{label}」：完成≥70%章节并写1页笔记（3个可面试复述要点）{ctx}",
            )
        if len(actions) >= 2:
            break

    for ref in item.get("practice_plan_refs") or []:
        if not isinstance(ref, dict):
            continue
        label = str(ref.get("label") or "").strip()
        if label:
            _add("practice", f"筹备/参与「{label}」：提交报名或组队计划，并记录时间节点{ctx}")
        break

    generic_map = SHORT_TERM_ACTIONS if phase_key == "early" else MID_TERM_ACTIONS
    for g in generic_map.get(dim, [])[:2]:
        _add("practice" if "项目" in g or "实战" in g else "learn", f"{g}{ctx}")

    for lp in (item.get("learning_path") or [])[:2]:
        if isinstance(lp, str) and lp.strip():
            _add("learn", f"{lp.strip()}{ctx}")

    for pp in (item.get("practice_plan") or [])[:1]:
        if isinstance(pp, str) and pp.strip():
            _add("practice", f"{pp.strip()}{ctx}")

    _add(
        "deliverable",
        f"第{plan_month}月成果：围绕「{focus_label}」产出1个可展示交付物（代码/作品/报告+截图）",
    )
    return actions[:5]


def remediation_actions_for_failed_rows(
    failed_rows: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen_codes: set[str] = set()
    for row in failed_rows or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        tmpl = _METRIC_REMEDIATION.get(code)
        if tmpl:
            out.append({"kind": tmpl["kind"], "text": tmpl["text"]})
    return out[:4]


def build_growth_rationale(
    item: Dict[str, Any],
    *,
    plan_month: int,
    phase_key: str,
    replan_mode: str,
    match_score: Optional[float] = None,
    failed_rows: Optional[List[Dict[str, Any]]] = None,
) -> str:
    _ = match_score
    focus = str(item.get("focus_label") or "核心能力")
    phase_cn = {"early": "前期", "mid": "中期", "late": "后期"}.get(phase_key, phase_key)
    fail_hints = []
    for r in failed_rows or []:
        if not isinstance(r, dict) or r.get("passed"):
            continue
        code = str(r.get("code") or "").strip()
        hint = METRIC_FAIL_HINTS.get(code) or metric_label(code) or str(r.get("label") or "").strip()
        if hint and hint not in fail_hints:
            fail_hints.append(hint)
    if fail_hints:
        fail_part = (
            f"上月在「{'、'.join(fail_hints[:3])}」还有提升空间，"
            f"本月把「{focus}」相关动作做到位，复盘时更容易看见进步。"
        )
    else:
        fail_part = f"本月围绕「{focus}」推进，建议做完一条勾一条，月末一起复盘。"
    mode_part = {
        "strong": "连续两个月未完全达标，本月任务会稍密集，按周拆分更容易坚持。",
        "light": "上月部分目标未达成，本月计划已针对性补强。",
        "continue": "上月表现不错，按总体规划继续推进即可。",
        "initial": "先从第一项开始，养成固定学习节奏。",
    }.get(replan_mode, "")
    text = f"第 {plan_month} 月 · {phase_cn}阶段。{fail_part}{mode_part}"
    return sanitize_user_facing_text(text)[:420]


def enrich_plan_item(
    item: Dict[str, Any],
    *,
    plan_month: int,
    phase_key: str,
    replan_mode: str,
    company: str = "",
    job_title: str = "",
    match_score: Optional[float] = None,
    failed_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """合并已有 custom_actions、骨架行动与指标补救，并写入成长性说明。"""
    import copy

    out = copy.deepcopy(item)
    existing = [
        a
        for a in (out.get("custom_actions") or [])
        if isinstance(a, dict) and str(a.get("text") or "").strip()
    ]
    skeleton = build_skeleton_custom_actions(
        out,
        company=company,
        job_title=job_title,
        plan_month=plan_month,
        phase_key=phase_key,
    )
    remedial = remediation_actions_for_failed_rows(failed_rows) if replan_mode != "continue" else []

    merged: List[Dict[str, str]] = []
    seen: set[str] = set()

    def _push(act: Dict[str, str]) -> None:
        text = str(act.get("text") or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        kind = str(act.get("kind") or "practice").strip().lower()
        if kind not in _ACTION_KIND_LABELS:
            kind = "practice"
        merged.append({"kind": kind, "text": sanitize_user_facing_text(text)[:150]})

    for act in existing + remedial + skeleton:
        if isinstance(act, dict):
            _push(act)

    min_actions = 4 if replan_mode == "strong" else 3
    if len(merged) < min_actions:
        for act in skeleton:
            _push(act)
            if len(merged) >= min_actions:
                break

    out["custom_actions"] = merged[:5]
    out["growth_rationale"] = build_growth_rationale(
        out,
        plan_month=plan_month,
        phase_key=phase_key,
        replan_mode=replan_mode,
        match_score=match_score,
        failed_rows=failed_rows,
    )
    if failed_rows and replan_mode != "continue":
        labels = [
            str(r.get("label") or metric_label(str(r.get("code") or "")) or "").strip()
            for r in failed_rows
            if isinstance(r, dict) and not r.get("passed")
        ]
        out["metric_target_labels"] = [x for x in labels if x][:4]
    sanitize_plan_item_user_text(out)
    return out
