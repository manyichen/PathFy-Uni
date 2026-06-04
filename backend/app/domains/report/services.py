"""生涯报告业务编排。"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

from flask import current_app

from app.domains.match.services import (
    _coarse_morphology_match,
    _fetch_jobs_for_match,
    _resolve_student_profile,
)
from app.domains.match.snapshots import extract_targets_from_match_run
from app.domains.report.export import build_report_export_html, render_pdf_with_playwright
from app.domains.report.growth import (
    _build_development_lines,
    _build_growth_plan,
    _rebuild_development_timelines,
    _seed_month_zero_adjustments,
)
from app.domains.report.llm import _build_llm_summary
from app.domains.report.sanitize import sanitize_review_text_fields
from app.infrastructure.privacy import storage_safe_text
from app.domains.report.repository import (
    _parse_json_field,
    _query_all_jobs_browse_lite,
    _query_job_relations,
    _query_jobs_by_ids,
    count_reviews,
    fetch_report_for_export,
    fetch_report_row,
    insert_report,
    insert_review,
    list_review_metrics_asc,
    list_review_rows,
    fetch_report_json_by_ids,
    list_targets_for_reports,
    list_user_reports,
    report_owned_by_user,
    update_report_json,
)
from app.domains.report.review import (
    _apply_auto_adjustment_to_report,
    _build_auto_adjustment,
    _evaluate_review_metrics,
    _llm_extract_metrics_from_text,
)
from app.domains.report.trends import (
    _augment_trends_with_deepseek,
    _build_global_trend_for_target,
    _fetch_category_peer_jobs,
)
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
) -> List[Dict[str, Any]]:
    margin = float(current_app.config.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
    shape_w = float(current_app.config.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    target_cards = _query_jobs_by_ids(target_job_ids)
    found_ids = {str(x.get("id")) for x in target_cards}
    missing = [jid for jid in target_job_ids if jid not in found_ids]
    if missing:
        raise ReportServiceError(f"存在无效 job_id: {', '.join(missing[:3])}", 400)

    insights: List[Dict[str, Any]] = []
    for card in target_cards:
        peers = _fetch_category_peer_jobs(str(card.get("title") or ""), limit=50)
        ms, wg, gaps, shape_r = _coarse_morphology_match(
            profile["scores"],
            profile["confidences"],
            card["scores"],
            card["confidences"],
            soft_margin=margin,
            shape_weight=shape_w,
        )
        insights.append(
            {
                **card,
                "display_title": (
                    f"{str(card.get('title') or '目标岗位')} · {str(card.get('company') or '未知公司')}"
                ),
                "trend": _build_global_trend_for_target(card, peers),
                "match_preview": {
                    "match_score": ms,
                    "weighted_gap": wg,
                    "dimension_gaps": gaps,
                    "shape_correlation": shape_r,
                },
            }
        )
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

    target_insights = build_target_insights(profile, target_job_ids)
    trend_meta = _augment_trends_with_deepseek(target_insights)
    relations = _query_job_relations(target_job_ids)
    short_term, mid_term, metrics = _build_growth_plan(target_insights)
    lines = _build_development_lines(str(profile.get("display_name") or "候选人"), target_insights)
    llm_summary = (
        _build_llm_summary(
            profile=profile,
            target_insights=target_insights,
            short_term=short_term,
            mid_term=mid_term,
        )
        if truthy(current_app.config.get("CAREER_ENABLE_COPYWRITER", True))
        else {"provider": "disabled", "text": ""}
    )

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    stamp_compact = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    report_obj = {
        "generated_at": now,
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
        },
        "narrative": llm_summary,
        "trend_meta": trend_meta,
    }
    _seed_month_zero_adjustments(report_obj, stamp=stamp_compact)

    title = str(body.get("title") or "").strip() or f"生涯报告-{now[:10]}"
    primary_job_id = str(body.get("primary_job_id") or target_job_ids[0]).strip()
    meta_json = {
        "providers": {
            "primary": "deepseek",
            "copywriter": "doubao",
        }
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
    )

    return {
        "report_id": report_id,
        "title": title,
        "primary_job_id": primary_job_id,
        "target_job_ids": target_job_ids,
        "report": report_obj,
    }


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
        rev_rows = list_review_metrics_asc(report_id)
        rev_parse: List[Dict[str, Any]] = []
        for rr in rev_rows:
            mj = _parse_json_field(rr.get("metrics_json"), {})
            if not isinstance(mj, dict):
                mj = {}
            rev_parse.append({"review_id": int(rr["id"]), "metrics": mj})
        _rebuild_development_timelines(report_obj, rev_parse)

    sanitize_review_text_fields(report_obj)

    return {
        "report_id": int(row["id"]),
        "title": row.get("title"),
        "resume_id": row.get("resume_id"),
        "primary_job_id": row.get("primary_job_id"),
        "target_job_ids": target_ids or [],
        "report": report_obj or {},
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def export_career_report_pdf(user_id: int, report_id: int) -> Tuple[bytes, str]:
    row = fetch_report_for_export(user_id, report_id)
    if not row:
        raise ReportServiceError("报告不存在或无权访问", 404)

    title = str(row.get("title") or "生涯报告")
    report_obj = _parse_json_field(row.get("report_json"), {})
    if not isinstance(report_obj, dict):
        report_obj = {}

    html = build_report_export_html(report_id=report_id, title=title, report_obj=report_obj)
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
    json_fallback = fetch_report_json_by_ids(report_ids) if report_ids else {}

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
                    "metrics": metrics,
                    "adjustment": adjust,
                    "created_at": str(row.get("created_at") or ""),
                }
            )
        )
    return items


def submit_career_review_cycle(user_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
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

    expected_metrics = (((report_obj.get("evaluation") or {}).get("metrics")) or [])
    if not isinstance(expected_metrics, list):
        expected_metrics = []

    llm_extract_meta: Dict[str, Any] = {}
    if not submitted_metrics:
        llm_extract = _llm_extract_metrics_from_text(
            report_obj=report_obj,
            review_text=stored_review_text or review_text,
            review_cycle=review_cycle,
        )
        submitted_metrics = llm_extract.get("metrics") or {}
        llm_extract_meta = {
            "ok": bool(llm_extract.get("ok")),
            "source": llm_extract.get("source"),
            "model": llm_extract.get("model"),
            "summary": llm_extract.get("summary"),
            "error": llm_extract.get("error"),
        }
    metric_eval = _evaluate_review_metrics(expected_metrics, submitted_metrics or {})

    review_anchor_month = float(min(12, count_reviews(report_id) + 1))
    adjust_detail = _build_auto_adjustment(report_obj, metric_eval.get("failed_codes") or [])
    adjustment_payload = {
        "all_passed": bool(metric_eval.get("all_passed")),
        "pass_rate": metric_eval.get("pass_rate"),
        "failed_codes": metric_eval.get("failed_codes") or [],
        "auto_adjustment": adjust_detail,
    }

    review_id = insert_review(
        report_id=report_id,
        review_cycle=review_cycle,
        metrics_payload={
            "submitted": submitted_metrics,
            "review_text": stored_review_text or review_text,
            "llm_extract": llm_extract_meta,
            "evaluation": metric_eval,
        },
        adjustment_payload=adjustment_payload,
    )

    now_stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    eval_block = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
    eval_block["latest_review"] = {
        "review_id": review_id,
        "review_cycle": review_cycle,
        "submitted_metrics": submitted_metrics or {},
        "review_text": stored_review_text or review_text,
        "llm_extract": llm_extract_meta,
        "evaluation": metric_eval,
        "adjustment": adjustment_payload,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    report_obj["evaluation"] = eval_block
    eval_block["adjust_rule_effective"] = True
    eval_block["latest_adjustment_actions"] = (adjust_detail.get("extra_actions") or [])[:3]
    _apply_auto_adjustment_to_report(
        report_obj,
        adjust_detail,
        stamp=now_stamp,
        review_anchor_month=review_anchor_month,
    )

    rev_rows = list_review_metrics_asc(report_id)
    reviews_asc: List[Dict[str, Any]] = []
    for rr in rev_rows:
        mj = _parse_json_field(rr.get("metrics_json"), {})
        if not isinstance(mj, dict):
            mj = {}
        reviews_asc.append({"review_id": int(rr["id"]), "metrics": mj})
    _rebuild_development_timelines(report_obj, reviews_asc)
    update_report_json(report_id, report_obj)

    return {
        "review_id": review_id,
        "report_id": report_id,
        "review_cycle": review_cycle,
        "evaluation": metric_eval,
        "adjustment": adjustment_payload,
        "submitted_metrics": submitted_metrics or {},
        "review_text": stored_review_text or review_text,
        "llm_extract": llm_extract_meta,
    }
