from datetime import datetime

from app.domains.personality.repository import serialize_profile


def test_serialize_profile_returns_stable_measured_contract():
    profile = serialize_profile(
        {
            "id": 8,
            "mbti_type": "INTJ",
            "personality_analysis": "summary",
            "recommended_jobs": "数据分析师, 产品经理",
            "dimension_scores_json": '[{"code":"EI","left":"E","right":"I","left_score":40,"right_score":60},{"code":"SN","left":"S","right":"N","left_score":20,"right_score":80},{"code":"TF","left":"T","right":"F","left_score":70,"right_score":30},{"code":"JP","left":"J","right":"P","left_score":65,"right_score":35}]',
            "detailed_analysis": "{}",
            "result_status": "measured",
            "question_set_version": "mbti-50-v1",
            "scoring_version": "mbti-count-v2",
            "answer_signature": "a" * 64,
            "is_active": 1,
            "personalization_enabled": 0,
            "completed_at": datetime(2026, 8, 19, 12, 30),
        }
    )

    assert profile["profile_id"] == 8
    assert profile["status"] == "measured"
    assert profile["recommended_jobs"] == ["数据分析师", "产品经理"]
    assert len(profile["preference_axes"]) == 4
    assert profile["answer_signature"] == "a" * 64
    assert profile["completed_at"] == "2026-08-19T12:30:00"


def test_serialize_profile_labels_unmeasured_history_as_legacy():
    profile = serialize_profile({"id": 2, "mbti_type": "ENFP", "result_status": "legacy_signature"})

    assert profile["status"] == "legacy"
    assert profile["dimension_scores"] == []
    assert profile["preference_axes"] == []
