"""人岗匹配 HTTP 路由。"""

from flask import Blueprint, jsonify, request

from app.core.security import get_bearer_user_id
from app.domains.match.services import run_match_preview
from app.domains.match.snapshots import fetch_match_run_detail, list_user_match_history

match_bp = Blueprint("match", __name__, url_prefix="/api/match")


def _require_user():
    uid = get_bearer_user_id()
    if uid is None:
        return None, (jsonify({"ok": False, "message": "请先登录"}), 401)
    return uid, None


@match_bp.get("/history")
def list_match_history():
    uid, err = _require_user()
    if err:
        return err
    try:
        limit = int(request.args.get("limit", 30))
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, min(limit, 80))
    try:
        items = list_user_match_history(user_id=uid, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "message": f"加载匹配历史失败: {exc}"}), 500
    return jsonify({"ok": True, "data": {"items": items}})


@match_bp.get("/history/<int:run_id>")
def get_match_history_detail(run_id: int):
    uid, err = _require_user()
    if err:
        return err
    data = fetch_match_run_detail(user_id=uid, run_id=run_id)
    if not data:
        return jsonify({"ok": False, "message": "记录不存在或无权访问"}), 404
    return jsonify({"ok": True, "data": data})


@match_bp.post("/preview")
def match_preview():
    body = request.get_json(silent=True) or {}
    jwt_user_id = get_bearer_user_id()
    data_out, err, status = run_match_preview(body, jwt_user_id)
    if err:
        return jsonify({"ok": False, "message": err}), status
    return jsonify({"ok": True, "data": data_out})
