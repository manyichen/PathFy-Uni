"""生涯报告路由。"""
from __future__ import annotations

from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, make_response, request

from app.core.security import get_bearer_user_id
from app.db import db_cursor
from app.core.rate_limit import consume_rate_limit
from app.domains.report.services import (
    ReportServiceError,
    confirm_career_review_draft,
    create_career_review_draft,
    decide_career_plan_proposal,
    decide_report_preference_strategy,
    delete_career_report,
    export_career_report_pdf,
    export_career_report_data,
    enrich_career_report,
    generate_career_report,
    get_career_report_detail,
    get_career_report_operations_metrics,
    import_targets_from_match,
    list_career_report_reviews,
    list_career_plan_versions,
    list_career_reports,
    get_track_public_info,
    manual_search_targets,
    random_browse_targets,
    submit_career_review_cycle,
    create_plan_action,
    delete_plan_action,
    set_plan_action_done,
    update_plan_action,
)
from app.domains.report.enrichment_jobs import enqueue_report_enrichment, report_enrichment_status
from app.domains.report.utils import clamp_int
from app.domains.report.repository import get_report_config_snapshot
from app.domains.settings.service import active_system_settings, effective_preferences, use_settings

career_report_bp = Blueprint("career_report", __name__, url_prefix="/api/report")


def _require_user():
    uid = get_bearer_user_id()
    if uid is None:
        return None, (jsonify({"ok": False, "message": "请先登录"}), 401)
    return uid, None


def _require_admin():
    uid, err = _require_user()
    if err:
        return None, err
    with db_cursor() as (_, cur):
        cur.execute("SELECT is_admin FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
    if not row or not row.get("is_admin"):
        return None, (jsonify({"ok": False, "message": "无权限，仅管理员可查看运营指标"}), 403)
    return uid, None


def _unexpected_error_message(action: str, exc: Exception) -> str:
    text = str(exc)
    if "Unknown column" in text or "doesn't exist" in text or "1146" in text or "1054" in text:
        return f"{action}失败：数据库结构未升级，请先执行 alembic upgrade head 或运行 schema 体检"
    return f"{action}失败，请稍后重试"


def _rate_limited(user_id: int, scope: str, *, limit: int):
    retry_after = consume_rate_limit(
        scope,
        user_id,
        limit=limit,
        window_seconds=60,
    )
    if not retry_after:
        return None
    response = jsonify({"ok": False, "message": "请求过于频繁，请稍后重试"})
    response.headers["Retry-After"] = str(retry_after)
    return response, 429


@career_report_bp.post("/targets/import-from-match")
def import_targets_from_match_route():
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        data = import_targets_from_match(uid, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_import_targets_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("导入匹配目标", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/targets/manual-search")
def manual_search_targets_route():
    uid, err = _require_user()
    if err:
        return err
    limited = _rate_limited(uid, "report_target_search", limit=60)
    if limited:
        return limited
    body = request.get_json(silent=True) or {}
    try:
        data = manual_search_targets(body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_manual_search_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("搜索报告目标", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.get("/targets/random-browse")
def random_browse_targets_route():
    uid, err = _require_user()
    if err:
        return err
    limited = _rate_limited(uid, "report_target_random", limit=30)
    if limited:
        return limited
    seed = str(request.args.get("seed") or "").strip()
    page = clamp_int(request.args.get("page"), 1, 10000, 1)
    page_size = clamp_int(request.args.get("page_size"), 1, 50, 20)
    try:
        data = random_browse_targets(seed, page, page_size)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_random_browse_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("随机浏览报告目标", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/track-public-info")
def track_public_info_route():
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    resolved = effective_preferences(uid)
    if not resolved["effective"]["report_public_info"]:
        return jsonify({"ok": False, "message": "公开信息增强已被平台或用户偏好关闭"}), 403
    try:
        with use_settings(resolved["settings"]): data = get_track_public_info(body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_public_info_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("获取公开信息", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/generate")
def generate_report():
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    system = active_system_settings(); resolved = effective_preferences(uid, system_snapshot=system)
    effective = resolved["effective"]; snapshot = dict(system["settings"])
    snapshot.update({
        "CAREER_ENABLE_COPYWRITER": effective["report_copywriter"],
        "CAREER_ENABLE_PER_TARGET_COPYWRITER": effective["report_copywriter"],
        "CAREER_ENABLE_REPLAN_LLM": effective["report_auto_replan"],
        "CAREER_ENABLE_PUBLIC_INFO": effective["report_public_info"],
        "CAREER_ENABLE_GRAPH_RECOMMENDATIONS": effective["report_graph_recommendations"],
        "CAREER_ENABLE_RECOMMENDATION_LLM": effective["report_recommendation_llm"],
        "CAREER_LR_PER_TARGET": effective["learning_resource_count"],
        "CAREER_COMP_PER_TARGET": effective["competition_count"],
    })
    # The initial request must stay fast and deterministic. External model work
    # is queued only after the report skeleton has been persisted and returned.
    body["skip_llm_enrich"] = True
    body["_use_personality_in_report"] = bool(effective.get("use_personality_in_report", True))
    body["_settings_revision"] = system.get("revision"); body["_config_snapshot"] = snapshot
    try:
        with use_settings(snapshot): data = generate_career_report(uid, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_generate_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("报告生成", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/<int:report_id>/enrichment")
def start_report_enrichment(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    scope = str(body.get("scope") or "full").strip().lower()
    if scope not in ("full", "narrative", "resources", "plan"):
        return jsonify({"ok": False, "message": "scope 仅支持 full、narrative、resources 或 plan"}), 400
    try:
        job = enqueue_report_enrichment(current_app._get_current_object(), uid, report_id, scope=scope)
        if job is None:
            return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_enrichment_start_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("启动 AI 增强", exc)}), 500
    return jsonify({"ok": True, "data": {"report_id": report_id, **job}}), 202


@career_report_bp.get("/<int:report_id>/enrichment")
def get_report_enrichment_status_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        job = report_enrichment_status(uid, report_id)
        if job is None:
            return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_enrichment_status_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("读取 AI 增强状态", exc)}), 500
    return jsonify({"ok": True, "data": {"report_id": report_id, **job}})


@career_report_bp.post("/<int:report_id>/enrich")
def enrich_report_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    scope = str(body.get("scope") or "full").strip().lower()
    try:
        stored = get_report_config_snapshot(uid, report_id)
        with use_settings((stored or {}).get("settings") or active_system_settings()["settings"]):
            data = enrich_career_report(uid, report_id, refresh_scope=scope)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_enrich_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("AI 增强报告", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.get("/<int:report_id>")
def get_report_detail(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = get_career_report_detail(uid, report_id)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_detail_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("加载报告", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.patch("/<int:report_id>/preference-strategy")
def decide_preference_strategy_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = decide_report_preference_strategy(uid, report_id, request.get_json(silent=True) or {})
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_preference_strategy_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("更新执行方式建议", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.route("/<int:report_id>/export/pdf", methods=["GET", "POST"])
def export_report_pdf(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        export_options = request.get_json(silent=True) or {} if request.method == "POST" else None
        if export_options is not None and not isinstance(export_options, dict):
            return jsonify({"ok": False, "message": "PDF 导出参数格式不正确"}), 400
        pdf_bytes, filename = (
            export_career_report_pdf(uid, report_id, export_options)
            if export_options is not None
            else export_career_report_pdf(uid, report_id)
        )
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except RuntimeError as exc:
        current_app.logger.exception("career_report_pdf_runtime_failed")
        return jsonify({"ok": False, "message": "PDF 导出服务暂不可用，请稍后重试"}), 500
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_pdf_export_failed")
        return jsonify({"ok": False, "message": "PDF 导出失败，请稍后重试"}), 500

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename={filename}; filename*=UTF-8''{quote(filename)}"
    )
    return resp


@career_report_bp.get("/<int:report_id>/export/data")
def export_report_data_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = export_career_report_data(uid, report_id)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_data_export_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("导出报告数据", exc)}), 500
    response = jsonify({"ok": True, "data": data})
    response.headers["Content-Disposition"] = f'attachment; filename="career-report-{report_id}-data.json"'
    return response


@career_report_bp.delete("/<int:report_id>")
def delete_report_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = delete_career_report(uid, report_id, request.get_json(silent=True) or {})
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_delete_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("删除报告", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.get("/operations/metrics")
def report_operations_metrics_route():
    _, err = _require_admin()
    if err:
        return err
    try:
        data = get_career_report_operations_metrics()
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_operations_metrics_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("加载报告运营指标", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.get("/my/list")
def list_my_reports():
    uid, err = _require_user()
    if err:
        return err
    limit = clamp_int(request.args.get("limit"), 1, 50, 20)
    try:
        items = list_career_reports(uid, limit)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_list_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("加载历史报告", exc)}), 500
    return jsonify({"ok": True, "data": {"items": items}})


@career_report_bp.get("/<int:report_id>/reviews")
def list_report_reviews(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        items = list_career_report_reviews(uid, report_id)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_reviews_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("加载复盘记录", exc)}), 500
    return jsonify({"ok": True, "data": {"items": items}})


@career_report_bp.post("/review-cycle")
def submit_review_cycle():
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        stored = get_report_config_snapshot(uid, int(body.get("report_id") or 0))
        with use_settings((stored or {}).get("settings") or active_system_settings()["settings"]):
            data = submit_career_review_cycle(uid, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_review_cycle_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("提交复盘", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/review-drafts")
def create_review_draft_route():
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        stored = get_report_config_snapshot(uid, int(body.get("report_id") or 0))
        with use_settings((stored or {}).get("settings") or active_system_settings()["settings"]):
            data = create_career_review_draft(uid, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_review_draft_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("生成复盘草稿", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/review-drafts/<int:draft_id>/confirm")
def confirm_review_draft_route(draft_id: int):
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        data = confirm_career_review_draft(uid, draft_id, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_review_confirm_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("确认复盘", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.get("/<int:report_id>/plan-versions")
def list_plan_versions_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        items = list_career_plan_versions(uid, report_id)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_plan_versions_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("加载计划版本", exc)}), 500
    return jsonify({"ok": True, "data": {"items": items}})


@career_report_bp.post("/plan-proposals/<int:proposal_id>/decision")
def decide_plan_proposal_route(proposal_id: int):
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        data = decide_career_plan_proposal(uid, proposal_id, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_plan_proposal_decision_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("处理计划提案", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/<int:report_id>/plan-actions/done")
def set_plan_action_done_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        data = set_plan_action_done(uid, report_id, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_plan_action_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("更新计划动作", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/<int:report_id>/plan-actions")
def create_plan_action_route(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = create_plan_action(uid, report_id, request.get_json(silent=True) or {})
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_plan_action_create_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("添加计划行动", exc)}), 500
    return jsonify({"ok": True, "data": data}), 201


@career_report_bp.patch("/<int:report_id>/plan-actions/<path:action_uid>")
def update_plan_action_route(report_id: int, action_uid: str):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = update_plan_action(uid, report_id, action_uid, request.get_json(silent=True) or {})
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_plan_action_update_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("编辑计划行动", exc)}), 500
    return jsonify({"ok": True, "data": data})


@career_report_bp.delete("/<int:report_id>/plan-actions/<path:action_uid>")
def delete_plan_action_route(report_id: int, action_uid: str):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = delete_plan_action(uid, report_id, action_uid, request.get_json(silent=True) or {})
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("career_report_plan_action_delete_failed")
        return jsonify({"ok": False, "message": _unexpected_error_message("删除计划行动", exc)}), 500
    return jsonify({"ok": True, "data": data})
