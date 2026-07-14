from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from flask import current_app, g, has_app_context, has_request_context

from app.db import db_cursor
from app.core.config import Config
from app.domains.settings.defaults_v1 import DEFAULT_SETTINGS_V1
from app.domains.settings.registry import FIELD_MAP, USER_DEFAULTS, definitions, validate_preferences, validate_settings


class SettingsError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message); self.message = message; self.status = status


PLATFORM_DEFAULTS = {
    "PLATFORM_ALLOW_EXTERNAL_LLM": True,
    "PLATFORM_ALLOW_MATCH_LLM": True,
    "PLATFORM_ALLOW_REPORT_LLM": True,
    "GRAPH_CAPABILITY_BATCH_SIZE": 8,
}
SECRET_STATUS_KEYS = (
    "ARK_API_KEY", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "SERPER_API_KEY",
    "OCR_APP_ID", "OCR_API_KEY", "OCR_SECRET_KEY", "GRAPH_LLM_API_KEY",
)
_RUNTIME_SETTINGS: ContextVar[dict[str, Any] | None] = ContextVar("pathfy_runtime_settings", default=None)


def legacy_settings() -> dict[str, Any]:
    config = current_app.config if has_app_context() else Config
    values = {key: (config.get(key, PLATFORM_DEFAULTS.get(key)) if hasattr(config, "get") else getattr(config, key, PLATFORM_DEFAULTS.get(key))) for key in FIELD_MAP}
    replacements = {
        "MATCH_DEEPSEEK_MODEL": "deepseek-v4-flash",
        "CAREER_DEEPSEEK_MODEL": "deepseek-v4-pro",
        "GRAPH_CAP_PRIMARY_MODEL": "deepseek-v4-flash",
    }
    for key, replacement in replacements.items():
        if values.get(key) == "deepseek-chat":
            values[key] = replacement
        elif values.get(key) == "deepseek-reasoner":
            values[key] = "deepseek-v4-pro"
    return values


def _decode_settings(row: dict | None) -> dict | None:
    if not row: return None
    raw = row.get("settings_json")
    values = json.loads(raw) if isinstance(raw, str) else raw
    return {"id": row.get("id"), "revision": int(row.get("revision") or 0), "settings": values or {},
            "created_by": row.get("created_by"), "created_at": row.get("created_at")}


def active_system_settings() -> dict[str, Any]:
    if not has_app_context():
        return {"revision": None, "source": "legacy_env", "settings": legacy_settings()}
    if has_request_context() and getattr(g, "pathfy_system_settings", None) is not None:
        return g.pathfy_system_settings
    try:
        with db_cursor() as (_, cur):
            cur.execute("""SELECT r.id,r.revision,r.settings_json,r.created_by,r.created_at
                           FROM system_setting_state s LEFT JOIN system_setting_revisions r ON r.id=s.current_revision_id
                           WHERE s.id=1""")
            revision = _decode_settings(cur.fetchone())
    except Exception:
        revision = None
    result = ({"revision": None, "source": "legacy_env", "settings": legacy_settings()}
              if not revision else {**revision, "source": "database"})
    if has_request_context(): g.pathfy_system_settings = result
    return result


def setting(key: str, default: Any = None) -> Any:
    snapshot = _RUNTIME_SETTINGS.get()
    if snapshot is not None and key in snapshot: return snapshot[key]
    if key in FIELD_MAP: return active_system_settings()["settings"].get(key, default)
    return current_app.config.get(key, default) if has_app_context() else getattr(Config, key, default)


class _SettingsView:
    def __init__(self, base, overlay: dict[str, Any]): self.base = base; self.overlay = overlay
    def get(self, key: str, default: Any = None) -> Any:
        if key in self.overlay: return self.overlay[key]
        if hasattr(self.base, "get"): return self.base.get(key, default)
        return getattr(self.base, key, default)


def settings_view(snapshot: dict[str, Any] | None = None, *, base=None):
    base_config = base or (current_app.config if has_app_context() else Config)
    overlay = snapshot or _RUNTIME_SETTINGS.get() or active_system_settings()["settings"]
    return _SettingsView(base_config, overlay)


@contextmanager
def use_settings(snapshot: dict[str, Any]):
    token = _RUNTIME_SETTINGS.set(dict(snapshot))
    try: yield
    finally: _RUNTIME_SETTINGS.reset(token)


def publish_settings(values: dict[str, Any], *, base_revision: int | None, user_id: int | None) -> dict[str, Any]:
    try:
        normalized = validate_settings(values, hard_scan_cap=int(current_app.config["MATCH_PREVIEW_MAX_SCAN_HARD"]))
    except (TypeError, ValueError) as exc:
        raise SettingsError(str(exc)) from exc
    with db_cursor() as (_, cur):
        cur.execute("SELECT current_revision_id FROM system_setting_state WHERE id=1 FOR UPDATE")
        state = cur.fetchone() or {}
        current_id = state.get("current_revision_id")
        current_revision = None
        if current_id:
            cur.execute("SELECT revision FROM system_setting_revisions WHERE id=%s", (current_id,))
            row = cur.fetchone() or {}; current_revision = int(row.get("revision") or 0)
        if current_revision != base_revision:
            raise SettingsError("系统设置已被其他管理员更新，请刷新后重试", 409)
        next_revision = (current_revision or 0) + 1
        cur.execute("INSERT INTO system_setting_revisions (revision,settings_json,created_by) VALUES (%s,%s,%s)",
                    (next_revision, json.dumps(normalized, ensure_ascii=False, separators=(",", ":")), user_id))
        revision_id = int(cur.lastrowid)
        cur.execute("UPDATE system_setting_state SET current_revision_id=%s WHERE id=1", (revision_id,))
    return {"revision": next_revision, "settings": normalized, "source": "database"}


def revision_detail(revision: int) -> dict[str, Any]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT id,revision,settings_json,created_by,created_at FROM system_setting_revisions WHERE revision=%s", (revision,))
        item = _decode_settings(cur.fetchone())
    if not item: raise SettingsError("配置版本不存在", 404)
    return item


def settings_history(page: int, page_size: int) -> dict[str, Any]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT COUNT(*) AS total FROM system_setting_revisions"); total = int((cur.fetchone() or {}).get("total") or 0)
        cur.execute("""SELECT r.id,r.revision,r.settings_json,r.created_by,r.created_at,u.username
                       FROM system_setting_revisions r LEFT JOIN users u ON u.id=r.created_by
                       ORDER BY r.revision DESC LIMIT %s OFFSET %s""", (page_size, (page - 1) * page_size))
        rows = cur.fetchall()
        previous_revisions = [int(row["revision"]) - 1 for row in rows if int(row["revision"]) > 1]
        previous: dict[int, dict[str, Any]] = {}
        if previous_revisions:
            placeholders = ",".join(["%s"] * len(previous_revisions))
            cur.execute(
                f"SELECT revision,settings_json FROM system_setting_revisions WHERE revision IN ({placeholders})",
                tuple(previous_revisions),
            )
            for row in cur.fetchall():
                raw = row.get("settings_json")
                previous[int(row["revision"])] = json.loads(raw) if isinstance(raw, str) else (raw or {})
    items = []
    for row in rows:
        item = _decode_settings(row) or {}
        current_values = item.pop("settings", {})
        old_values = previous.get(int(item["revision"]) - 1, {})
        item["changes"] = [
            {"key": key, "before": old_values.get(key), "after": current_values.get(key)}
            for key in sorted(current_values)
            if old_values.get(key) != current_values.get(key)
        ]
        item["username"] = row.get("username")
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def preference_record(user_id: int) -> dict[str, Any]:
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT version,preferences_json,updated_at FROM user_preferences WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
    except Exception:
        row = None
    stored = {}
    if row:
        raw = row.get("preferences_json"); stored = json.loads(raw) if isinstance(raw, str) else (raw or {})
    return {"version": int((row or {}).get("version") or 0), "preferences": {**USER_DEFAULTS, **stored},
            "stored": bool(row), "updated_at": (row or {}).get("updated_at")}


def effective_preferences(user_id: int, *, request_overrides: dict[str, Any] | None = None,
                          system_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    system = system_snapshot or active_system_settings()
    settings = system["settings"]
    record = preference_record(user_id); prefs = record["preferences"]
    overrides = request_overrides or {}
    if "match_goal" in overrides: prefs["default_match_goal"] = "stretch" if overrides["match_goal"] == "stretch" else "fit"
    if "refine_with_llm" in overrides: prefs["default_refine_with_llm"] = bool(overrides["refine_with_llm"])
    allow_external = bool(settings["PLATFORM_ALLOW_EXTERNAL_LLM"] and prefs["allow_external_llm"])
    effective = {**prefs, "allow_external_llm": allow_external}
    effective["default_refine_with_llm"] = bool(allow_external and settings["PLATFORM_ALLOW_MATCH_LLM"] and prefs["default_refine_with_llm"])
    effective["match_result_count"] = min(int(prefs["match_result_count"]), int(settings["MATCH_TOP_K_RETURN"]))
    report_allowed = bool(allow_external and settings["PLATFORM_ALLOW_REPORT_LLM"])
    effective["report_copywriter"] = bool(report_allowed and settings["CAREER_ENABLE_COPYWRITER"] and prefs["report_copywriter"])
    effective["report_public_info"] = bool(report_allowed and settings["CAREER_ENABLE_PUBLIC_INFO"] and prefs["report_public_info"])
    effective["report_auto_replan"] = bool(report_allowed and settings["CAREER_ENABLE_REPLAN_LLM"] and prefs["report_auto_replan"])
    effective["report_graph_recommendations"] = bool(settings["CAREER_ENABLE_GRAPH_RECOMMENDATIONS"] and prefs["report_graph_recommendations"])
    effective["report_recommendation_llm"] = bool(report_allowed and settings["CAREER_ENABLE_RECOMMENDATION_LLM"] and prefs["report_recommendation_llm"])
    effective["learning_resource_count"] = min(int(prefs["learning_resource_count"]), int(settings["CAREER_LR_PER_TARGET"]))
    effective["competition_count"] = min(int(prefs["competition_count"]), int(settings["CAREER_COMP_PER_TARGET"]))
    return {"revision": system.get("revision"), "settings": settings, "preferences": prefs, "effective": effective,
            "preference_version": record["version"], "stored": record["stored"]}


def save_preferences(user_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    try: clean = validate_preferences(patch)
    except (TypeError, ValueError) as exc: raise SettingsError(str(exc)) from exc
    current = preference_record(user_id); merged = {**current["preferences"], **clean}; next_version = current["version"] + 1
    with db_cursor() as (_, cur):
        cur.execute("""INSERT INTO user_preferences (user_id,version,preferences_json) VALUES (%s,%s,%s)
                       ON DUPLICATE KEY UPDATE version=VALUES(version),preferences_json=VALUES(preferences_json)""",
                    (user_id, next_version, json.dumps(merged, ensure_ascii=False, separators=(",", ":"))))
    return {"version": next_version, **effective_preferences(user_id)}


def user_preferences_payload(data: dict[str, Any]) -> dict[str, Any]:
    settings = data["settings"]
    return {
        "revision": data.get("revision"), "preference_version": data.get("preference_version", data.get("version", 0)),
        "stored": data.get("stored", True), "preferences": data["preferences"], "effective": data["effective"],
        "limits": {"match_result_count": int(settings["MATCH_TOP_K_RETURN"]),
                   "learning_resource_count": int(settings["CAREER_LR_PER_TARGET"]),
                   "competition_count": int(settings["CAREER_COMP_PER_TARGET"])},
        "capabilities": {"external_llm": bool(settings["PLATFORM_ALLOW_EXTERNAL_LLM"]),
                         "match_llm": bool(settings["PLATFORM_ALLOW_MATCH_LLM"]),
                         "report_llm": bool(settings["PLATFORM_ALLOW_REPORT_LLM"])},
    }


def admin_payload() -> dict[str, Any]:
    active = active_system_settings()
    field_definitions = definitions()
    hard_scan = int(current_app.config["MATCH_PREVIEW_MAX_SCAN_HARD"])
    for item in field_definitions:
        if item["key"] == "MATCH_PREVIEW_MAX_SCAN": item["maximum"] = hard_scan
    return {**active, "definitions": field_definitions, "defaults": dict(DEFAULT_SETTINGS_V1),
            "hard_limits": {"MATCH_PREVIEW_MAX_SCAN_HARD": int(current_app.config["MATCH_PREVIEW_MAX_SCAN_HARD"]),
                            "MAX_UPLOAD_MB": int(current_app.config["MAX_UPLOAD_MB"])},
            "credential_status": {key: bool(current_app.config.get(key)) for key in SECRET_STATUS_KEYS}}
