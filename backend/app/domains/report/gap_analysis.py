"""能力缺口：相对目标 JD + 复盘基线。"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import current_app

from app.domains.match.services import _coarse_morphology_match
from app.infrastructure.neo4j import DIM_KEYS


def parse_match_goal(value: Any) -> str:
    v = str(value or "").strip().lower()
    return "stretch" if v == "stretch" else "fit"


def resolve_soft_margin(match_goal: str) -> float:
    fit, stretch = 6.0, 10.0
    try:
        cfg = current_app.config
        fit = float(cfg.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
        stretch = float(cfg.get("MATCH_GAP_SOFT_MARGIN_STRETCH", 10.0))
    except RuntimeError:
        pass
    return stretch if match_goal == "stretch" else fit


def _shape_weight() -> float:
    try:
        return float(current_app.config.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    except RuntimeError:
        return 0.42


def build_match_preview(
    profile: Dict[str, Any],
    job_card: Dict[str, Any],
    *,
    match_goal: str = "fit",
) -> Dict[str, Any]:
    """相对本条目标 JD 生成 match_preview（不含同类岗位中位数）。"""
    goal = parse_match_goal(match_goal)
    margin = resolve_soft_margin(goal)
    shape_w = _shape_weight()

    student_scores = profile.get("scores") or {}
    student_conf = profile.get("confidences") or {}
    job_scores = job_card.get("scores") or {}
    job_conf = job_card.get("confidences") or {}

    ms, wg_job, gaps_job, shape_r = _coarse_morphology_match(
        student_scores,
        student_conf,
        job_scores,
        job_conf,
        soft_margin=margin,
        shape_weight=shape_w,
    )

    raw_delta: Dict[str, float] = {}
    surplus: Dict[str, float] = {}
    for dk in DIM_KEYS:
        s = float(student_scores.get(dk, 0.0))
        jv = float(job_scores.get(dk, 0.0))
        raw_delta[dk] = round(jv - s, 2)
        surplus[dk] = round(max(0.0, s - jv - margin), 2)

    return {
        "match_score": ms,
        "weighted_gap": wg_job,
        "shape_correlation": shape_r,
        "soft_margin": margin,
        "match_goal": goal,
        "dimension_gaps": gaps_job,
        "dimension_raw_delta": raw_delta,
        "dimension_surplus": surplus,
        "student_scores": {dk: round(float(student_scores.get(dk, 0.0)), 2) for dk in DIM_KEYS},
        "job_requirement_scores": {dk: round(float(job_scores.get(dk, 0.0)), 2) for dk in DIM_KEYS},
        "reference_note": (
            "各维度对比本条岗位要求；条形越长表示该能力越需优先补齐。"
        ),
    }


def build_gap_baseline(
    target_insights: List[Dict[str, Any]],
    *,
    primary_job_id: str,
    resume_id: int,
) -> Dict[str, Any]:
    primary = None
    for t in target_insights:
        if str(t.get("id") or "") == str(primary_job_id):
            primary = t
            break
    if primary is None and target_insights:
        primary = target_insights[0]
    mp = (primary or {}).get("match_preview") or {}
    by_job: Dict[str, Any] = {}
    for t in target_insights:
        jid = str(t.get("id") or "").strip()
        if not jid:
            continue
        p = t.get("match_preview") or {}
        by_job[jid] = {
            "match_score": p.get("match_score"),
            "weighted_gap": p.get("weighted_gap"),
            "dimension_gaps": p.get("dimension_gaps"),
        }
    return {
        "resume_id": resume_id,
        "primary_job_id": str((primary or {}).get("id") or primary_job_id),
        "match_goal": mp.get("match_goal") or "fit",
        "soft_margin": mp.get("soft_margin"),
        "match_score": mp.get("match_score"),
        "weighted_gap_job": mp.get("weighted_gap"),
        "dimension_gaps_job": mp.get("dimension_gaps") or {},
        "by_job_id": by_job,
    }


def _pct_reduction(baseline: float, current: float) -> float:
    b = max(0.0, float(baseline))
    c = max(0.0, float(current))
    if b <= 1e-6:
        return 100.0 if c <= 1e-6 else 0.0
    return round(max(0.0, min(100.0, (b - c) / b * 100.0)), 2)


def compute_review_gap_metrics(
    report_obj: Dict[str, Any],
    profile: Dict[str, Any],
    job_cards: List[Dict[str, Any]],
) -> Dict[str, float]:
    """用当前画像重算相对主目标 JD 的缺口，对比报告基线。"""
    eval_block = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
    baseline = eval_block.get("gap_baseline") if isinstance(eval_block.get("gap_baseline"), dict) else {}
    if not baseline:
        return {}

    goal = parse_match_goal(baseline.get("match_goal"))
    margin = float(baseline.get("soft_margin") or resolve_soft_margin(goal))
    shape_w = _shape_weight()
    student_scores = profile.get("scores") or {}
    student_conf = profile.get("confidences") or {}

    primary_id = str(baseline.get("primary_job_id") or "").strip()
    card = next((c for c in job_cards if str(c.get("id") or "") == primary_id), None)
    if not card and job_cards:
        card = job_cards[0]

    out: Dict[str, float] = {}
    if card:
        ms, wg_now, _, _ = _coarse_morphology_match(
            student_scores,
            student_conf,
            card.get("scores") or {},
            card.get("confidences") or {},
            soft_margin=margin,
            shape_weight=shape_w,
        )
        out["dim_gap_reduction"] = _pct_reduction(
            float(baseline.get("weighted_gap_job") or 0),
            float(wg_now),
        )
        out["match_score_change"] = round(
            float(ms) - float(baseline.get("match_score") or 0),
            2,
        )
    return out
