from __future__ import annotations

import pytest

from app.domains.settings import registry, service
from app.domains.settings import router as settings_router


def test_registry_rejects_unknown_missing_and_invalid_weights(app):
    with app.app_context():
        values = dict(registry.DEFAULT_SETTINGS_V1)
        assert registry.validate_settings(values, hard_scan_cap=8000)["MATCH_TOP_K_RETURN"] > 0
        with pytest.raises(ValueError, match="未知设置"):
            registry.validate_settings({**values, "SECRET_KEY": "leak"}, hard_scan_cap=8000)
        with pytest.raises(ValueError, match="权重之和"):
            registry.validate_settings({**values, "MATCH_STRETCH_SORT_W_MATCH": 0.9}, hard_scan_cap=8000)


def test_database_defaults_are_complete_and_use_current_deepseek_models():
    defaults = registry.DEFAULT_SETTINGS_V1
    assert set(defaults) == set(registry.FIELD_MAP)
    assert registry.validate_settings(defaults, hard_scan_cap=8000) == defaults
    assert defaults["MATCH_DEEPSEEK_MODEL"] == "deepseek-v4-flash"
    assert defaults["CAREER_DEEPSEEK_MODEL"] == "deepseek-v4-pro"
    assert defaults["GRAPH_CAP_PRIMARY_MODEL"] == "deepseek-v4-flash"


def test_legacy_environment_models_are_mapped_to_supported_names(app):
    with app.app_context():
        values = service.legacy_settings()
    assert values["MATCH_DEEPSEEK_MODEL"] in {"deepseek-v4-flash", "deepseek-v4-pro"}
    assert values["CAREER_DEEPSEEK_MODEL"] in {"deepseek-v4-flash", "deepseek-v4-pro"}
    assert values["GRAPH_CAP_PRIMARY_MODEL"] in {"deepseek-v4-flash", "deepseek-v4-pro"}


def test_effective_preferences_can_only_tighten_platform(monkeypatch):
    system = {"revision": 4, "settings": {**{key: 1 for key in registry.FIELD_MAP},
        "PLATFORM_ALLOW_EXTERNAL_LLM": False, "PLATFORM_ALLOW_MATCH_LLM": True,
        "PLATFORM_ALLOW_REPORT_LLM": True, "MATCH_TOP_K_RETURN": 20,
        "CAREER_ENABLE_COPYWRITER": True, "CAREER_ENABLE_PUBLIC_INFO": True,
        "CAREER_ENABLE_REPLAN_LLM": True, "CAREER_ENABLE_GRAPH_RECOMMENDATIONS": True,
        "CAREER_ENABLE_RECOMMENDATION_LLM": True, "CAREER_LR_PER_TARGET": 6,
        "CAREER_COMP_PER_TARGET": 3}}
    monkeypatch.setattr(service, "preference_record", lambda _uid: {"version": 1, "stored": True, "updated_at": None,
        "preferences": {**registry.USER_DEFAULTS, "allow_external_llm": True, "default_refine_with_llm": True, "match_result_count": 99}})
    result = service.effective_preferences(7, system_snapshot=system)["effective"]
    assert result["allow_external_llm"] is False
    assert result["default_refine_with_llm"] is False
    assert result["report_copywriter"] is False
    assert result["match_result_count"] == 20


def test_user_payload_does_not_expose_admin_algorithm_or_secrets():
    settings = {**{key: 1 for key in registry.FIELD_MAP}, "MATCH_TOP_K_RETURN": 20,
                "CAREER_LR_PER_TARGET": 6, "CAREER_COMP_PER_TARGET": 3,
                "PLATFORM_ALLOW_EXTERNAL_LLM": True, "PLATFORM_ALLOW_MATCH_LLM": True,
                "PLATFORM_ALLOW_REPORT_LLM": True}
    data = {"revision": 2, "preference_version": 1, "stored": True,
            "settings": settings, "preferences": registry.USER_DEFAULTS, "effective": registry.USER_DEFAULTS}
    payload = service.user_preferences_payload(data)
    assert "settings" not in payload
    assert "MATCH_COARSE_SHAPE_WEIGHT" not in str(payload)
    assert payload["limits"]["match_result_count"] == 20


@pytest.fixture()
def settings_api_admin(monkeypatch):
    monkeypatch.setattr(settings_router, "_admin", lambda: (7, None))
    monkeypatch.setattr(settings_router, "_user", lambda: (7, None))


def test_settings_api_never_accepts_arbitrary_keys(client, monkeypatch, settings_api_admin):
    captured = {}
    monkeypatch.setattr(settings_router, "admin_payload", lambda: {"revision": None, "credential_status": {"DEEPSEEK_API_KEY": True}})
    monkeypatch.setattr(settings_router, "publish_settings", lambda values, **kwargs: captured.update(values=values, **kwargs) or {"revision": 1})
    body = client.get("/api/admin/settings").get_json()["data"]
    assert body == {"revision": None, "credential_status": {"DEEPSEEK_API_KEY": True}}
    response = client.post("/api/admin/settings/publish", json={"base_revision": None, "settings": {"MATCH_TOP_K_RETURN": 20}})
    assert response.status_code == 200
    assert captured["user_id"] == 7


def test_settings_migration_contains_snapshots():
    source = open("migrations/versions/20260715_0004_settings_layers.py", encoding="utf-8").read()
    assert "CREATE TABLE system_setting_revisions" in source
    assert "CREATE TABLE user_preferences" in source
    assert "config_snapshot_json" in source
    seed_source = open("migrations/versions/20260715_0005_seed_system_settings.py", encoding="utf-8").read()
    assert "DEFAULT_SETTINGS_V1" in seed_source
    assert "deepseek-v4-flash" in seed_source
    assert "deepseek-v4-pro" in seed_source
