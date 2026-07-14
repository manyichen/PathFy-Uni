from flask import Blueprint, jsonify, request

from app.core.security import get_bearer_user_id
from app.db import db_cursor
from app.domains.settings.service import (
    SettingsError, active_system_settings, admin_payload, effective_preferences,
    publish_settings, revision_detail, save_preferences, settings_history, user_preferences_payload,
)

settings_bp = Blueprint("settings", __name__, url_prefix="/api")


def _user():
    uid = get_bearer_user_id()
    return (uid, None) if uid is not None else (None, (jsonify({"ok": False, "message": "请先登录"}), 401))


def _admin():
    uid, err = _user()
    if err: return None, err
    with db_cursor() as (_, cur):
        cur.execute("SELECT is_admin FROM users WHERE id=%s", (uid,)); row = cur.fetchone()
    if not row or not row.get("is_admin"): return None, (jsonify({"ok": False, "message": "无权限，仅管理员可操作"}), 403)
    return uid, None


@settings_bp.get("/admin/settings")
def get_admin_settings():
    _, err = _admin()
    if err: return err
    return jsonify({"ok": True, "data": admin_payload()})


@settings_bp.post("/admin/settings/publish")
def publish_admin_settings():
    uid, err = _admin()
    if err: return err
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "data": publish_settings(body.get("settings") or {}, base_revision=body.get("base_revision"), user_id=uid)})
    except SettingsError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status


@settings_bp.get("/admin/settings/history")
def admin_settings_history():
    _, err = _admin()
    if err: return err
    try:
        page = max(1, int(request.args.get("page") or 1)); size = max(1, min(int(request.args.get("page_size") or 20), 100))
    except ValueError: return jsonify({"ok": False, "message": "分页参数格式错误"}), 400
    return jsonify({"ok": True, "data": settings_history(page, size)})


@settings_bp.get("/admin/settings/revisions/<int:revision>")
def admin_settings_revision(revision: int):
    _, err = _admin()
    if err: return err
    try: return jsonify({"ok": True, "data": revision_detail(revision)})
    except SettingsError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status


@settings_bp.get("/account/preferences")
def get_preferences():
    uid, err = _user()
    if err: return err
    return jsonify({"ok": True, "data": user_preferences_payload(effective_preferences(uid))})


@settings_bp.patch("/account/preferences")
def patch_preferences():
    uid, err = _user()
    if err: return err
    try: return jsonify({"ok": True, "data": user_preferences_payload(save_preferences(uid, request.get_json(silent=True) or {}))})
    except SettingsError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status
