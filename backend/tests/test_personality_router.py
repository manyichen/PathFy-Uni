from app.domains.personality import router


QUESTIONS = [
    {"id": 1, "dimension": "EI", "option_a_type": "E", "option_b_type": "I"},
    {"id": 2, "dimension": "SN", "option_a_type": "S", "option_b_type": "N"},
    {"id": 3, "dimension": "TF", "option_a_type": "T", "option_b_type": "F"},
    {"id": 4, "dimension": "JP", "option_a_type": "J", "option_b_type": "P"},
]


def _authenticate(monkeypatch):
    monkeypatch.setattr(router, "get_bearer_user_id", lambda: 7)


def test_latest_returns_explicit_missing_state(client, monkeypatch):
    _authenticate(monkeypatch)
    monkeypatch.setattr(router, "get_active_profile", lambda user_id: None)

    response = client.get("/api/personality/me/latest")

    assert response.status_code == 200
    assert response.get_json() == {
        "code": 200,
        "msg": "success",
        "data": {"status": "missing"},
    }


def test_submit_scores_then_returns_persisted_contract(client, monkeypatch):
    _authenticate(monkeypatch)
    monkeypatch.setattr(router, "list_questions", lambda: QUESTIONS)
    monkeypatch.setattr(router, "generate_dimension_analysis", lambda dimensions: [{"type": "I"}])
    monkeypatch.setattr(router, "generate_complete_analysis", lambda mbti: {"type": mbti})
    monkeypatch.setattr(
        router,
        "generate_job_recommendations",
        lambda mbti: {"recommended_jobs": ["数据分析师"]},
    )
    monkeypatch.setattr(router, "generate_comprehensive_report", lambda *args: "summary")
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return 12

    monkeypatch.setattr(router, "create_assessment", create)
    monkeypatch.setattr(
        router,
        "load_profile",
        lambda user_id, profile_id: {"profile_id": profile_id, "mbti_type": "INTJ"},
    )

    response = client.post(
        "/api/personality/submit",
        json={
            "answers": [
                {"question_id": 1, "user_choice": "B"},
                {"question_id": 2, "user_choice": "B"},
                {"question_id": 3, "user_choice": "A"},
                {"question_id": 4, "user_choice": "A"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.get_json()["data"] == {"profile_id": 12, "mbti_type": "INTJ"}
    assert captured["user_id"] == 7
    assert captured["scored"]["question_set_version"] == "mbti-50-v1"
    assert len(captured["scored"]["answer_signature"]) == 64


def test_preferences_requires_explicit_boolean(client, monkeypatch):
    _authenticate(monkeypatch)

    response = client.patch(
        "/api/personality/profiles/12/preferences",
        json={"personalization_enabled": "yes"},
    )

    assert response.status_code == 400
    assert "布尔值" in response.get_json()["msg"]


def test_delete_profile_returns_scrubbed_snapshot_count(client, monkeypatch):
    _authenticate(monkeypatch)
    monkeypatch.setattr(
        router,
        "delete_profile",
        lambda user_id, profile_id: {"deleted_profiles": 1, "scrubbed_match_runs": 3},
    )

    response = client.delete("/api/personality/profiles/12")

    assert response.status_code == 200
    assert response.get_json()["data"]["scrubbed_match_runs"] == 3
