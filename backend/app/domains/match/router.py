"""Person-job matching HTTP routes."""

from flask import Blueprint, current_app, jsonify, request

from app.core.security import get_bearer_user_id
from app.domains.match.services import run_match_preview
from app.domains.match.snapshots import fetch_match_run_detail, list_user_match_history
from app.domains.settings.service import active_system_settings, effective_preferences, use_settings

match_bp = Blueprint("match", __name__, url_prefix="/api/match")


def _require_user():
    uid = get_bearer_user_id()
    if uid is None:
        return None, (jsonify({"ok": False, "message": "请先登录"}), 401)
    return uid, None


def _schema_error_message(action: str, exc: Exception) -> str:
    text = str(exc)
    if "Unknown column" in text or "doesn't exist" in text or "1146" in text or "1054" in text:
        return f"{action}失败：数据库结构未升级，请先执行 alembic upgrade head 或运行 schema 体检"
    return f"{action}失败: {exc}"


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
        current_app.logger.exception("match_history_failed")
        return jsonify({"ok": False, "message": _schema_error_message("加载匹配历史", exc)}), 500
    return jsonify({"ok": True, "data": {"items": items}})


@match_bp.get("/history/<int:run_id>")
def get_match_history_detail(run_id: int):
    uid, err = _require_user()
    if err:
        return err
    try:
        data = fetch_match_run_detail(user_id=uid, run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("match_history_detail_failed")
        return jsonify({"ok": False, "message": _schema_error_message("加载匹配详情", exc)}), 500
    if not data:
        return jsonify({"ok": False, "message": "记录不存在或无权访问"}), 404
    return jsonify({"ok": True, "data": data})


@match_bp.post("/preview")
def match_preview():
    body = request.get_json(silent=True) or {}
    jwt_user_id = get_bearer_user_id()
    if jwt_user_id is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    system = active_system_settings()
    overrides = {key: body[key] for key in ("match_goal", "refine_with_llm") if key in body}
    resolved = effective_preferences(jwt_user_id, request_overrides=overrides, system_snapshot=system)
    body.setdefault("match_goal", resolved["effective"]["default_match_goal"])
    if not resolved["effective"].get("use_personality_in_match", True):
        body["preference_mode"] = "off"
    else:
        body.setdefault("preference_mode", resolved["effective"].get("default_preference_mode", "explain"))
    body["refine_with_llm"] = resolved["effective"]["default_refine_with_llm"]
    snapshot = dict(system["settings"])
    snapshot["MATCH_TOP_K_RETURN"] = resolved["effective"]["match_result_count"]
    body["_settings_revision"] = system.get("revision")
    body["_config_snapshot"] = snapshot
    with use_settings(snapshot):
        data_out, err, status = run_match_preview(body, jwt_user_id)
    if err:
        return jsonify({"ok": False, "message": err}), status
    return jsonify({"ok": True, "data": data_out})
