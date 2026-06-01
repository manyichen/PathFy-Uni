"""生涯报告路由。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, make_response, request

from app.core.security import get_bearer_user_id
from app.db import db_cursor
from app.infrastructure.neo4j import serialize_job_row
from app.domains.match.llm_refine import refine_top5_deepseek
from app.domains.match.services import (
    _coarse_morphology_match,
    _fetch_jobs_for_match,
    _resolve_student_profile,
)
from app.domains.match.snapshots import load_recent_match_snapshot
from app.domains.report.growth import (
    _build_development_lines,
    _build_growth_plan,
    _rebuild_development_timelines,
    _seed_month_zero_adjustments,
)
from app.domains.report.helpers import (
    _build_report_export_html,
    _clamp_int,
    _json_dumps,
    _render_pdf_with_playwright,
    _truthy,
)
from app.domains.report.llm import _build_llm_summary
from app.domains.report.repository import (
    _ensure_report_tables,
    _query_job_relations,
    _query_jobs_by_ids,
)
from app.domains.report.review import (
    _apply_auto_adjustment_to_report,
    _build_auto_adjustment,
    _evaluate_review_metrics,
    _llm_extract_metrics_from_text,
)
from app.domains.report.targets import _build_match_ranked
from app.domains.report.trends import (
    _augment_trends_with_deepseek,
    _build_global_trend_for_target,
    _fetch_category_peer_jobs,
)

career_report_bp = Blueprint("career_report", __name__, url_prefix="/api/report")

@career_report_bp.post("/targets/import-from-match")
def import_targets_from_match():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录后导入目标职业"}), 401

    body = request.get_json(silent=True) or {}
    resume_id = body.get("resume_id")
    try:
        rid = int(resume_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "resume_id 无效"}), 400

    profile, err = _resolve_student_profile({"resume_id": rid}, uid)
    if err or not profile:
        return jsonify({"ok": False, "message": err or "画像读取失败"}), 400

    q = str(body.get("q") or "").strip()
    location_q = str(body.get("location_q") or "").strip()
    match_goal = str(body.get("match_goal") or "fit").strip().lower()
    if match_goal not in {"fit", "stretch"}:
        match_goal = "fit"
    limit = _clamp_int(body.get("limit"), 1, 5, 5)
    refine_with_llm = _truthy(body.get("refine_with_llm", True))

    selected: List[Dict[str, Any]]
    source = "match_coarse"

    # 优先读取最近一次匹配快照（与岗位匹配页结果保持一致）
    selected, source = load_recent_match_snapshot(
        user_id=uid,
        resume_id=rid,
        match_goal=match_goal,
        limit=limit,
    )

    if not selected:
        ranked = _build_match_ranked(profile, q, location_q, match_goal)
        pool = ranked[: max(limit, _clamp_int(current_app.config.get("MATCH_LLM_POOL_K", 40), 5, 100, 40))]
        if refine_with_llm:
            api_key = str(current_app.config.get("DEEPSEEK_API_KEY") or "").strip()
            if api_key:
                llm_payload, llm_err = refine_top5_deepseek(
                    profile,
                    pool,
                    api_key=api_key,
                    model=str(current_app.config.get("MATCH_DEEPSEEK_MODEL") or "deepseek-chat"),
                    timeout=float(current_app.config.get("MATCH_LLM_TIMEOUT_SECONDS") or 120.0),
                    match_goal=match_goal,
                )
                if not llm_err and llm_payload:
                    selected = []
                    for item in (llm_payload.get("top5") or [])[:limit]:
                        selected.append(
                            {
                                "job_id": item.get("job_id"),
                                "title": item.get("title"),
                                "company": item.get("company"),
                                "location": item.get("location"),
                                "salary": item.get("salary"),
                                "score_avg": item.get("coarse_match_score"),
                                "reason": item.get("one_line") or "",
                                "source": "match_llm",
                            }
                        )
                    source = "match_llm_recompute"
                else:
                    selected = []
            else:
                selected = []
        else:
            selected = []

    if not selected:
        ranked = _build_match_ranked(profile, q, location_q, match_goal)
        selected = [
            {
                "job_id": row.get("id"),
                "title": row.get("title"),
                "company": row.get("company"),
                "location": row.get("location"),
                "salary": row.get("salary"),
                "score_avg": (row.get("match_preview") or {}).get("match_score"),
                "reason": "基于画像与岗位八维需求匹配排序",
                "source": "match_coarse",
            }
            for row in ranked[:limit]
        ]
        source = "match_coarse_recompute"

    return jsonify(
        {
            "ok": True,
            "data": {
                "resume_id": rid,
                "match_goal": match_goal,
                "source": source,
                "targets": selected,
            },
        }
    )


@career_report_bp.post("/targets/manual-search")
def manual_search_targets():
    body = request.get_json(silent=True) or {}
    q = str(body.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "message": "请提供岗位关键词"}), 400
    location_q = str(body.get("location_q") or "").strip()
    limit = _clamp_int(body.get("limit"), 1, 30, 20)
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
    return jsonify({"ok": True, "data": {"targets": targets, "count": len(targets)}})


@career_report_bp.post("/generate")
def generate_report():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录后生成报告"}), 401
    body = request.get_json(silent=True) or {}

    resume_id = body.get("resume_id")
    try:
        rid = int(resume_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "resume_id 无效"}), 400

    profile, err = _resolve_student_profile({"resume_id": rid}, uid)
    if err or not profile:
        return jsonify({"ok": False, "message": err or "画像读取失败"}), 400

    raw_ids = body.get("target_job_ids")
    if not isinstance(raw_ids, list):
        return jsonify({"ok": False, "message": "target_job_ids 必须为数组"}), 400
    target_job_ids = [str(x).strip() for x in raw_ids if str(x).strip()]
    target_job_ids = list(dict.fromkeys(target_job_ids))
    if not target_job_ids:
        return jsonify({"ok": False, "message": "请至少选择 1 个目标职业"}), 400
    if len(target_job_ids) > 5:
        return jsonify({"ok": False, "message": "最多选择 5 个目标职业"}), 400

    target_cards = _query_jobs_by_ids(target_job_ids)
    found_ids = {str(x.get("id")) for x in target_cards}
    missing = [jid for jid in target_job_ids if jid not in found_ids]
    if missing:
        return jsonify({"ok": False, "message": f"存在无效 job_id: {', '.join(missing[:3])}"}), 400

    margin = float(current_app.config.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
    shape_w = float(current_app.config.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    target_insights: List[Dict[str, Any]] = []
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
        target_insights.append(
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

    trend_meta = _augment_trends_with_deepseek(target_insights)

    relations = _query_job_relations(target_job_ids)
    short_term, mid_term, metrics = _build_growth_plan(target_insights)
    lines = _build_development_lines(str(profile.get("display_name") or "候选人"), target_insights)
    llm_summary = _build_llm_summary(
        profile=profile,
        target_insights=target_insights,
        short_term=short_term,
        mid_term=mid_term,
    ) if _truthy(current_app.config.get("CAREER_ENABLE_COPYWRITER", True)) else {
        "provider": "disabled",
        "text": "",
    }

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
        "growth_plan": {
            "short_term": short_term,
            "mid_term": mid_term,
        },
        "evaluation": {
            "cycle": {"default": "monthly", "recommended": ["monthly"]},
            "metrics": metrics,
            "adjust_rule": "连续2个评估周期未达标时触发自动重规划",
        },
        "narrative": llm_summary,
        "trend_meta": trend_meta,
    }
    _seed_month_zero_adjustments(report_obj, stamp=stamp_compact)

    _ensure_report_tables()
    title = str(body.get("title") or "").strip() or f"生涯报告-{now[:10]}"
    primary_job_id = str(body.get("primary_job_id") or target_job_ids[0]).strip()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO career_reports (
              user_id, resume_id, title, primary_job_id, target_job_ids_json, report_json, meta_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uid,
                rid,
                title[:160],
                primary_job_id or None,
                _json_dumps(target_job_ids),
                _json_dumps(report_obj),
                _json_dumps(
                    {
                        "providers": {
                            "primary": current_app.config.get("CAREER_PRIMARY_PROVIDER"),
                            "secondary": current_app.config.get("CAREER_SECONDARY_PROVIDER"),
                            "copywriter": current_app.config.get("CAREER_COPYWRITER_PROVIDER"),
                        }
                    }
                ),
            ),
        )
        report_id = int(cur.lastrowid)
        for idx, target in enumerate(target_insights):
            job_id = str(target.get("id") or "").strip()
            if not job_id:
                continue
            cur.execute(
                """
                INSERT INTO career_report_targets (
                  report_id, job_id, title, is_primary, target_order, source, meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    report_id,
                    job_id,
                    str(target.get("title") or "")[:191] or None,
                    1 if job_id == primary_job_id else 0,
                    idx + 1,
                    "mixed",
                    _json_dumps(
                        {
                            "match_score": (target.get("match_preview") or {}).get("match_score"),
                            "trend": target.get("trend"),
                        }
                    ),
                ),
            )

    return jsonify(
        {
            "ok": True,
            "data": {
                "report_id": report_id,
                "title": title,
                "primary_job_id": primary_job_id,
                "target_job_ids": target_job_ids,
                "report": report_obj,
            },
        }
    )


@career_report_bp.get("/<int:report_id>")
def get_report_detail(report_id: int):
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, user_id, resume_id, title, primary_job_id, target_job_ids_json, report_json, created_at, updated_at
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, uid),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404
    try:
        target_ids = row.get("target_job_ids_json")
        if isinstance(target_ids, str):
            target_ids = json.loads(target_ids)
        report_obj = row.get("report_json")
        if isinstance(report_obj, str):
            report_obj = json.loads(report_obj)
    except Exception:  # noqa: BLE001
        target_ids = []
        report_obj = {}
    if isinstance(report_obj, dict):
        with db_cursor() as (_, cur2):
            cur2.execute(
                """
                SELECT id, metrics_json
                FROM career_report_reviews
                WHERE report_id = %s
                ORDER BY id ASC
                """,
                (report_id,),
            )
            rr_all = cur2.fetchall() or []
        rev_parse: List[Dict[str, Any]] = []
        for rr in rr_all:
            mj = rr.get("metrics_json")
            if isinstance(mj, str):
                try:
                    mj = json.loads(mj)
                except Exception:  # noqa: BLE001
                    mj = {}
            if not isinstance(mj, dict):
                mj = {}
            rev_parse.append({"review_id": int(rr["id"]), "metrics": mj})
        _rebuild_development_timelines(report_obj, rev_parse)
    return jsonify(
        {
            "ok": True,
            "data": {
                "report_id": int(row["id"]),
                "title": row.get("title"),
                "resume_id": row.get("resume_id"),
                "primary_job_id": row.get("primary_job_id"),
                "target_job_ids": target_ids or [],
                "report": report_obj or {},
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            },
        }
    )


@career_report_bp.get("/<int:report_id>/export/pdf")
def export_report_pdf(report_id: int):
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401

    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, title, report_json
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, uid),
        )
        row = cur.fetchone()

    if not row:
        return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404

    title = str(row.get("title") or "生涯报告")
    report_obj = row.get("report_json")
    if isinstance(report_obj, str):
        try:
            report_obj = json.loads(report_obj)
        except Exception:  # noqa: BLE001
            report_obj = {}
    if not isinstance(report_obj, dict):
        report_obj = {}

    try:
        html = _build_report_export_html(report_id=report_id, title=title, report_obj=report_obj)
        pdf_bytes = _render_pdf_with_playwright(html)
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "message": f"导出 PDF 失败: {exc}"}), 500

    filename = f"career_report_{report_id}.pdf"
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename={filename}; filename*=UTF-8''{quote(filename)}"
    )
    return resp


@career_report_bp.get("/my/list")
def list_my_reports():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    _ensure_report_tables()
    limit = _clamp_int(request.args.get("limit"), 1, 50, 20)
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, title, resume_id, primary_job_id, target_job_ids_json, created_at, updated_at
            FROM career_reports
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (uid, limit),
        )
        rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        target_ids = row.get("target_job_ids_json")
        if isinstance(target_ids, str):
            try:
                target_ids = json.loads(target_ids)
            except Exception:  # noqa: BLE001
                target_ids = []
        out.append(
            {
                "report_id": int(row["id"]),
                "title": row.get("title"),
                "resume_id": row.get("resume_id"),
                "primary_job_id": row.get("primary_job_id"),
                "target_job_ids": target_ids or [],
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            }
        )
    return jsonify({"ok": True, "data": {"items": out}})


@career_report_bp.get("/<int:report_id>/reviews")
def list_report_reviews(report_id: int):
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, uid),
        )
        if not cur.fetchone():
            return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404
        cur.execute(
            """
            SELECT id, review_cycle, metrics_json, adjustment_json, created_at
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id DESC
            LIMIT 80
            """,
            (report_id,),
        )
        rows = cur.fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        metrics = row.get("metrics_json")
        adjust = row.get("adjustment_json")
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except Exception:  # noqa: BLE001
                metrics = {}
        if isinstance(adjust, str):
            try:
                adjust = json.loads(adjust)
            except Exception:  # noqa: BLE001
                adjust = {}
        items.append(
            {
                "review_id": int(row["id"]),
                "review_cycle": row.get("review_cycle"),
                "metrics": metrics or {},
                "adjustment": adjust or {},
                "created_at": str(row.get("created_at") or ""),
            }
        )
    return jsonify({"ok": True, "data": {"items": items}})


@career_report_bp.post("/review-cycle")
def submit_review_cycle():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    body = request.get_json(silent=True) or {}
    report_id = body.get("report_id")
    try:
        rid = int(report_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "report_id 无效"}), 400
    # 固定按月复盘（与进步曲线横轴「第 n 月」一致）
    review_cycle = "monthly"
    submitted_metrics = body.get("metrics")
    review_text = str(body.get("review_text") or "").strip()
    if not isinstance(submitted_metrics, dict):
        submitted_metrics = None
    if not submitted_metrics and not review_text:
        return jsonify({"ok": False, "message": "请提供 metrics 或 review_text"}), 400

    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, report_json
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (rid, uid),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404

        report_obj = row.get("report_json")
        if isinstance(report_obj, str):
            try:
                report_obj = json.loads(report_obj)
            except Exception:  # noqa: BLE001
                report_obj = {}
        if not isinstance(report_obj, dict):
            report_obj = {}

        expected_metrics = (((report_obj.get("evaluation") or {}).get("metrics")) or [])
        if not isinstance(expected_metrics, list):
            expected_metrics = []

        llm_extract_meta: Dict[str, Any] = {}
        if not submitted_metrics:
            llm_extract = _llm_extract_metrics_from_text(
                report_obj=report_obj,
                review_text=review_text,
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

        cur.execute(
            "SELECT COUNT(*) AS c FROM career_report_reviews WHERE report_id = %s",
            (rid,),
        )
        cnt_row = cur.fetchone() or {}
        # 与折线上「第 n 月」复盘点对齐：本次提交为第 (已有条数+1) 月
        review_anchor_month = float(min(12, int(cnt_row.get("c") or 0) + 1))

        # 每次提交评估都生成重规划方案，并在发展线画布追加菱形节点
        adjust_detail = _build_auto_adjustment(report_obj, metric_eval.get("failed_codes") or [])
        adjustment_payload = {
            "all_passed": bool(metric_eval.get("all_passed")),
            "pass_rate": metric_eval.get("pass_rate"),
            "failed_codes": metric_eval.get("failed_codes") or [],
            "auto_adjustment": adjust_detail,
        }

        cur.execute(
            """
            INSERT INTO career_report_reviews (report_id, review_cycle, metrics_json, adjustment_json)
            VALUES (%s, %s, %s, %s)
            """,
            (
                rid,
                review_cycle,
                _json_dumps(
                    {
                        "submitted": submitted_metrics,
                        "review_text": review_text,
                        "llm_extract": llm_extract_meta,
                        "evaluation": metric_eval,
                    }
                ),
                _json_dumps(adjustment_payload),
            ),
        )
        review_id = int(cur.lastrowid)

        # 将评估摘要写回 report_json，便于前端直接读取
        now_stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        eval_block = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
        eval_block["latest_review"] = {
            "review_id": review_id,
            "review_cycle": review_cycle,
            "submitted_metrics": submitted_metrics or {},
            "review_text": review_text,
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

        cur.execute(
            """
            SELECT id, metrics_json
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id ASC
            """,
            (rid,),
        )
        rev_rows_all = cur.fetchall() or []
        reviews_asc: List[Dict[str, Any]] = []
        for rr in rev_rows_all:
            mj = rr.get("metrics_json")
            if isinstance(mj, str):
                try:
                    mj = json.loads(mj)
                except Exception:  # noqa: BLE001
                    mj = {}
            if not isinstance(mj, dict):
                mj = {}
            reviews_asc.append({"review_id": int(rr["id"]), "metrics": mj})
        _rebuild_development_timelines(report_obj, reviews_asc)

        cur.execute(
            """
            UPDATE career_reports
            SET report_json = %s
            WHERE id = %s
            """,
            (_json_dumps(report_obj), rid),
        )

    return jsonify(
        {
            "ok": True,
            "data": {
                "review_id": review_id,
                "report_id": rid,
                "review_cycle": review_cycle,
                "evaluation": metric_eval,
                "adjustment": adjustment_payload,
                "submitted_metrics": submitted_metrics or {},
                "review_text": review_text,
                "llm_extract": llm_extract_meta,
            },
        }
    )
