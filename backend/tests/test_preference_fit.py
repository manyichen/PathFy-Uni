from app.domains.match.preference_fit import build_preference_fit


def _user(*values: float):
    codes = ["interaction_intensity", "abstraction_preference", "analytical_decision", "structure_preference"]
    return {
        "status": "measured",
        "axes": [
            {"code": code, "value": value, "preference_strength": abs(value - 50) / 50, "measurement_quality": 1.0}
            for code, value in zip(codes, values, strict=True)
        ],
    }


def _job(*values: float, confidence: float = 0.8):
    codes = ["interaction_intensity", "abstraction_preference", "analytical_decision", "structure_preference"]
    return {
        "axes": [
            {"code": code, "value": value, "confidence": confidence, "low_label": "低", "high_label": "高", "evidence": [{"text": f"{code} evidence"}]}
            for code, value in zip(codes, values, strict=True)
        ]
    }


def test_neutral_user_axis_is_not_penalized_by_an_extreme_job():
    result = build_preference_fit(_user(50, 50, 50, 50), _job(0, 100, 0, 100))
    assert result["status"] == "available"
    assert result["score"] == 100.0
    assert all(axis["fit"] == 100.0 for axis in result["axes"])


def test_strong_opposite_preferences_can_reach_zero_with_auditable_axes():
    result = build_preference_fit(_user(100, 100, 100, 100), _job(0, 0, 0, 0))
    assert result["status"] == "available"
    assert result["score"] == 0.0
    assert result["influenced_ranking"] is False
    assert result["axes"][0]["evidence"][0]["text"]


def test_insufficient_axes_or_confidence_suppresses_the_score():
    workstyle = _job(80, 80, 80, 80, confidence=0.3)
    assert build_preference_fit(_user(80, 80, 80, 80), workstyle)["score"] is None
    workstyle["axes"] = workstyle["axes"][:1]
    result = build_preference_fit(_user(80, 80, 80, 80), workstyle, min_confidence=0.1)
    assert result["status"] == "insufficient_job_evidence"
    assert result["evidenced_axes"] == 1


def test_missing_user_profile_is_a_non_error_state():
    assert build_preference_fit(None, _job(50, 50, 50, 50))["status"] == "missing_user_profile"
