from app.domains.personality import preference_profile


def _profile(*, enabled=True, status="measured"):
    return {
        "profile_id": 9,
        "status": status,
        "mbti_type": "INTJ",
        "personalization_enabled": enabled,
        "completed_at": "2026-08-19T10:00:00",
        "question_set_version": "mbti-50-v1",
        "scoring_version": "mbti-count-v2",
        "preference_axes": [
            {"code": code, "value": value, "preference_strength": 0.4, "measurement_quality": 1.0}
            for code, value in (
                ("interaction_intensity", 30),
                ("abstraction_preference", 75),
                ("analytical_decision", 70),
                ("structure_preference", 65),
            )
        ],
        "personality_analysis": "must not cross domains",
        "answer_signature": "secret-derived-signature",
    }


def test_resolved_snapshot_is_minimal_and_requires_consent(monkeypatch):
    monkeypatch.setattr(preference_profile, "get_active_profile", lambda user_id: _profile())

    resolved = preference_profile.resolve_preference_profile(7)
    snapshot = resolved["snapshot"]

    assert resolved["status"] == "measured"
    assert len(snapshot["axes"]) == 4
    assert "personality_analysis" not in snapshot
    assert "answer_signature" not in snapshot


def test_disabled_and_legacy_profiles_do_not_expose_axes(monkeypatch):
    monkeypatch.setattr(preference_profile, "get_active_profile", lambda user_id: _profile(enabled=False))
    assert preference_profile.resolve_preference_profile(7)["status"] == "disabled"
    assert preference_profile.resolve_preference_profile(7)["snapshot"] is None

    monkeypatch.setattr(preference_profile, "get_active_profile", lambda user_id: _profile(status="legacy"))
    assert preference_profile.resolve_preference_profile(7)["status"] == "legacy"
    assert preference_profile.resolve_preference_profile(7)["snapshot"] is None
