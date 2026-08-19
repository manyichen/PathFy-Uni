from flask import Flask

from app.domains.match import services
from app.infrastructure.neo4j import CONF_KEYS, DIM_KEYS


def _student():
    return {
        "id": "1",
        "display_name": "测试画像",
        "scores": {key: 60.0 for key in DIM_KEYS},
        "confidences": {key: 0.7 for key in CONF_KEYS},
    }


def _job(job_id: str, score: float):
    return {
        "id": job_id,
        "title": job_id,
        "company": "公司",
        "location": "上海",
        "salary": "面议",
        "scores": {key: score for key in DIM_KEYS},
        "confidences": {key: 0.7 for key in CONF_KEYS},
        "score_avg": score,
        "conf_avg": 70,
    }


def _prepare(monkeypatch):
    monkeypatch.setattr(services, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(services, "_resolve_student_profile", lambda *_args: (_student(), None))
    monkeypatch.setattr(services, "_fetch_jobs_for_match", lambda **_kwargs: [_job("job-high", 62), _job("job-low", 90)])
    monkeypatch.setattr(services, "serialize_job_row", lambda row: row)
    monkeypatch.setattr(services, "setting", lambda _name, default=None: default)
    monkeypatch.setattr(services, "settings_view", lambda: {})


def test_explain_mode_attaches_context_without_changing_ranking(monkeypatch):
    _prepare(monkeypatch)
    snapshot = {"status": "measured", "axes": [{"code": "interaction_intensity", "value": 30}]}
    monkeypatch.setattr(
        services,
        "resolve_preference_profile",
        lambda *_args, **_kwargs: {
            "status": "measured",
            "snapshot": snapshot,
            "personality_profile_id": 9,
            "mbti_type": "INTJ",
            "personalization_enabled": True,
        },
    )
    app = Flask(__name__)
    app.config["MATCH_PREVIEW_MAX_SCAN_HARD"] = 8000

    with app.app_context():
        off, off_error, _ = services.run_match_preview({"resume_id": 1, "persist_snapshot": False}, 7)
        explained, explained_error, _ = services.run_match_preview(
            {"resume_id": 1, "preference_mode": "explain", "personality_profile_id": 9, "persist_snapshot": False},
            7,
        )

    assert off_error is None and explained_error is None
    assert [item["id"] for item in off["jobs"]] == [item["id"] for item in explained["jobs"]]
    assert [item["match_preview"]["match_score"] for item in off["jobs"]] == [item["match_preview"]["match_score"] for item in explained["jobs"]]
    assert explained["preference_context"]["influenced_ranking"] is False
    assert all(item["match_preview"]["preference_fit"]["status"] == "insufficient_job_evidence" for item in explained["jobs"])


def test_explain_mode_rejects_an_unowned_profile(monkeypatch):
    _prepare(monkeypatch)
    monkeypatch.setattr(services, "resolve_preference_profile", lambda *_args, **_kwargs: {"status": "missing", "snapshot": None})
    app = Flask(__name__)
    app.config["MATCH_PREVIEW_MAX_SCAN_HARD"] = 8000

    with app.app_context():
        data, error, status = services.run_match_preview(
            {"resume_id": 1, "preference_mode": "explain", "personality_profile_id": 999},
            7,
        )

    assert data is None
    assert status == 403
    assert "无权" in error


def test_explain_mode_calculates_auditable_fit_after_capability_sort(monkeypatch):
    _prepare(monkeypatch)
    codes = ["interaction_intensity", "abstraction_preference", "analytical_decision", "structure_preference"]
    snapshot = {"status": "measured", "axes": [
        {"code": code, "value": 80, "preference_strength": 0.6, "measurement_quality": 1.0}
        for code in codes
    ]}
    workstyle = {"evidenced_axis_count": 4, "axes": [
        {"code": code, "value": 75, "confidence": 0.8, "low_label": "低", "high_label": "高", "evidence": [{"text": f"{code} 岗位证据"}]}
        for code in codes
    ]}
    jobs = [_job("job-high", 62), _job("job-low", 90)]
    for job in jobs:
        job["workstyle"] = workstyle
    monkeypatch.setattr(services, "_fetch_jobs_for_match", lambda **_kwargs: jobs)
    monkeypatch.setattr(services, "resolve_preference_profile", lambda *_args, **_kwargs: {
        "status": "measured", "snapshot": snapshot, "personality_profile_id": 9,
        "mbti_type": "INTJ", "personalization_enabled": True,
    })
    app = Flask(__name__)
    app.config["MATCH_PREVIEW_MAX_SCAN_HARD"] = 8000
    with app.app_context():
        result, error, _ = services.run_match_preview({
            "resume_id": 1, "preference_mode": "explain", "persist_snapshot": False,
        }, 7)
    assert error is None
    assert result["preference_context"]["jobs_with_preference_fit"] == 2
    assert [item["id"] for item in result["jobs"]] == ["job-high", "job-low"]
    assert all(item["match_preview"]["preference_fit"]["status"] == "available" for item in result["jobs"])
    assert all(item["match_preview"]["preference_fit"]["influenced_ranking"] is False for item in result["jobs"])


def test_tie_break_mode_reorders_only_after_service_gates_pass(monkeypatch):
    _prepare(monkeypatch)
    codes = ["interaction_intensity", "abstraction_preference", "analytical_decision", "structure_preference"]
    snapshot = {
        "status": "measured",
        "axes": [
            {"code": code, "value": 80, "preference_strength": 0.6, "measurement_quality": 1.0}
            for code in codes
        ],
    }

    def workstyle(value):
        return {
            "evidenced_axis_count": 4,
            "axes": [
                {
                    "code": code,
                    "value": value,
                    "confidence": 0.9,
                    "low_label": "low",
                    "high_label": "high",
                    "evidence": [{"text": f"{code} evidence"}],
                }
                for code in codes
            ],
        }

    ability_first = _job("ability-first", 60)
    preference_first = _job("preference-first", 61)
    ability_first["workstyle"] = workstyle(20)
    preference_first["workstyle"] = workstyle(80)
    monkeypatch.setattr(services, "_fetch_jobs_for_match", lambda **_kwargs: [ability_first, preference_first])
    monkeypatch.setattr(services, "resolve_preference_profile", lambda *_args, **_kwargs: {
        "status": "measured",
        "snapshot": snapshot,
        "personality_profile_id": 9,
        "mbti_type": "INTJ",
        "personalization_enabled": True,
    })

    overrides = {
        "MATCH_PREFERENCE_TIE_BREAK_ENABLED": True,
        "MATCH_PREFERENCE_TIE_BREAK_MIN_COVERAGE": 0.6,
        "MATCH_PREFERENCE_TIE_BREAK_MAX_ABILITY_GAP": 3.0,
        "MATCH_PREFERENCE_TIE_BREAK_EXPERIMENT_PERCENT": 100,
    }
    monkeypatch.setattr(services, "setting", lambda name, default=None: overrides.get(name, default))
    app = Flask(__name__)
    app.config["MATCH_PREVIEW_MAX_SCAN_HARD"] = 8000

    with app.app_context():
        result, error, _ = services.run_match_preview({
            "resume_id": 1,
            "preference_mode": "tie_break",
            "persist_snapshot": False,
        }, 7)

    assert error is None
    assert [item["id"] for item in result["jobs"]] == ["preference-first", "ability-first"]
    context = result["preference_context"]
    assert context["influenced_ranking"] is True
    assert context["tie_break"]["applied"] is True
    assert context["tie_break"]["original_ability_order"] == ["ability-first", "preference-first"]
    assert context["tie_break"]["preference_order"] == ["preference-first", "ability-first"]
    assert result["jobs"][0]["match_preview"]["ability_rank"] == 2
