"""生涯报告业务编排。"""
from __future__ import annotations

import copy
import hashlib
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

from flask import current_app
from app.domains.settings.service import effective_preferences, setting

from app.domains.match.services import (
    _fetch_jobs_for_match,
    _resolve_student_profile,
)
from app.domains.match.snapshots import extract_targets_from_match_run
from app.domains.jobs.workstyle import WORKSTYLE_SNAPSHOT_VERSION
from app.domains.match.preference_fit import PREFERENCE_FIT_ALGORITHM_VERSION
from app.domains.personality.preference_profile import resolve_preference_profile
from app.domains.report.export import ReportExportValidationError, build_report_export_html, render_pdf_with_playwright
from app.domains.report.decision_support import attach_decision_support
from app.domains.report.enrichment_quality import (
    create_evidence_packet,
    create_input_snapshot,
    ensure_input_snapshot,
    gate_enrichment,
    profile_from_snapshot,
)
from app.domains.report.gap_analysis import (
    build_gap_baseline,
    build_match_preview,
    compute_review_gap_metrics,
    parse_match_goal,
)
from app.domains.report.growth import (
    _build_development_lines,
    _build_growth_plan,
    _rebuild_development_timelines,
    _seed_month_zero_adjustments,
)
from app.domains.report.llm import (
    _build_llm_summary,
    augment_plans_narrative_with_doubao,
    build_grounded_report_narratives,
)
from app.domains.report.plan_action_progress import (
    PlanActionProgressError,
    apply_plan_action_done,
    build_stable_action_ref,
    ensure_action_ids,
    find_plan_action,
    locate_plan_action,
    new_user_action_uid,
    summarize_plan_action_completion,
    sync_action_progress_to_plans,
)
from app.domains.report.longitudinal import build_longitudinal_insights
from app.domains.report.plan_customization import build_custom_plan_actions_batch
from app.domains.report.preference_strategy import (
    apply_strategy_decision,
    behavioral_evidence_rows,
    build_preference_strategy,
    sanitize_preference_signals,
    update_calibration,
)
from app.domains.report.plans_by_target import bind_plan_line_ids, build_plans_by_target
from app.domains.report.recommendations import (
    build_graph_recommendations,
    enrich_growth_plan_with_recommendations,
)
from app.domains.report.sanitize import sanitize_review_text_fields
from app.infrastructure.privacy import storage_safe_text
from app.domains.report.repository import (
    _parse_json_field,
    _query_all_jobs_browse_lite,
    _query_job_relations,
    _query_jobs_by_ids,
    count_reviews,
    commit_action_done_patch,
    commit_action_progress_update,
    commit_confirmed_review,
    commit_plan_proposal_decision,
    commit_review_update,
    fetch_plan_version,
    fetch_review_draft,
    fetch_report_for_export,
    fetch_report_privacy_bundle,
    fetch_report_row,
    fetch_longitudinal_rows,
    insert_report,
    insert_review_draft,
    list_plan_version_rows,
    list_evidence_records,
    list_review_metrics_asc,
    list_review_rows,
    fetch_report_json_by_ids,
    list_targets_for_reports,
    merge_report_enrichment,
    list_user_reports,
    delete_user_report,
    ensure_report_experiment_assignment,
    get_report_experiment_assignment,
    purge_expired_review_drafts,
    report_operations_metrics,
    report_owned_by_user,
    commit_preference_strategy_update,
    update_report_json_if_version,
)
from app.domains.report.replan_by_target import ensure_next_month_plans_for_report, resolve_replan_mode
from app.domains.report.review import (
    _apply_auto_adjustment_to_report,
    _build_auto_adjustment,
    _evaluate_review_metrics,
    _llm_extract_metrics_from_text,
)
from app.domains.report.review_workflow import (
    apply_change_overrides,
    apply_plan_changes,
    build_metric_candidates,
    build_plan_diff,
    classify_review_status,
    confirmed_metrics_from_decisions,
    normalize_review_cycle,
    utc_stamp,
)
from app.domains.report.trends import attach_track_profiles_to_insights
from app.domains.report.external_public_info import fetch_public_info_for_job_title
from app.domains.report.graph_repository import resolve_job_title_names
from app.domains.report.utils import clamp_int, truthy
from app.infrastructure.neo4j import serialize_job_row


class ReportServiceError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _parse_resume_id(body: Dict[str, Any]) -> int:
    try:
        return int(body.get("resume_id"))
    except (TypeError, ValueError) as exc:
        raise ReportServiceError("resume_id 无效", 400) from exc


def _parse_report_id(body: Dict[str, Any]) -> int:
    try:
        return int(body.get("report_id"))
    except (TypeError, ValueError) as exc:
        raise ReportServiceError("report_id 无效", 400) from exc


def _load_profile(resume_id: int, user_id: int) -> Dict[str, Any]:
    profile, err = _resolve_student_profile({"resume_id": resume_id}, user_id)
    if err or not profile:
        raise ReportServiceError(err or "画像读取失败", 400)
    return profile


def build_target_insights(
    profile: Dict[str, Any],
    target_job_ids: List[str],
    *,
    match_goal: str = "fit",
) -> List[Dict[str, Any]]:
    goal = parse_match_goal(match_goal)
    target_cards = _query_jobs_by_ids(target_job_ids)
    found_ids = {str(x.get("id")) for x in target_cards}
    missing = [jid for jid in target_job_ids if jid not in found_ids]
    if missing:
        raise ReportServiceError(f"存在无效 job_id: {', '.join(missing[:3])}", 400)

    insights: List[Dict[str, Any]] = []
    for card in target_cards:
        insights.append(
            {
                **card,
                "display_title": (
                    f"{str(card.get('title') or '目标岗位')} · {str(card.get('company') or '未知公司')}"
                ),
                "match_preview": build_match_preview(
                    profile,
                    card,
                    match_goal=goal,
                ),
            }
        )
    attach_track_profiles_to_insights(insights)
    return insights


def _parse_run_id(body: Dict[str, Any]) -> int:
    try:
        return int(body.get("run_id"))
    except (TypeError, ValueError) as exc:
        raise ReportServiceError("run_id 无效", 400) from exc


def import_targets_from_match(user_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    run_id = _parse_run_id(body)
    limit = clamp_int(body.get("limit"), 1, 5, 5)

    payload = extract_targets_from_match_run(user_id=user_id, run_id=run_id, limit=limit)
    if not payload:
        raise ReportServiceError("匹配记录不存在或无权访问", 404)

    resume_id = int(payload.get("resume_id") or 0)
    if not resume_id:
        raise ReportServiceError("匹配记录缺少画像信息", 400)

    profile, err = _resolve_student_profile({"resume_id": resume_id}, user_id)
    if err or not profile:
        raise ReportServiceError(err or "匹配记录关联的画像不可用", 400)

    targets = payload.get("targets") or []
    if not targets:
        raise ReportServiceError("该匹配记录无可用 Top5 数据，请先在「人岗匹配」完成一次匹配", 400)

    return {
        "run_id": run_id,
        "resume_id": resume_id,
        "match_goal": payload.get("match_goal") or "fit",
        "source": payload.get("source") or "match_snapshot",
        "targets": targets,
    }


def manual_search_targets(body: Dict[str, Any]) -> Dict[str, Any]:
    q = str(body.get("q") or "").strip()
    if not q:
        raise ReportServiceError("请提供岗位关键词", 400)
    location_q = str(body.get("location_q") or "").strip()
    limit = clamp_int(body.get("limit"), 1, 30, 20)
    rows = _fetch_jobs_for_match(q=q, location_q=location_q, cap=max(limit, 60))
    cards = [serialize_job_row(r) for r in rows][:limit]
    targets = [
        {
            "job_id": c.get("id"),
            "title": c.get("title"),
            "company": c.get("company"),
            "location": c.get("location"),
            "salary": c.get("salary"),
            "score_avg": c.get("score_avg"),
            "scores": c.get("scores"),
            "source": "manual_search",
        }
        for c in cards
    ]
    return {"targets": targets, "count": len(targets)}


def get_track_public_info(body: Dict[str, Any]) -> Dict[str, Any]:
    """按需获取岗位外部公开信息（JobTitle 级缓存）。"""
    job_title = str(body.get("job_title") or "").strip()
    job_id = str(body.get("job_id") or "").strip()
    if not job_title and job_id:
        mapped = resolve_job_title_names([job_id])
        job_title = mapped.get(job_id) or ""
    if not job_title:
        raise ReportServiceError("请提供 job_title 或 job_id", 400)
    force = truthy(body.get("force_refresh"))
    result = fetch_public_info_for_job_title(job_title, force_refresh=force)
    if not result.get("ok"):
        raise ReportServiceError(str(result.get("message") or "获取失败"), 502)
    return result


_BROWSE_SHUFFLE_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_BROWSE_CACHE_ORDER: List[str] = []
_MAX_BROWSE_CACHES = 32


def _browse_shuffle_key(job_id: str, seed: str) -> str:
    raw = f"{seed}:{job_id}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _shuffled_browse_rows(seed: str) -> List[Dict[str, Any]]:
    cached = _BROWSE_SHUFFLE_CACHE.get(seed)
    if cached is not None:
        return cached
    rows = _query_all_jobs_browse_lite()
    rows.sort(key=lambda row: _browse_shuffle_key(str(row.get("id") or ""), seed))
    _BROWSE_SHUFFLE_CACHE[seed] = rows
    _BROWSE_CACHE_ORDER.append(seed)
    while len(_BROWSE_CACHE_ORDER) > _MAX_BROWSE_CACHES:
        old_seed = _BROWSE_CACHE_ORDER.pop(0)
        _BROWSE_SHUFFLE_CACHE.pop(old_seed, None)
    return rows


def random_browse_targets(seed: str, page: int, page_size: int) -> Dict[str, Any]:
    seed_text = str(seed or "").strip()
    if not seed_text:
        raise ReportServiceError("seed 无效", 400)
    page_num = max(1, int(page))
    size = clamp_int(page_size, 1, 50, 20)
    rows = _shuffled_browse_rows(seed_text)
    total = len(rows)
    total_pages = max(1, (total + size - 1) // size) if total else 1
    page_num = min(page_num, total_pages)
    start = (page_num - 1) * size
    page_rows = rows[start : start + size]
    targets = [
        {
            "job_id": row.get("id"),
            "title": row.get("title"),
            "company": row.get("company"),
            "location": row.get("location"),
            "salary": row.get("salary"),
            "source": "random_browse",
        }
        for row in page_rows
    ]
    return {
        "seed": seed_text,
        "targets": targets,
        "count": len(targets),
        "total": total,
        "page": page_num,
        "page_size": size,
        "total_pages": total_pages,
    }


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 1)


def generate_career_report(user_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    resume_id = _parse_resume_id(body)
    profile = _load_profile(resume_id, user_id)
    raw_ids = body.get("target_job_ids")
    if not isinstance(raw_ids, list):
        raise ReportServiceError("target_job_ids 必须为数组", 400)
    target_job_ids = [str(x).strip() for x in raw_ids if str(x).strip()]
    target_job_ids = list(dict.fromkeys(target_job_ids))
    if not target_job_ids:
        raise ReportServiceError("请至少选择 1 个目标职业", 400)
    if len(target_job_ids) > 5:
        raise ReportServiceError("最多选择 5 个目标职业", 400)

    skip_llm_enrich = truthy(body.get("skip_llm_enrich"))
    match_goal = parse_match_goal(body.get("match_goal"))
    primary_job_id = str(body.get("primary_job_id") or target_job_ids[0]).strip()
    if primary_job_id not in target_job_ids:
        raise ReportServiceError("primary_job_id 必须属于 target_job_ids", 400)

    use_personality = bool(body.get("_use_personality_in_report", False)) and bool(
        setting("CAREER_ENABLE_PERSONALITY_STRATEGY", True)
    )
    requested_personality_id = None
    try:
        if body.get("personality_profile_id") is not None:
            requested_personality_id = int(body.get("personality_profile_id"))
    except (TypeError, ValueError) as exc:
        raise ReportServiceError("personality_profile_id 无效", 400) from exc
    resolved_preference = (
        resolve_preference_profile(user_id, profile_id=requested_personality_id, require_personalization_enabled=True)
        if use_personality else {"status": "disabled", "snapshot": None}
    )
    if requested_personality_id is not None and resolved_preference.get("status") == "missing":
        raise ReportServiceError("人格偏好画像不存在或无权使用", 403)
    preference_snapshot = resolved_preference.get("snapshot") if resolved_preference.get("status") == "measured" else None

    timing_ms: Dict[str, float] = {}
    t_all = time.perf_counter()

    t = time.perf_counter()
    target_insights = build_target_insights(profile, target_job_ids, match_goal=match_goal)
    timing_ms["insights"] = _elapsed_ms(t)

    t = time.perf_counter()
    relations = _query_job_relations(target_job_ids)
    timing_ms["relations"] = _elapsed_ms(t)

    t = time.perf_counter()
    recommendations = build_graph_recommendations(
        target_insights,
        use_llm_curator=False,
    )
    timing_ms["recommendations"] = _elapsed_ms(t)

    t = time.perf_counter()
    short_term, mid_term, metrics = _build_growth_plan(target_insights)
    enrich_growth_plan_with_recommendations(short_term, mid_term, recommendations)
    lines = _build_development_lines(str(profile.get("display_name") or "候选人"), target_insights)
    plans_by_target = build_plans_by_target(target_insights, recommendations)
    bind_plan_line_ids(plans_by_target, lines)
    timing_ms["plans"] = _elapsed_ms(t)

    plan_custom_meta: Dict[str, Any] = {"ok": False, "reason": "skipped"}
    per_target_narrative_meta: Dict[str, Any] = {"ok": False, "reason": "skipped"}
    llm_summary: Dict[str, Any] = {"provider": "skipped", "text": ""}
    if not skip_llm_enrich:
        t = time.perf_counter()
        plan_custom_meta = build_custom_plan_actions_batch(
            plans_by_target, target_insights, use_llm=True
        )
        timing_ms["plan_customization"] = _elapsed_ms(t)
        ensure_next_month_plans_for_report(
            {"plans_by_target": plans_by_target}, stamp=datetime.utcnow().strftime("%Y%m%d%H%M%S")
        )
        ensure_action_ids({"plans_by_target": plans_by_target})
        t = time.perf_counter()
        _, per_target_narrative_meta = build_grounded_report_narratives(
            plans_by_target, target_insights
        )
        llm_summary = _build_llm_summary(
            profile=profile, target_insights=target_insights, short_term=short_term,
            mid_term=mid_term, recommendations=recommendations,
        )
        timing_ms["grounded_narrative"] = _elapsed_ms(t)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    stamp_compact = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    gap_baseline = build_gap_baseline(
        target_insights,
        primary_job_id=primary_job_id,
        resume_id=resume_id,
    )
    gap_baseline["captured_at"] = now
    timing_ms["total"] = _elapsed_ms(t_all)

    report_obj = {
        "generated_at": now,
        "match_goal": match_goal,
        "student": {
            "id": profile.get("id"),
            "display_name": profile.get("display_name"),
            "scores": profile.get("scores"),
            "confidences": profile.get("confidences"),
            "score_avg": profile.get("score_avg"),
            "education": profile.get("education"),
        },
        "targets": target_insights,
        "path_relations": relations,
        "development_lines": lines,
        "growth_plan": {"short_term": short_term, "mid_term": mid_term},
        "evaluation": {
            "cycle": {"default": "monthly", "recommended": ["monthly"]},
            "metrics": metrics,
            "adjust_rule": "连续2个评估周期未达标时触发自动重规划",
            "gap_baseline": gap_baseline,
            "gap_metric_help": (
                "能力缺口收敛：对比生成报告时的主目标，看短板缩小了多少；"
                "贴合度变化：目标岗位匹配分相较报告生成时的增减（分）"
            ),
        },
        "narrative": llm_summary,
        "track_profile_meta": {
            "ok": True,
            "source": "internal",
            "note": "赛道画像来自本系统岗位库统计；外部公开信息需用户点击后按需获取",
        },
        "recommendations": recommendations,
        "plans_by_target": plans_by_target,
        "generation_timing_ms": timing_ms,
        "llm_enrich_pending": skip_llm_enrich,
        "preference_strategy": build_preference_strategy(preference_snapshot),
    }
    input_snapshot = create_input_snapshot(
        report_obj,
        resume_id=resume_id,
        primary_job_id=primary_job_id,
        target_job_ids=target_job_ids,
        match_goal=match_goal,
        settings_revision=body.get("_settings_revision"),
        captured_at=now,
        constraints={
            key: copy.deepcopy(body[key])
            for key in ("weekly_hours", "planning_horizon_months", "risk_preference")
            if body.get(key) is not None
        },
        preference_snapshot=preference_snapshot,
        preference_revisions={
            "preference_algorithm_version": PREFERENCE_FIT_ALGORITHM_VERSION,
            "workstyle_snapshot_version": WORKSTYLE_SNAPSHOT_VERSION,
            "preference_strategy_version": "preference-strategy-v1",
        },
    )
    report_obj["input_snapshot"] = input_snapshot
    _seed_month_zero_adjustments(report_obj, stamp=stamp_compact)
    ensure_next_month_plans_for_report(report_obj, stamp=stamp_compact)
    ensure_action_ids(report_obj)
    attach_decision_support(report_obj, primary_job_id=primary_job_id)

    title = str(body.get("title") or "").strip() or f"生涯报告-{now[:10]}"
    meta_json = {
        "providers": {
            "primary": "deepseek",
            "copywriter": "doubao",
            "per_target_copywriter": bool(per_target_narrative_meta.get("ok")),
            "plan_customization": bool(plan_custom_meta.get("ok")),
            "graph_recommendations": bool(recommendations.get("enabled")),
            "recommendation_curator_mode": (recommendations.get("meta") or {}).get("curator_batch", {}).get(
                "mode"
            ),
        },
        "per_target_narrative_meta": per_target_narrative_meta,
        "generation_timing_ms": timing_ms,
        "skip_llm_enrich": skip_llm_enrich,
        "input_snapshot": {
            "schema_version": input_snapshot["schema_version"],
            "sha256": input_snapshot["sha256"],
            "captured_at": input_snapshot["captured_at"],
        },
        "enrichment_job": {
            "status": "pending" if skip_llm_enrich else "completed",
            "attempt": 0,
            "requested_at": None,
            "started_at": None,
            "completed_at": now if not skip_llm_enrich else None,
            "error": "",
        },
    }
    report_id = insert_report(
        user_id=user_id,
        resume_id=resume_id,
        title=title,
        primary_job_id=primary_job_id or None,
        target_job_ids=target_job_ids,
        report_obj=report_obj,
        meta_json=meta_json,
        target_insights=target_insights,
        settings_revision=body.get("_settings_revision"),
        config_snapshot=body.get("_config_snapshot") or {},
        personality_profile_id=(
            int(preference_snapshot.get("personality_profile_id"))
            if preference_snapshot and preference_snapshot.get("personality_profile_id")
            else None
        ),
    )
    try:
        ensure_report_experiment_assignment(user_id, report_id)
    except Exception:  # Assignment must never make report generation fail.
        current_app.logger.exception("career_report_experiment_assignment_failed", extra={"report_id": report_id})

    return {
        "report_id": report_id,
        "title": title,
        "primary_job_id": primary_job_id,
        "target_job_ids": target_job_ids,
        "report": report_obj,
        "generation_timing_ms": timing_ms,
        "llm_enrich_pending": skip_llm_enrich,
    }


def enrich_career_report(
    user_id: int,
    report_id: int,
    *,
    expected_attempt: int | None = None,
    on_progress: Callable[[str, int], Any] | None = None,
    refresh_scope: str = "full",
) -> Dict[str, Any]:
    """第二阶段：batch 资源策展 + 豆包叙事/总摘要（报告需先 skip_llm_enrich 生成）。"""
    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)
    if refresh_scope not in ("full", "narrative", "resources", "plan"):
        raise ReportServiceError("不支持的 AI 增强范围", 400)

    report_obj = _parse_json_field(row.get("report_json"), {})
    if not isinstance(report_obj, dict):
        report_obj = {}

    target_job_ids = _parse_json_field(row.get("target_job_ids_json"), [])
    if not isinstance(target_job_ids, list):
        target_job_ids = []
    target_job_ids = [str(value).strip() for value in target_job_ids if str(value).strip()]
    primary_job_id = str(row.get("primary_job_id") or "").strip()
    try:
        input_snapshot, snapshot_backfilled = ensure_input_snapshot(
            report_obj,
            resume_id=int(row.get("resume_id") or 0),
            primary_job_id=primary_job_id,
            target_job_ids=target_job_ids,
            match_goal=str(report_obj.get("match_goal") or "fit"),
            settings_revision=row.get("settings_revision"),
        )
    except ValueError as exc:
        raise ReportServiceError("报告输入快照校验失败，请重新生成报告", 409) from exc
    report_obj["input_snapshot"] = input_snapshot
    base_report = copy.deepcopy(report_obj)

    def emit(stage: str, progress: int) -> None:
        if on_progress is not None:
            on_progress(stage, max(0, min(100, int(progress))))

    emit("snapshot_verified", 8)

    target_insights = report_obj.get("targets")
    if not isinstance(target_insights, list) or not target_insights:
        raise ReportServiceError("报告缺少目标数据，无法增强", 400)

    profile = profile_from_snapshot(input_snapshot)
    if not profile:
        raise ReportServiceError("报告输入快照缺少画像信息，请重新生成报告", 409)

    timing_ms: Dict[str, float] = {}
    t_all = time.perf_counter()

    t = time.perf_counter()
    if refresh_scope in ("full", "resources"):
        recommendations = build_graph_recommendations(target_insights, use_llm_curator=False)
    else:
        recommendations = copy.deepcopy(report_obj.get("recommendations") or {})
    timing_ms["recommendations"] = _elapsed_ms(t)
    emit("evidence_retrieved", 30)

    growth = report_obj.get("growth_plan") if isinstance(report_obj.get("growth_plan"), dict) else {}
    short_term = list(growth.get("short_term") or [])
    mid_term = list(growth.get("mid_term") or [])

    t = time.perf_counter()
    prev_plan_state: Dict[str, Dict[str, Any]] = {}
    for p in report_obj.get("plans_by_target") or []:
        if not isinstance(p, dict):
            continue
        jid = str(p.get("job_id") or "").strip()
        if not jid:
            continue
        prev_plan_state[jid] = {
            "next_month_plan": copy.deepcopy(p.get("next_month_plan")),
            "current_plan_month": p.get("current_plan_month"),
        }

    lines = report_obj.get("development_lines") or {}
    if refresh_scope == "narrative":
        plans_by_target = copy.deepcopy(report_obj.get("plans_by_target") or [])
    else:
        enrich_growth_plan_with_recommendations(short_term, mid_term, recommendations)
        plans_by_target = build_plans_by_target(target_insights, recommendations)
        bind_plan_line_ids(plans_by_target, lines if isinstance(lines, dict) else {})
    for p in plans_by_target:
        if not isinstance(p, dict):
            continue
        jid = str(p.get("job_id") or "").strip()
        prev = prev_plan_state.get(jid) or {}
        if prev.get("current_plan_month") is not None:
            p["current_plan_month"] = prev["current_plan_month"]
    timing_ms["plans"] = _elapsed_ms(t)
    emit("constraint_plan_built", 48)

    t = time.perf_counter()
    if refresh_scope in ("full", "plan"):
        plan_custom_meta = build_custom_plan_actions_batch(
            plans_by_target, target_insights, use_llm=True
        )
    else:
        plan_custom_meta = {"ok": False, "reason": "scope_skipped", "scope": refresh_scope}
    timing_ms["plan_customization"] = _elapsed_ms(t)
    emit("structured_copy_generated", 66)

    stamp_compact = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    ensure_next_month_plans_for_report(
        {"plans_by_target": plans_by_target}, stamp=stamp_compact
    )
    ensure_action_ids({"plans_by_target": plans_by_target})
    t = time.perf_counter()
    _, per_target_narrative_meta = build_grounded_report_narratives(
        plans_by_target, target_insights
    )
    llm_summary = _build_llm_summary(
        profile=profile, target_insights=target_insights, short_term=short_term,
        mid_term=mid_term, recommendations=recommendations,
    )
    timing_ms["grounded_narrative"] = _elapsed_ms(t)
    emit("narrative_generated", 78)

    timing_ms["total"] = _elapsed_ms(t_all)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    report_obj["recommendations"] = recommendations
    report_obj["plans_by_target"] = plans_by_target
    report_obj["growth_plan"] = {"short_term": short_term, "mid_term": mid_term}
    report_obj["narrative"] = llm_summary
    report_obj["llm_enrich_pending"] = False
    report_obj["input_snapshot"] = input_snapshot
    report_obj["enrichment_evidence"] = create_evidence_packet(
        report_obj,
        input_snapshot_sha256=str(input_snapshot.get("sha256") or ""),
        collected_at=now,
    )
    ensure_next_month_plans_for_report(report_obj, stamp=stamp_compact)
    ensure_action_ids(report_obj)
    sync_action_progress_to_plans(report_obj)
    report_obj["enrichment"] = {
        "completed_at": now,
        "timing_ms": timing_ms,
        "plan_customization": plan_custom_meta,
        "refresh_scope": refresh_scope,
        "input_snapshot_sha256": input_snapshot.get("sha256"),
        "evidence_packet_sha256": (report_obj.get("enrichment_evidence") or {}).get("sha256"),
        "snapshot_backfilled": snapshot_backfilled,
    }
    prev_timing = report_obj.get("generation_timing_ms")
    if isinstance(prev_timing, dict):
        prev_timing["enrich_total"] = timing_ms.get("total")
    else:
        report_obj["generation_timing_ms"] = {"enrich_total": timing_ms.get("total")}

    attach_decision_support(report_obj, primary_job_id=primary_job_id)
    safe_report, quality = gate_enrichment(base_report, report_obj, input_snapshot)
    safe_report["input_snapshot"] = input_snapshot
    safe_report["enrichment_evidence"] = report_obj["enrichment_evidence"]
    safe_report["enrichment_quality"] = quality
    safe_enrichment = safe_report.get("enrichment") if isinstance(safe_report.get("enrichment"), dict) else {}
    safe_enrichment.update(
        {
            "completed_at": now,
            "timing_ms": timing_ms,
            "quality_status": quality.get("status"),
            "quality_score": quality.get("score"),
            "input_snapshot_sha256": input_snapshot.get("sha256"),
            "evidence_packet_sha256": (safe_report.get("enrichment_evidence") or {}).get("sha256"),
            "snapshot_backfilled": snapshot_backfilled,
        }
    )
    safe_report["enrichment"] = safe_enrichment
    safe_report["llm_enrich_pending"] = False
    attach_decision_support(safe_report, primary_job_id=primary_job_id)
    emit("quality_gate_completed", 92)

    merged = merge_report_enrichment(
        report_id,
        safe_report,
        expected_attempt=expected_attempt,
        refresh_scope=refresh_scope,
    )
    if merged is None:
        return {
            "report_id": report_id,
            "superseded": True,
            "enrichment_timing_ms": timing_ms,
        }
    report_obj = merged
    emit("completed", 100)

    return {
        "report_id": report_id,
        "report": report_obj,
        "enrichment_timing_ms": timing_ms,
        "per_target_narrative_meta": per_target_narrative_meta,
        "plan_customization_meta": plan_custom_meta,
        "quality": quality,
    }


def _repair_missing_monthly_follow_up(
    *,
    user_id: int,
    report_id: int,
    report_version: int,
    report_obj: Dict[str, Any],
    reviews_asc: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Repair legacy reviews that were saved without advancing the next month.

    New reviews use an explicit proposal. This compatibility path only applies
    when no live proposal exists, and persists a deterministic continuation so
    an already-confirmed historical review is not left at a dead end forever.
    """
    versions = list_plan_version_rows(user_id, report_id)
    if any(
        str(item.get("status") or "") == "proposed"
        and int(item.get("base_report_version") or 0) == int(item.get("current_report_version") or -1)
        for item in versions
    ):
        return report_obj

    candidate = copy.deepcopy(report_obj)
    plans = [item for item in candidate.get("plans_by_target") or [] if isinstance(item, dict)]
    repaired = False
    original_latest = copy.deepcopy((candidate.get("evaluation") or {}).get("latest_review"))
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    for plan in plans:
        job_id = str(plan.get("job_id") or "").strip()
        applicable = [
            review
            for review in reviews_asc
            if str(review.get("review_cycle") or "monthly") == "monthly"
            and (
                str(review.get("scope") or "all") == "all"
                or (str(review.get("scope") or "") == "target" and str(review.get("job_id") or "") == job_id)
            )
        ]
        review_month = min(12, len(applicable))
        if not job_id or review_month <= 0:
            continue
        next_plan = plan.get("next_month_plan") if isinstance(plan.get("next_month_plan"), dict) else {}
        try:
            anchor_month = int(next_plan.get("review_anchor_month"))
        except (TypeError, ValueError):
            anchor_month = -1
        try:
            plan_month = int(next_plan.get("plan_month") or plan.get("current_plan_month") or 0)
        except (TypeError, ValueError):
            plan_month = 0
        if anchor_month >= review_month and plan_month >= min(12, review_month + 1):
            continue

        metrics = applicable[-1].get("metrics") if isinstance(applicable[-1].get("metrics"), dict) else {}
        evaluation = metrics.get("evaluation") if isinstance(metrics.get("evaluation"), dict) else {}
        eval_block = candidate.get("evaluation") if isinstance(candidate.get("evaluation"), dict) else {}
        eval_block["latest_review"] = {
            "submitted_metrics": metrics.get("submitted") or {},
            "action_completion": metrics.get("action_completion") or {},
            "evaluation": evaluation,
        }
        candidate["evaluation"] = eval_block
        adjustment = _build_auto_adjustment(
            candidate,
            [],
            replan_mode="continue",
            target_job_ids=[job_id],
            allow_llm=False,
        )
        adjustment["reason"] = "兼容补齐：历史月复盘已确认，延续当前阶段并恢复下一月安排"
        _apply_auto_adjustment_to_report(
            candidate,
            adjustment,
            stamp=stamp,
            review_anchor_month=float(review_month),
            replan_mode="continue",
            metric_eval=evaluation,
            target_job_ids=[job_id],
            include_global_growth=False,
        )
        repaired = True

    eval_block = candidate.get("evaluation") if isinstance(candidate.get("evaluation"), dict) else {}
    if original_latest is None:
        eval_block.pop("latest_review", None)
    else:
        eval_block["latest_review"] = original_latest
    candidate["evaluation"] = eval_block
    if not repaired:
        return report_obj
    saved = update_report_json_if_version(
        user_id=user_id,
        report_id=report_id,
        expected_version=report_version,
        report_obj=candidate,
    )
    return candidate if saved else report_obj


def get_career_report_detail(user_id: int, report_id: int) -> Dict[str, Any]:
    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)

    target_ids = _parse_json_field(row.get("target_job_ids_json"), [])
    report_obj = _parse_json_field(row.get("report_json"), {})
    if not isinstance(target_ids, list):
        target_ids = []
    if not isinstance(report_obj, dict):
        report_obj = {}

    if isinstance(report_obj, dict):
        ensure_next_month_plans_for_report(
            report_obj,
            stamp=datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        )
        ensure_action_ids(report_obj)
        sync_action_progress_to_plans(report_obj)
        rev_rows = list_review_metrics_asc(report_id)
        rev_parse: List[Dict[str, Any]] = []
        for rr in rev_rows:
            mj = _parse_json_field(rr.get("metrics_json"), {})
            if not isinstance(mj, dict):
                mj = {}
            rev_parse.append(
                {
                    "review_id": int(rr["id"]),
                    "review_cycle": rr.get("review_cycle") or "monthly",
                    "scope": rr.get("scope") or "all",
                    "job_id": rr.get("job_id"),
                    "metrics": mj,
                }
            )
        # Compatibility repair for reviews confirmed before action completion
        # became part of the growth basis. Only the latest monthly review for a
        # scope is hydrated, and only while the plan is still the unadvanced
        # initial plan; this avoids attributing next-month work to an old review.
        hydrated_scopes: set[str] = set()
        plans = [item for item in report_obj.get("plans_by_target") or [] if isinstance(item, dict)]
        for review in reversed(rev_parse):
            if str(review.get("review_cycle") or "monthly") != "monthly":
                continue
            scope = str(review.get("scope") or "all")
            job_id = str(review.get("job_id") or "").strip()
            scope_key = f"target:{job_id}" if scope == "target" else "all"
            if scope_key in hydrated_scopes:
                continue
            hydrated_scopes.add(scope_key)
            scoped_plans = plans if scope == "all" else [plan for plan in plans if str(plan.get("job_id") or "") == job_id]
            if not scoped_plans or any((plan.get("next_month_plan") or {}).get("review_anchor_month") not in (None, "") for plan in scoped_plans):
                continue
            metrics = review.get("metrics") if isinstance(review.get("metrics"), dict) else {}
            if isinstance(metrics.get("action_completion"), dict):
                continue
            snapshot = summarize_plan_action_completion(
                report_obj,
                target_job_ids=[job_id] if scope == "target" and job_id else None,
            )
            if snapshot.get("has_completed_actions"):
                metrics["action_completion"] = snapshot
                evaluation = metrics.get("evaluation") if isinstance(metrics.get("evaluation"), dict) else {}
                evaluation["action_completion"] = snapshot
                evaluation["has_action_evidence"] = True
                evaluation["action_completion_rate"] = snapshot.get("completion_rate")
                metrics["evaluation"] = evaluation
        _rebuild_development_timelines(report_obj, rev_parse)
        report_obj = _repair_missing_monthly_follow_up(
            user_id=user_id,
            report_id=report_id,
            report_version=int(row.get("report_version") or 1),
            report_obj=report_obj,
            reviews_asc=rev_parse,
        )
    evidence_records = list_evidence_records(report_id)
    attach_decision_support(
        report_obj,
        primary_job_id=str(row.get("primary_job_id") or ""),
        evidence_records=evidence_records,
    )

    preferences = effective_preferences(user_id)["effective"]
    personalization_enabled = bool(preferences.get("report_longitudinal_personalization", True))
    assignment = get_report_experiment_assignment(user_id, report_id) if personalization_enabled else None
    longitudinal_rows = fetch_longitudinal_rows(user_id, report_id, int(row.get("resume_id") or 0))
    if longitudinal_rows is not None:
        report_obj["longitudinal_insights"] = build_longitudinal_insights(
            report_obj,
            report_created_at=row.get("created_at"),
            report_updated_at=row.get("updated_at"),
            profile_updated_at=longitudinal_rows.get("profile_updated_at"),
            review_rows=longitudinal_rows.get("reviews") or [],
            plan_version_rows=longitudinal_rows.get("versions") or [],
            action_event_rows=longitudinal_rows.get("events") or [],
            personalization_enabled=personalization_enabled,
            experiment_variant=str((assignment or {}).get("variant") or "off"),
        )

    sanitize_review_text_fields(report_obj)

    return {
        "report_id": int(row["id"]),
        "title": row.get("title"),
        "resume_id": row.get("resume_id"),
        "primary_job_id": row.get("primary_job_id"),
        "target_job_ids": target_ids or [],
        "report": report_obj or {},
        "llm_enrich_pending": bool(report_obj.get("llm_enrich_pending")),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "configuration": {"settings_revision": row.get("settings_revision"), "source": "revision" if row.get("settings_revision") is not None else "legacy_env_config"},
    }


def export_career_report_pdf(
    user_id: int,
    report_id: int,
    export_options: Dict[str, Any] | None = None,
) -> Tuple[bytes, str]:
    row = fetch_report_for_export(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)

    title = str(row.get("title") or "生涯报告")
    report_obj = _parse_json_field(row.get("report_json"), {})
    if not isinstance(report_obj, dict):
        report_obj = {}

    try:
        html = build_report_export_html(
            report_id=report_id,
            title=title,
            report_obj=report_obj,
            export_options=export_options,
        )
    except ReportExportValidationError as exc:
        raise ReportServiceError(str(exc), 400) from exc
    pdf_bytes = render_pdf_with_playwright(html)
    return pdf_bytes, f"career_report_{report_id}.pdf"


def _target_titles_from_report_obj(
    report_obj: Any,
    job_ids_order: List[str] | None = None,
) -> List[str]:
    if not isinstance(report_obj, dict):
        return []
    targets = report_obj.get("targets") or []
    by_id: Dict[str, str] = {}
    ordered: List[str] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        job_id = str(target.get("id") or "").strip()
        title = str(target.get("display_title") or target.get("title") or "").strip()
        if not title:
            continue
        if job_id:
            by_id[job_id] = title
        ordered.append(title)
    if job_ids_order:
        titles: List[str] = []
        for job_id in job_ids_order:
            jid = str(job_id or "").strip()
            if not jid:
                continue
            titles.append(by_id.get(jid) or jid)
        if titles:
            return titles
    return ordered


def _resolve_report_target_titles(
    report_id: int,
    targets_map: Dict[int, List[Dict[str, Any]]],
    json_fallback: Dict[int, Dict[str, Any]],
    target_job_ids: List[str],
) -> List[str]:
    table_rows = targets_map.get(report_id, [])
    job_ids_order = [str(row.get("job_id") or "").strip() for row in table_rows if str(row.get("job_id") or "").strip()]
    if not job_ids_order:
        job_ids_order = [str(x).strip() for x in target_job_ids if str(x).strip()]

    report_obj = json_fallback.get(report_id)
    if report_obj:
        json_titles = _target_titles_from_report_obj(report_obj, job_ids_order or None)
        if json_titles:
            return json_titles

    titles: List[str] = []
    for row in table_rows:
        title = str(row.get("title") or "").strip()
        if title:
            titles.append(title)
            continue
        job_id = str(row.get("job_id") or "").strip()
        if job_id:
            titles.append(job_id)
    return titles


def list_career_reports(user_id: int, limit: int) -> List[Dict[str, Any]]:
    rows = list_user_reports(user_id, limit)
    report_ids = [int(row["id"]) for row in rows]
    targets_map = list_targets_for_reports(report_ids)
    fallback_ids = [
        report_id
        for report_id in report_ids
        if not any(str(item.get("title") or "").strip() for item in targets_map.get(report_id, []))
    ]
    json_fallback = fetch_report_json_by_ids(fallback_ids) if fallback_ids else {}

    out: List[Dict[str, Any]] = []
    for row in rows:
        report_id = int(row["id"])
        target_ids = _parse_json_field(row.get("target_job_ids_json"), [])
        if not isinstance(target_ids, list):
            target_ids = []
        out.append(
            {
                "report_id": report_id,
                "title": row.get("title"),
                "resume_id": row.get("resume_id"),
                "primary_job_id": row.get("primary_job_id"),
                "target_job_ids": target_ids,
                "target_titles": _resolve_report_target_titles(
                    report_id,
                    targets_map,
                    json_fallback,
                    target_ids,
                ),
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            }
        )
    return out


def list_career_report_reviews(user_id: int, report_id: int) -> List[Dict[str, Any]]:
    if not report_owned_by_user(user_id, report_id):
        raise ReportServiceError("报告不存在或无权访问", 404)

    items: List[Dict[str, Any]] = []
    for row in list_review_rows(report_id):
        metrics = _parse_json_field(row.get("metrics_json"), {})
        adjust = _parse_json_field(row.get("adjustment_json"), {})
        if not isinstance(metrics, dict):
            metrics = {}
        if not isinstance(adjust, dict):
            adjust = {}
        items.append(
            sanitize_review_text_fields(
                {
                    "review_id": int(row["id"]),
                    "review_cycle": row.get("review_cycle"),
                    "scope": row.get("scope") or "all",
                    "job_id": row.get("job_id"),
                    "metrics": metrics,
                    "adjustment": adjust,
                    "review_status": metrics.get("review_status") or adjust.get("review_status"),
                    "created_at": str(row.get("created_at") or ""),
                }
            )
        )
    return items


def _resolve_review_scope(body: Dict[str, Any], row: Dict[str, Any]) -> tuple[str, str | None, List[str]]:
    target_ids = _parse_json_field(row.get("target_job_ids_json"), [])
    if not isinstance(target_ids, list):
        target_ids = []
    target_ids = [str(value).strip() for value in target_ids if str(value).strip()]
    scope = str(body.get("scope") or "target").strip().lower()
    if scope not in ("target", "all"):
        raise ReportServiceError("scope 仅支持 target 或 all", 400)
    if scope == "target":
        job_id = str(body.get("job_id") or row.get("primary_job_id") or "").strip()
        if not job_id or job_id not in target_ids:
            raise ReportServiceError("job_id 必须属于当前报告的目标岗位", 400)
        return scope, job_id, [job_id]
    return scope, None, target_ids


def _review_job_cards(report_obj: Dict[str, Any], job_ids: List[str]) -> List[Dict[str, Any]]:
    """Resolve review baselines without making Neo4j a hard dependency.

    A generated report already contains the exact job capability snapshot used
    for its baseline.  Reusing it is both more reproducible and more resilient
    than requiring the graph service to be online for every review draft.
    """
    wanted = {str(value).strip() for value in job_ids if str(value).strip()}
    cards: Dict[str, Dict[str, Any]] = {}
    for target in report_obj.get("targets") or []:
        if not isinstance(target, dict):
            continue
        target_id = str(target.get("id") or target.get("job_id") or "").strip()
        if target_id in wanted and isinstance(target.get("scores"), dict):
            cards[target_id] = target

    missing = [job_id for job_id in wanted if job_id not in cards]
    if missing:
        try:
            for card in _query_jobs_by_ids(missing):
                card_id = str(card.get("id") or card.get("job_id") or "").strip()
                if card_id:
                    cards[card_id] = card
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning(
                "career_report_review_graph_unavailable; using saved report snapshots: %s",
                exc,
            )
    return [cards[job_id] for job_id in job_ids if job_id in cards]


def create_career_review_draft(user_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Extract candidates without evaluating them or changing the current plan."""
    report_id = _parse_report_id(body)
    purge_expired_review_drafts(user_id, retention_days=90)
    review_text = str(body.get("review_text") or "").strip()
    explicit_metrics = body.get("metrics") if isinstance(body.get("metrics"), dict) else {}
    if not review_text and not explicit_metrics:
        raise ReportServiceError("请填写复盘内容", 400)
    try:
        review_cycle = normalize_review_cycle(body.get("review_cycle"))
    except ValueError as exc:
        raise ReportServiceError(str(exc), 400) from exc
    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)
    scope, job_id, scoped_job_ids = _resolve_review_scope(body, row)
    report_obj = _parse_json_field(row.get("report_json"), {})
    if not isinstance(report_obj, dict):
        report_obj = {}
    stored_text = storage_safe_text(review_text, kind="review", max_chars=4000) if review_text else "结构化指标复盘"
    extraction = (
        {"ok": True, "source": "user_submitted", "metrics": explicit_metrics, "summary": "用户提交的结构化指标，仍需按确认流程记录"}
        if explicit_metrics
        else _llm_extract_metrics_from_text(
            report_obj=report_obj,
            review_text=stored_text,
            review_cycle=review_cycle,
        )
    )
    system_metrics: Dict[str, float] = {}
    resume_id = int(row.get("resume_id") or 0)
    if resume_id and scoped_job_ids:
        profile, profile_error = _resolve_student_profile({"resume_id": resume_id}, user_id)
        if profile and not profile_error:
            system_metrics = compute_review_gap_metrics(
                report_obj,
                profile,
                _review_job_cards(report_obj, scoped_job_ids),
                target_job_id=job_id if scope == "target" else None,
            )
    metric_definitions = (((report_obj.get("evaluation") or {}).get("metrics")) or [])
    candidates = build_metric_candidates(
        review_text=stored_text,
        metric_definitions=metric_definitions if isinstance(metric_definitions, list) else [],
        extracted_metrics=extraction.get("metrics") if isinstance(extraction.get("metrics"), dict) else {},
        extraction_source=str(extraction.get("source") or "heuristic_fallback"),
        system_metrics=system_metrics,
    )
    extraction_meta = {
        "ok": bool(extraction.get("ok")),
        "source": extraction.get("source"),
        "model": extraction.get("model"),
        "summary": extraction.get("summary"),
        "error": extraction.get("error"),
        "system_metric_codes": sorted(system_metrics),
    }
    draft_id = insert_review_draft(
        user_id=user_id,
        report_id=report_id,
        review_cycle=review_cycle,
        scope=scope,
        job_id=job_id,
        review_text=stored_text,
        candidates=candidates,
        extraction=extraction_meta,
    )
    if draft_id is None:
        raise ReportServiceError("报告不存在或无权访问", 404)
    return {
        "draft_id": draft_id,
        "report_id": report_id,
        "status": "draft",
        "review_cycle": review_cycle,
        "scope": scope,
        "job_id": job_id,
        "review_text": stored_text,
        "summary": extraction_meta.get("summary"),
        "candidates": candidates,
        "requires_confirmation": True,
    }


def submit_career_review_cycle(user_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility endpoint: explicit metrics are confirmed, text-only callers must use drafts."""
    explicit_metrics = body.get("metrics")
    if not isinstance(explicit_metrics, dict) or not explicit_metrics:
        raise ReportServiceError("自然语言复盘需先生成草稿并确认事实，请使用 review-drafts 接口", 409)
    draft = create_career_review_draft(user_id, body)
    explicit_codes = {str(code) for code in explicit_metrics}
    decisions = [
        {
            "code": candidate["code"],
            "decision": "confirm" if candidate["code"] in explicit_codes else "ignore",
            "value": candidate["value"],
        }
        for candidate in draft["candidates"]
    ]
    return confirm_career_review_draft(
        user_id,
        int(draft["draft_id"]),
        {"candidates": decisions, "signals": body.get("signals") or {}},
    )


def confirm_career_review_draft(user_id: int, draft_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    draft = fetch_review_draft(user_id, draft_id)
    if not draft:
        raise ReportServiceError("复盘草稿不存在或无权访问", 404)
    if str(draft.get("status") or "") != "draft":
        raise ReportServiceError("该复盘草稿已处理", 409)
    stored_candidates = _parse_json_field(draft.get("candidates_json"), [])
    decisions = body.get("candidates")
    if not isinstance(decisions, list):
        raise ReportServiceError("请确认或忽略每个候选指标", 400)
    try:
        submitted_metrics, audited_candidates = confirmed_metrics_from_decisions(
            stored_candidates if isinstance(stored_candidates, list) else [],
            decisions,
        )
    except ValueError as exc:
        raise ReportServiceError(str(exc), 400) from exc

    report_obj = _parse_json_field(draft.get("report_json"), {})
    if not isinstance(report_obj, dict):
        report_obj = {}
    expected_metrics = (((report_obj.get("evaluation") or {}).get("metrics")) or [])
    if not isinstance(expected_metrics, list):
        expected_metrics = []
    metric_eval = _evaluate_review_metrics(expected_metrics, submitted_metrics)
    scope = str(draft.get("scope") or "target")
    job_id = str(draft.get("job_id") or "").strip() or None
    target_ids = _parse_json_field(draft.get("target_job_ids_json"), [])
    scoped_job_ids = [job_id] if scope == "target" and job_id else [str(item) for item in target_ids or []]
    action_completion = summarize_plan_action_completion(
        report_obj,
        target_job_ids=scoped_job_ids,
    )
    metric_eval["action_completion"] = copy.deepcopy(action_completion)
    metric_eval["has_action_evidence"] = bool(action_completion.get("has_completed_actions"))
    metric_eval["action_completion_rate"] = action_completion.get("completion_rate")
    signals = body.get("signals") if isinstance(body.get("signals"), dict) else {}
    preference_signals = sanitize_preference_signals(body.get("preference_signals"))
    evidence_records = body.get("evidence_records") if isinstance(body.get("evidence_records"), list) else []
    review_status = classify_review_status(
        metric_eval,
        signals=signals,
        evidence_records=evidence_records,
    )
    eval_block = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
    streaks = eval_block.get("consecutive_fail_months_by_scope")
    if not isinstance(streaks, dict):
        streaks = {}
    streak_key = f"target:{job_id}" if scope == "target" else "all"
    previous_failures = int(streaks.get(streak_key) or 0)
    has_metric_evidence = bool(metric_eval.get("has_evidence"))
    has_action_evidence = bool(metric_eval.get("has_action_evidence"))
    has_evidence = has_metric_evidence or has_action_evidence
    failed_codes = list(metric_eval.get("failed_codes") or [])
    if not has_evidence or review_status in {"goal_changed", "overloaded", "evidence_missing"}:
        consecutive_failures = previous_failures
    elif failed_codes:
        consecutive_failures = previous_failures + 1
    else:
        consecutive_failures = 0
    action_rate = float(action_completion.get("completion_rate") or 0.0)
    action_only_passed = has_action_evidence and action_rate >= 0.8
    replan_mode = resolve_replan_mode(
        all_passed=(not failed_codes and has_metric_evidence) or (not has_metric_evidence and action_only_passed),
        failed_codes=failed_codes,
        consecutive_fail_months=consecutive_failures,
        has_evidence=has_evidence,
    )
    review_cycle = str(draft.get("review_cycle") or "monthly")
    if review_cycle == "monthly" and replan_mode == "insufficient":
        # A confirmed monthly review must still hand the user a concrete next
        # month. With no quantitative signal we extend the stage plan without
        # pretending that a metric passed or failed.
        replan_mode = "continue"
    should_build_next_month = review_cycle == "monthly" and review_status not in {"goal_changed", "evidence_missing"}
    if should_build_next_month:
        adjust_detail = _build_auto_adjustment(
            report_obj,
            failed_codes,
            replan_mode=replan_mode,
            target_job_ids=scoped_job_ids,
            allow_llm=has_metric_evidence,
        )
        if not has_evidence:
            adjust_detail["reason"] = "本月复盘已确认，但量化证据不足；按当前阶段延续并生成下一月基础安排"
    else:
        adjust_detail = {
            "triggered": False,
            "reason": "确认信息不足或目标已变化，本次不生成自动调计划提案",
            "replan_mode": "insufficient",
            "failed_metric_codes": [],
            "focus_dimensions": [],
            "focus_labels": [],
            "extra_actions": [],
            "by_job": [],
            "llm_meta": {"enabled": False, "used": False, "error": review_status},
        }
    adjust_detail["consecutive_fail_months"] = consecutive_failures
    adjustment_payload = {
        "scope": scope,
        "job_id": job_id,
        "review_status": review_status,
        "all_passed": bool(metric_eval.get("all_passed")) or (not has_metric_evidence and action_only_passed),
        "pass_rate": metric_eval.get("pass_rate") if metric_eval.get("pass_rate") is not None else action_completion.get("completion_rate"),
        "failed_codes": failed_codes,
        "replan_mode": replan_mode,
        "consecutive_fail_months": consecutive_failures,
        "auto_adjustment": adjust_detail,
        "application_status": "proposed" if adjust_detail.get("triggered") else "not_proposed",
    }
    extraction_meta = _parse_json_field(draft.get("extraction_json"), {})
    metrics_payload = {
        "submitted": submitted_metrics,
        "action_completion": action_completion,
        "review_text": str(draft.get("review_text") or ""),
        "llm_extract": extraction_meta if isinstance(extraction_meta, dict) else {},
        "candidate_decisions": audited_candidates,
        "preference_signals": preference_signals,
        "evaluation": metric_eval,
        "review_status": review_status,
        "signals": signals,
    }
    created_at = utc_stamp()
    eval_block["latest_review"] = {
        "review_id": None,
        "draft_id": draft_id,
        "review_cycle": str(draft.get("review_cycle") or "monthly"),
        "scope": scope,
        "job_id": job_id,
        "status": review_status,
        "submitted_metrics": submitted_metrics,
        "action_completion": action_completion,
        "review_text": str(draft.get("review_text") or ""),
        "llm_extract": extraction_meta,
        "candidate_decisions": audited_candidates,
        "preference_signals": preference_signals,
        "evaluation": metric_eval,
        "adjustment": adjustment_payload,
        "created_at": created_at,
    }
    report_obj["evaluation"] = eval_block
    if scope == "target" and job_id:
        latest_by_target = eval_block.get("latest_reviews_by_target")
        if not isinstance(latest_by_target, dict):
            latest_by_target = {}
            eval_block["latest_reviews_by_target"] = latest_by_target
        latest_by_target[job_id] = copy.deepcopy(eval_block["latest_review"])
    streaks[streak_key] = consecutive_failures
    eval_block["consecutive_fail_months_by_scope"] = streaks
    eval_block["latest_review_status"] = review_status
    eval_block["latest_plan_proposal_status"] = "proposed" if adjust_detail.get("triggered") else "none"

    review_anchor_month = float(
        min(
            12,
            count_reviews(
                int(draft["report_id"]),
                scope=scope,
                job_id=job_id,
                review_cycle="monthly",
            )
            + 1,
        )
    )
    reviews_asc: List[Dict[str, Any]] = []
    for review_row in list_review_metrics_asc(int(draft["report_id"])):
        stored_metrics = _parse_json_field(review_row.get("metrics_json"), {})
        reviews_asc.append(
            {
                "review_id": int(review_row["id"]),
                "review_cycle": review_row.get("review_cycle") or "monthly",
                "scope": review_row.get("scope") or "all",
                "job_id": review_row.get("job_id"),
                "metrics": stored_metrics if isinstance(stored_metrics, dict) else {},
            }
        )
    reviews_asc.append({"review_id": None, "review_cycle": review_cycle, "scope": scope, "job_id": job_id, "metrics": metrics_payload})
    report_obj["preference_strategy"] = update_calibration(
        report_obj.get("preference_strategy"),
        [item.get("metrics") or {} for item in reviews_asc],
    )
    _rebuild_development_timelines(report_obj, reviews_asc)

    proposed_report: Dict[str, Any] | None = None
    plan_diff: List[Dict[str, Any]] = []
    if adjust_detail.get("triggered"):
        proposed_report = copy.deepcopy(report_obj)
        _apply_auto_adjustment_to_report(
            proposed_report,
            adjust_detail,
            stamp=datetime.utcnow().strftime("%Y%m%d%H%M%S"),
            review_anchor_month=review_anchor_month,
            replan_mode=replan_mode,
            metric_eval=metric_eval,
            target_job_ids=scoped_job_ids,
            include_global_growth=scope == "all",
        )
        plan_diff = build_plan_diff(report_obj, proposed_report, scope=scope, job_id=job_id)

    committed = commit_confirmed_review(
        user_id=user_id,
        report_id=int(draft["report_id"]),
        draft_id=draft_id,
        expected_version=int(draft.get("report_version") or 1),
        report_obj=report_obj,
        review_cycle=str(draft.get("review_cycle") or "monthly"),
        scope=scope,
        job_id=job_id,
        metrics_payload=metrics_payload,
        adjustment_payload=adjustment_payload,
        proposed_report=proposed_report,
        plan_diff=plan_diff,
        evidence_records=evidence_records,
        preference_evidence=behavioral_evidence_rows(preference_signals),
    )
    if committed is None:
        raise ReportServiceError("报告或草稿已更新，请刷新后重试", 409)
    proposal_id = committed.get("proposal_id")
    return {
        "draft_id": draft_id,
        "review_id": committed["review_id"],
        "report_id": int(draft["report_id"]),
        "review_cycle": str(draft.get("review_cycle") or "monthly"),
        "review_status": review_status,
        "evaluation": metric_eval,
        "submitted_metrics": submitted_metrics,
        "preference_calibration": (report_obj.get("preference_strategy") or {}).get("calibration"),
        "plan_proposal": {
            "proposal_id": proposal_id,
            "status": "proposed",
            "changes": plan_diff,
            "stale": False,
        } if proposal_id else None,
    }


def decide_report_preference_strategy(user_id: int, report_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)
    report_obj = _parse_json_field(row.get("report_json"), {})
    strategy = report_obj.get("preference_strategy") if isinstance(report_obj, dict) else None
    if not isinstance(strategy, dict) or strategy.get("status") == "missing":
        raise ReportServiceError("当前报告没有可用的执行方式建议", 409)
    try:
        updated = apply_strategy_decision(strategy, body)
    except ValueError as exc:
        raise ReportServiceError(str(exc), 400) from exc
    report_obj["preference_strategy"] = updated
    saved = commit_preference_strategy_update(
        user_id=user_id,
        report_id=report_id,
        expected_version=int(row.get("report_version") or 1),
        report_obj=report_obj,
        decision=str(updated.get("last_decision") or "accept"),
    )
    if not saved:
        raise ReportServiceError("报告已更新，请刷新后重试", 409)
    return {"report_id": report_id, "report_version": int(row.get("report_version") or 1) + 1, "preference_strategy": updated}


def list_career_plan_versions(user_id: int, report_id: int) -> List[Dict[str, Any]]:
    if not report_owned_by_user(user_id, report_id):
        raise ReportServiceError("报告不存在或无权访问", 404)
    items: List[Dict[str, Any]] = []
    for row in list_plan_version_rows(user_id, report_id):
        diff = _parse_json_field(row.get("diff_json"), [])
        decision = _parse_json_field(row.get("decision_json"), {})
        status = str(row.get("status") or "proposed")
        items.append(
            {
                "proposal_id": int(row["id"]),
                "review_id": int(row["review_id"]) if row.get("review_id") else None,
                "status": status,
                "scope": row.get("scope"),
                "job_id": row.get("job_id"),
                "base_report_version": int(row.get("base_report_version") or 0),
                "current_report_version": int(row.get("current_report_version") or 0),
                "stale": status == "proposed" and int(row.get("base_report_version") or 0) != int(row.get("current_report_version") or 0),
                "changes": diff if isinstance(diff, list) else [],
                "decision": decision if isinstance(decision, dict) else {},
                "created_at": str(row.get("created_at") or ""),
                "decided_at": str(row.get("decided_at") or "") or None,
            }
        )
    return items


def decide_career_plan_proposal(user_id: int, proposal_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    decision = str(body.get("decision") or "").strip().lower()
    if decision not in {"accept", "reject"}:
        raise ReportServiceError("decision 仅支持 accept 或 reject", 400)
    row = fetch_plan_version(user_id, proposal_id)
    if not row:
        raise ReportServiceError("计划提案不存在或无权访问", 404)
    changes = _parse_json_field(row.get("diff_json"), [])
    if not isinstance(changes, list):
        changes = []
    all_ids = {str(item.get("id") or "") for item in changes if isinstance(item, dict)}
    requested_ids = body.get("accepted_change_ids")
    if decision == "accept":
        if requested_ids is None:
            accepted_ids = all_ids
        elif isinstance(requested_ids, list):
            accepted_ids = {str(value) for value in requested_ids}
        else:
            raise ReportServiceError("accepted_change_ids 必须是数组", 400)
        if not accepted_ids or not accepted_ids.issubset(all_ids):
            raise ReportServiceError("请选择至少一项有效变更", 400)
        try:
            effective_changes = apply_change_overrides(
                changes,
                body.get("change_overrides") if isinstance(body.get("change_overrides"), list) else [],
                accepted_ids,
            )
        except ValueError as exc:
            raise ReportServiceError(str(exc), 400) from exc
        report_obj = _parse_json_field(row.get("report_json"), {})
        if not isinstance(report_obj, dict):
            report_obj = {}
        applied_ids = apply_plan_changes(report_obj, effective_changes, accepted_ids)
        if not applied_ids:
            raise ReportServiceError("没有可应用的计划变更", 400)
        snapshot = _parse_json_field(row.get("snapshot_json"), {})
        snapshot_eval = snapshot.get("evaluation") if isinstance(snapshot, dict) else {}
        current_eval = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
        if isinstance(snapshot_eval, dict):
            current_eval["last_replan_mode"] = snapshot_eval.get("latest_review", {}).get("adjustment", {}).get("replan_mode") or snapshot_eval.get("last_replan_mode")
        current_eval["latest_plan_proposal_status"] = "accepted"
        current_eval["latest_plan_version_id"] = proposal_id
        report_obj["evaluation"] = current_eval
        attach_decision_support(report_obj, primary_job_id=str(row.get("primary_job_id") or ""))
    else:
        accepted_ids = set()
        applied_ids = []
        report_obj = None
    result = commit_plan_proposal_decision(
        user_id=user_id,
        version_id=proposal_id,
        decision=decision,
        accepted_change_ids=applied_ids,
        report_obj=report_obj,
    )
    if result == "stale":
        raise ReportServiceError("当前计划已变化，该提案已过期，请基于最新报告重新复盘", 409)
    if result == "conflict":
        raise ReportServiceError("该计划提案已处理", 409)
    if result == "not_found":
        raise ReportServiceError("计划提案不存在或无权访问", 404)
    return {
        "proposal_id": proposal_id,
        "report_id": int(row["report_id"]),
        "status": result,
        "accepted_change_ids": applied_ids,
        "partial": decision == "accept" and len(applied_ids) < len(all_ids),
    }


def _submit_career_review_cycle_legacy_applied(user_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    report_id = _parse_report_id(body)
    review_cycle = "monthly"
    submitted_metrics = body.get("metrics")
    review_text = str(body.get("review_text") or "").strip()
    stored_review_text = (
        storage_safe_text(review_text, kind="review", max_chars=4000) if review_text else ""
    )
    if not isinstance(submitted_metrics, dict):
        submitted_metrics = None
    if not submitted_metrics and not review_text:
        raise ReportServiceError("请提供 metrics 或 review_text", 400)

    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)

    report_obj = _parse_json_field(row.get("report_json"), {})
    if not isinstance(report_obj, dict):
        report_obj = {}

    target_ids = _parse_json_field(row.get("target_job_ids_json"), [])
    if not isinstance(target_ids, list):
        target_ids = []
    target_ids = [str(value).strip() for value in target_ids if str(value).strip()]
    scope = str(body.get("scope") or "target").strip().lower()
    if scope not in ("target", "all"):
        raise ReportServiceError("scope 仅支持 target 或 all", 400)
    job_id: str | None = None
    if scope == "target":
        job_id = str(body.get("job_id") or row.get("primary_job_id") or "").strip()
        if not job_id or job_id not in target_ids:
            raise ReportServiceError("job_id 必须属于当前报告的目标岗位", 400)
        scoped_job_ids = [job_id]
    else:
        scoped_job_ids = target_ids

    expected_metrics = (((report_obj.get("evaluation") or {}).get("metrics")) or [])
    if not isinstance(expected_metrics, list):
        expected_metrics = []

    llm_extract_meta: Dict[str, Any] = {}
    auto_gap_metrics: Dict[str, float] = {}
    resume_id = int(row.get("resume_id") or 0)
    if resume_id:
        profile, perr = _resolve_student_profile({"resume_id": resume_id}, user_id)
        if profile and not perr:
            if scoped_job_ids:
                job_cards = _query_jobs_by_ids(scoped_job_ids)
                auto_gap_metrics = compute_review_gap_metrics(
                    report_obj,
                    profile,
                    job_cards,
                    target_job_id=job_id if scope == "target" else None,
                )

    def _merge_auto_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(metrics)
        for code, val in auto_gap_metrics.items():
            if out.get(code) in (None, ""):
                out[code] = val
        return out

    if isinstance(submitted_metrics, dict) and submitted_metrics:
        submitted_metrics = _merge_auto_metrics(submitted_metrics)
        if auto_gap_metrics:
            llm_extract_meta["auto_gap_metrics"] = auto_gap_metrics
    elif review_text:
        llm_extract = _llm_extract_metrics_from_text(
            report_obj=report_obj,
            review_text=stored_review_text or review_text,
            review_cycle=review_cycle,
        )
        llm_metrics = llm_extract.get("metrics") or {}
        submitted_metrics = _merge_auto_metrics(
            llm_metrics if isinstance(llm_metrics, dict) else {},
        )
        llm_extract_meta = {
            "ok": bool(llm_extract.get("ok")),
            "source": llm_extract.get("source"),
            "model": llm_extract.get("model"),
            "summary": llm_extract.get("summary"),
            "error": llm_extract.get("error"),
            "auto_gap_metrics": auto_gap_metrics,
        }
    else:
        raise ReportServiceError("请提供 metrics 或 review_text", 400)

    metric_eval = _evaluate_review_metrics(expected_metrics, submitted_metrics)
    action_completion = summarize_plan_action_completion(report_obj, target_job_ids=scoped_job_ids)
    metric_eval["action_completion"] = copy.deepcopy(action_completion)
    metric_eval["has_action_evidence"] = bool(action_completion.get("has_completed_actions"))
    metric_eval["action_completion_rate"] = action_completion.get("completion_rate")

    eval_block_pre = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
    streaks = eval_block_pre.get("consecutive_fail_months_by_scope")
    if not isinstance(streaks, dict):
        streaks = {}
    streak_key = f"target:{job_id}" if scope == "target" else "all"
    prev_fail = int(streaks.get(streak_key) or 0)
    evidence_complete = bool(metric_eval.get("evidence_complete"))
    has_review_evidence = bool(metric_eval.get("has_evidence")) or bool(metric_eval.get("has_action_evidence"))
    all_passed = bool(metric_eval.get("all_passed"))
    failed_codes = metric_eval.get("failed_codes") or []
    if not evidence_complete:
        consecutive_fail_months = prev_fail
    elif all_passed:
        consecutive_fail_months = 0
    else:
        consecutive_fail_months = prev_fail + 1

    replan_mode = resolve_replan_mode(
        all_passed=all_passed,
        failed_codes=failed_codes,
        consecutive_fail_months=consecutive_fail_months,
        has_evidence=has_review_evidence,
    )
    if review_cycle == "monthly" and replan_mode == "insufficient":
        replan_mode = "continue"
    review_anchor_month = float(
        min(12, count_reviews(report_id, scope=scope, job_id=job_id, review_cycle="monthly") + 1)
    )
    if review_cycle == "monthly":
        adjust_detail = _build_auto_adjustment(
            report_obj,
            failed_codes,
            replan_mode=replan_mode,
            target_job_ids=scoped_job_ids,
            allow_llm=bool(metric_eval.get("has_evidence")),
        )
        if not has_review_evidence:
            adjust_detail["reason"] = "本月复盘已保存，但量化证据不足；按当前阶段延续并生成下一月基础安排"
    else:
        adjust_detail = {
            "triggered": False,
            "reason": "本次复盘缺少可核验的数值证据，已保存记录但未自动调整计划",
            "replan_mode": "insufficient",
            "failed_metric_codes": [],
            "focus_dimensions": [],
            "focus_labels": [],
            "extra_actions": [],
            "by_job": [],
            "llm_meta": {"enabled": False, "used": False, "error": "insufficient_evidence"},
        }
    adjust_detail["consecutive_fail_months"] = consecutive_fail_months
    adjustment_payload = {
        "scope": scope,
        "job_id": job_id,
        "all_passed": all_passed or (not metric_eval.get("has_evidence") and float(action_completion.get("completion_rate") or 0) >= 0.8),
        "pass_rate": metric_eval.get("pass_rate") if metric_eval.get("pass_rate") is not None else action_completion.get("completion_rate"),
        "failed_codes": failed_codes,
        "replan_mode": replan_mode,
        "consecutive_fail_months": consecutive_fail_months,
        "auto_adjustment": adjust_detail,
    }
    metrics_payload = {
        "submitted": submitted_metrics,
        "action_completion": action_completion,
        "review_text": stored_review_text or review_text,
        "llm_extract": llm_extract_meta,
        "evaluation": metric_eval,
    }

    now_stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    eval_block = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
    eval_block["latest_review"] = {
        "review_id": None,
        "review_cycle": review_cycle,
        "scope": scope,
        "job_id": job_id,
        "submitted_metrics": submitted_metrics or {},
        "action_completion": action_completion,
        "review_text": stored_review_text or review_text,
        "llm_extract": llm_extract_meta,
        "evaluation": metric_eval,
        "adjustment": adjustment_payload,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    report_obj["evaluation"] = eval_block
    if scope == "target" and job_id:
        latest_by_target = eval_block.get("latest_reviews_by_target")
        if not isinstance(latest_by_target, dict):
            latest_by_target = {}
            eval_block["latest_reviews_by_target"] = latest_by_target
        latest_by_target[job_id] = copy.deepcopy(eval_block["latest_review"])
    eval_block["adjust_rule_effective"] = bool(adjust_detail.get("triggered"))
    eval_block["latest_adjustment_actions"] = (adjust_detail.get("extra_actions") or [])[:3]
    eval_block["consecutive_fail_months"] = consecutive_fail_months
    streaks[streak_key] = consecutive_fail_months
    eval_block["consecutive_fail_months_by_scope"] = streaks
    eval_block["last_replan_mode"] = replan_mode
    _apply_auto_adjustment_to_report(
        report_obj,
        adjust_detail,
        stamp=now_stamp,
        review_anchor_month=review_anchor_month,
        replan_mode=replan_mode,
        metric_eval=metric_eval,
        target_job_ids=scoped_job_ids,
        include_global_growth=scope == "all",
    )
    attach_decision_support(
        report_obj,
        primary_job_id=str(row.get("primary_job_id") or ""),
    )

    rev_rows = list_review_metrics_asc(report_id)
    reviews_asc: List[Dict[str, Any]] = []
    for rr in rev_rows:
        mj = _parse_json_field(rr.get("metrics_json"), {})
        if not isinstance(mj, dict):
            mj = {}
        reviews_asc.append(
            {
                "review_id": int(rr["id"]),
                "review_cycle": rr.get("review_cycle") or "monthly",
                "scope": rr.get("scope") or "all",
                "job_id": rr.get("job_id"),
                "metrics": mj,
            }
        )
    reviews_asc.append(
        {
            "review_id": None,
            "review_cycle": review_cycle,
            "scope": scope,
            "job_id": job_id,
            "metrics": metrics_payload,
        }
    )
    _rebuild_development_timelines(report_obj, reviews_asc)
    review_id = commit_review_update(
        user_id=user_id,
        report_id=report_id,
        expected_version=int(row.get("report_version") or 1),
        report_obj=report_obj,
        review_cycle=review_cycle,
        scope=scope,
        job_id=job_id,
        metrics_payload=metrics_payload,
        adjustment_payload=adjustment_payload,
    )
    if review_id is None:
        raise ReportServiceError("报告已在其他操作中更新，请刷新后重新提交复盘", 409)

    return {
        "review_id": review_id,
        "report_id": report_id,
        "review_cycle": review_cycle,
        "scope": scope,
        "job_id": job_id,
        "evaluation": metric_eval,
        "adjustment": adjustment_payload,
        "submitted_metrics": submitted_metrics or {},
        "review_text": stored_review_text or review_text,
        "llm_extract": llm_extract_meta,
    }


def set_plan_action_done(user_id: int, report_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """切换下月计划行动项完成状态并持久化到 report_json。"""
    job_id = str(body.get("job_id") or "").strip()
    if not job_id:
        raise ReportServiceError("job_id 无效", 400)

    action_uid = str(body.get("action_uid") or "").strip() or None
    try:
        item_index = int(body.get("item_index")) if body.get("item_index") is not None else None
        action_index = int(body.get("action_index")) if body.get("action_index") is not None else None
    except (TypeError, ValueError) as exc:
        raise ReportServiceError("item_index 或 action_index 无效", 400) from exc
    if not action_uid and (item_index is None or action_index is None):
        raise ReportServiceError("action_uid 或行动位置必填", 400)

    if "done" not in body:
        raise ReportServiceError("done 必填", 400)
    done = bool(body.get("done"))

    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)

    report_obj = _parse_json_field(row.get("report_json"), {})
    if not isinstance(report_obj, dict):
        report_obj = {}

    try:
        result = apply_plan_action_done(
            report_obj,
            job_id=job_id,
            item_index=item_index,
            action_index=action_index,
            action_uid=action_uid,
            done=done,
        )
    except PlanActionProgressError as exc:
        raise ReportServiceError(str(exc), 404) from exc

    plan, _, action, resolved_item_index, resolved_action_index = locate_plan_action(
        report_obj, job_id=job_id, action_uid=result.get("action_uid")
    )
    plans = report_obj.get("plans_by_target") or []
    plan_index = next((index for index, candidate in enumerate(plans) if candidate is plan), -1)
    action_ref = str(action.get("action_uid") or build_stable_action_ref(job_id, action))
    if not commit_action_done_patch(
        user_id=user_id,
        report_id=report_id,
        expected_version=int(row.get("report_version") or 1),
        plan_index=plan_index,
        item_index=resolved_item_index,
        action_index=resolved_action_index,
        action_uid=action_ref,
        progress_key=str(result.get("progress_key") or ""),
        done=done,
        done_at=result.get("done_at"),
        event_type="action_completed" if done else "action_reopened",
        action_ref=action_ref,
        payload={
            "done": done,
            "done_at": result.get("done_at"),
            "job_id": job_id,
            "item_index": resolved_item_index,
            "action_index": resolved_action_index,
            "title": action.get("title") or action.get("text") or action.get("deliverable"),
            "kind": action.get("kind"),
            "deadline": action.get("deadline"),
            "effort_hours": action.get("effort_hours"),
        },
    ):
        raise ReportServiceError("报告已在其他操作中更新，请刷新后重试", 409)
    return {
        "report_id": report_id,
        "job_id": job_id,
        "item_index": resolved_item_index,
        "action_index": resolved_action_index,
        "action_ref": action_ref,
        "report_version": int(row.get("report_version") or 1) + 1,
        **result,
    }


_ACTION_EDIT_FIELDS = {
    "text", "kind", "deliverable", "deadline", "effort_hours", "acceptance_rule", "evidence_type"
}


def _clean_action_patch(body: Dict[str, Any], *, require_text: bool = False) -> Dict[str, Any]:
    patch: Dict[str, Any] = {}
    if "text" in body or "title" in body:
        text = storage_safe_text(
            str(body.get("text") or body.get("title") or "").strip(), kind="review", max_chars=150
        )
        if not text:
            raise ReportServiceError("行动标题不能为空", 400)
        patch["text"] = text
    elif require_text:
        raise ReportServiceError("行动标题不能为空", 400)
    if "kind" in body:
        kind = str(body.get("kind") or "practice").strip().lower()
        patch["kind"] = kind if kind in ("learn", "practice", "deliverable") else "practice"
    for field, max_len in (("deliverable", 180), ("deadline", 40), ("acceptance_rule", 220)):
        if field in body:
            patch[field] = storage_safe_text(
                str(body.get(field) or "").strip(), kind="review", max_chars=max_len
            )
    if "effort_hours" in body:
        try:
            patch["effort_hours"] = round(max(0.5, min(80.0, float(body.get("effort_hours")))), 1)
        except (TypeError, ValueError) as exc:
            raise ReportServiceError("预计投入小时数无效", 400) from exc
    if "evidence_type" in body:
        evidence_type = str(body.get("evidence_type") or "other").strip().lower()
        patch["evidence_type"] = evidence_type if evidence_type in ("project", "certificate", "feedback", "event", "other") else "other"
    return patch


def create_plan_action(user_id: int, report_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = str(body.get("job_id") or "").strip()
    try:
        item_index = int(body.get("item_index", 0))
    except (TypeError, ValueError) as exc:
        raise ReportServiceError("计划分组无效", 400) from exc
    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)
    report_obj = _parse_json_field(row.get("report_json"), {})
    plans = report_obj.get("plans_by_target") if isinstance(report_obj, dict) else []
    plan = next((p for p in plans or [] if isinstance(p, dict) and str(p.get("job_id") or "") == job_id), None)
    items = ((plan or {}).get("next_month_plan") or {}).get("items") or []
    if item_index < 0 or item_index >= len(items) or not isinstance(items[item_index], dict):
        raise ReportServiceError("计划分组不存在", 404)
    action = {
        "action_uid": new_user_action_uid(),
        "kind": "practice",
        "done": False,
        "user_created": True,
        **_clean_action_patch(body, require_text=True),
    }
    action.setdefault("deliverable", action["text"])
    action.setdefault("deadline", "本月内")
    action.setdefault("effort_hours", 2.0)
    action.setdefault("acceptance_rule", f"形成可查看、可复盘的成果：{action['deliverable']}")
    items[item_index].setdefault("custom_actions", []).append(action)
    ensure_action_ids(report_obj)
    attach_decision_support(report_obj, primary_job_id=str(row.get("primary_job_id") or ""))
    if not commit_action_progress_update(
        user_id=user_id, report_id=report_id, expected_version=int(row.get("report_version") or 1),
        report_obj=report_obj, event_type="action_created", action_ref=action["action_uid"],
        payload={"job_id": job_id, "item_index": item_index, "title": action["text"]},
    ):
        raise ReportServiceError("报告刚刚发生变化，请刷新后重试", 409)
    return {"report_id": report_id, "report_version": int(row.get("report_version") or 1) + 1, "action": action}


def update_plan_action(user_id: int, report_id: int, action_uid: str, body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = str(body.get("job_id") or "").strip()
    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)
    report_obj = _parse_json_field(row.get("report_json"), {})
    patch = _clean_action_patch(body)
    if not patch:
        raise ReportServiceError("没有可更新的行动字段", 400)
    try:
        _, _, action, item_index, action_index = locate_plan_action(report_obj, job_id=job_id, action_uid=action_uid)
    except PlanActionProgressError as exc:
        raise ReportServiceError(str(exc), 404) from exc
    action.update(patch)
    edited = set(str(value) for value in action.get("user_edited_fields") or [])
    edited.update(patch.keys())
    action["user_edited_fields"] = sorted(edited.intersection(_ACTION_EDIT_FIELDS))
    action["user_edited"] = True
    attach_decision_support(report_obj, primary_job_id=str(row.get("primary_job_id") or ""))
    if not commit_action_progress_update(
        user_id=user_id, report_id=report_id, expected_version=int(row.get("report_version") or 1),
        report_obj=report_obj, event_type="action_updated", action_ref=action_uid,
        payload={"job_id": job_id, "item_index": item_index, "action_index": action_index, "fields": sorted(patch)},
    ):
        raise ReportServiceError("报告刚刚发生变化，请刷新后重试", 409)
    return {"report_id": report_id, "report_version": int(row.get("report_version") or 1) + 1, "action": action}


def delete_plan_action(user_id: int, report_id: int, action_uid: str, body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = str(body.get("job_id") or "").strip()
    row = fetch_report_row(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)
    report_obj = _parse_json_field(row.get("report_json"), {})
    try:
        _, item, action, item_index, action_index = locate_plan_action(report_obj, job_id=job_id, action_uid=action_uid)
    except PlanActionProgressError as exc:
        raise ReportServiceError(str(exc), 404) from exc
    title = action.get("text") or action.get("title")
    del item["custom_actions"][action_index]
    if not action.get("user_created"):
        tombstones = report_obj.setdefault("user_action_tombstones", [])
        tombstones.append({
            "action_uid": action_uid,
            "job_id": job_id,
            "item_index": item_index,
            "action_index": action_index,
            "kind": action.get("kind"),
            "deleted_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        })
    report_obj.get("action_progress", {}).pop(action_uid, None)
    attach_decision_support(report_obj, primary_job_id=str(row.get("primary_job_id") or ""))
    if not commit_action_progress_update(
        user_id=user_id, report_id=report_id, expected_version=int(row.get("report_version") or 1),
        report_obj=report_obj, event_type="action_deleted", action_ref=action_uid,
        payload={"job_id": job_id, "item_index": item_index, "action_index": action_index, "title": title},
    ):
        raise ReportServiceError("报告刚刚发生变化，请刷新后重试", 409)
    return {"report_id": report_id, "report_version": int(row.get("report_version") or 1) + 1, "action_uid": action_uid, "deleted": True}


def export_career_report_data(user_id: int, report_id: int) -> Dict[str, Any]:
    bundle = fetch_report_privacy_bundle(user_id, report_id)
    if bundle is None:
        raise ReportServiceError("报告不存在或无权访问", 404)

    def safe(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [safe(item) for item in value]
        return value

    data = safe(bundle)
    data["exported_at"] = datetime.utcnow().isoformat() + "Z"
    data["policy"] = {
        "scope": "该报告及其目标、复盘、草稿、计划版本、证据、行动事件和实验分组",
        "unconfirmed_draft_retention_days": 90,
    }
    return data


def delete_career_report(user_id: int, report_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        confirmed_id = int(body.get("confirm_report_id"))
    except (TypeError, ValueError) as exc:
        raise ReportServiceError("删除前必须确认报告编号", 400) from exc
    if confirmed_id != report_id:
        raise ReportServiceError("确认的报告编号不匹配", 400)
    if not delete_user_report(user_id, report_id):
        raise ReportServiceError("报告不存在或无权访问", 404)
    return {"report_id": report_id, "deleted": True, "recoverable": False}


def get_career_report_operations_metrics() -> Dict[str, Any]:
    values = report_operations_metrics()
    drafts = int(values.get("draft_count") or 0)
    proposals = int(values.get("proposal_count") or 0)
    confirmed = int(values.get("confirmed_draft_count") or 0)
    accepted = int(values.get("accepted_proposal_count") or 0)
    experiment_rows = []
    for source in values.get("experiments") or []:
        row = dict(source)
        assignments = int(row.get("assignments") or 0)
        activated = int(row.get("activated_reports") or 0)
        review_count = int(row.get("review_count") or 0)
        row_proposals = int(row.get("proposal_count") or 0)
        row_accepted = int(row.get("accepted_proposal_count") or 0)
        completion_events = int(row.get("completion_event_count") or 0)
        experiment_rows.append(
            {
                **row,
                "assignments": assignments,
                "activated_reports": activated,
                "review_count": review_count,
                "proposal_count": row_proposals,
                "accepted_proposal_count": row_accepted,
                "completion_event_count": completion_events,
                "activation_rate": round(activated / assignments, 4) if assignments else None,
                "proposal_acceptance_rate": round(row_accepted / row_proposals, 4) if row_proposals else None,
                "completion_events_per_assignment": round(completion_events / assignments, 4) if assignments else None,
            }
        )
    return {
        **values,
        "experiments": experiment_rows,
        "draft_confirmation_rate": round(confirmed / drafts, 4) if drafts else None,
        "proposal_acceptance_rate": round(accepted / proposals, 4) if proposals else None,
        "definitions": {
            "draft_confirmation_rate": "已确认草稿 / 全部复盘草稿",
            "proposal_acceptance_rate": "已接受提案 / 全部计划提案",
            "active_reviewer_count_30d": "近 30 天至少提交一次正式复盘的去重用户数",
        },
    }
