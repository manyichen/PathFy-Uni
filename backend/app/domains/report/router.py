"""生涯报告路由。"""
from __future__ import annotations

from urllib.parse import quote

from flask import Blueprint, jsonify, make_response, request

from app.core.security import get_bearer_user_id
from app.domains.report.services import (
    ReportServiceError,
    export_career_report_pdf,
    generate_career_report,
    get_career_report_detail,
    import_targets_from_match,
    list_career_report_reviews,
    list_career_reports,
    manual_search_targets,
    random_browse_targets,
    submit_career_review_cycle,
)
from app.domains.report.utils import clamp_int

career_report_bp = Blueprint("career_report", __name__, url_prefix="/api/report")


def _require_user():
    uid = get_bearer_user_id()
    if uid is None:
        return None, (jsonify({"ok": False, "message": "请先登录"}), 401)
    return uid, None


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
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/targets/manual-search")
def manual_search_targets_route():
    body = request.get_json(silent=True) or {}
    try:
        data = manual_search_targets(body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    return jsonify({"ok": True, "data": data})


@career_report_bp.get("/targets/random-browse")
def random_browse_targets_route():
    seed = str(request.args.get("seed") or "").strip()
    page = clamp_int(request.args.get("page"), 1, 10000, 1)
    page_size = clamp_int(request.args.get("page_size"), 1, 50, 20)
    try:
        data = random_browse_targets(seed, page, page_size)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    return jsonify({"ok": True, "data": data})


@career_report_bp.post("/generate")
def generate_report():
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        data = generate_career_report(uid, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
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
    return jsonify({"ok": True, "data": data})


@career_report_bp.get("/<int:report_id>/export/pdf")
def export_report_pdf(report_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        pdf_bytes, filename = export_career_report_pdf(uid, report_id)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "message": f"导出 PDF 失败: {exc}"}), 500

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename={filename}; filename*=UTF-8''{quote(filename)}"
    )
    return resp


@career_report_bp.get("/my/list")
def list_my_reports():
    uid, err = _require_user()
    if err:
        return err
    limit = clamp_int(request.args.get("limit"), 1, 50, 20)
    items = list_career_reports(uid, limit)
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
    return jsonify({"ok": True, "data": {"items": items}})


@career_report_bp.post("/review-cycle")
def submit_review_cycle():
    uid, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        data = submit_career_review_cycle(uid, body)
    except ReportServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    return jsonify({"ok": True, "data": data})
