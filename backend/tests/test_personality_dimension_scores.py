import pytest

from app.domains.personality.scoring import (
    PersonalityValidationError,
    build_dimension_scores,
    score_assessment,
)


def _questions():
    return [
        {"id": 1, "dimension": "EI", "option_a_type": "E", "option_b_type": "I"},
        {"id": 2, "dimension": "EI", "option_a_type": "E", "option_b_type": "I"},
        {"id": 3, "dimension": "SN", "option_a_type": "S", "option_b_type": "N"},
        {"id": 4, "dimension": "TF", "option_a_type": "T", "option_b_type": "F"},
        {"id": 5, "dimension": "JP", "option_a_type": "J", "option_b_type": "P"},
    ]


def test_build_dimension_scores_preserves_counts_and_marks_ties_neutral():
    scores = build_dimension_scores(
        {"E": 3, "I": 1, "S": 1, "N": 3, "T": 2, "F": 2, "J": 4, "P": 0}
    )

    assert [item["code"] for item in scores] == ["EI", "SN", "TF", "JP"]
    assert scores[0]["left_score"] == 75.0
    assert scores[0]["right_score"] == 25.0
    assert scores[0]["dominant"] == "E"
    assert scores[0]["preference_strength"] == 0.5
    assert scores[1]["dominant"] == "N"
    assert scores[2]["dominant"] == "neutral"
    assert scores[2]["borderline"] is True
    assert scores[3]["confidence"] == 1.0


def test_score_assessment_is_complete_versioned_and_order_stable():
    answers = [
        {"question_id": 1, "user_choice": "A"},
        {"question_id": 2, "user_choice": "B"},
        {"question_id": 3, "user_choice": "B"},
        {"question_id": 4, "user_choice": "A"},
        {"question_id": 5, "user_choice": "A"},
    ]

    first = score_assessment(answers, _questions())
    reordered = score_assessment(reversed(answers), _questions())

    assert first["mbti_type"] == "INTJ"
    assert first["borderline_axes"] == ["EI"]
    assert len(first["preference_axes"]) == 4
    assert first["question_set_version"] == "mbti-50-v1"
    assert first["scoring_version"] == "mbti-count-v2"
    assert first["answer_signature"] == reordered["answer_signature"]


@pytest.mark.parametrize(
    "answers, message",
    [
        ([{"question_id": 1, "user_choice": "A"}], "尚缺少"),
        (
            [
                {"question_id": 1, "user_choice": "A"},
                {"question_id": 1, "user_choice": "B"},
            ],
            "重复作答",
        ),
        ([{"question_id": 999, "user_choice": "A"}], "不属于当前题库"),
        ([{"question_id": 1, "user_choice": "C"}], "仅支持 A 或 B"),
    ],
)
def test_score_assessment_rejects_invalid_or_incomplete_answers(answers, message):
    with pytest.raises(PersonalityValidationError, match=message):
        score_assessment(answers, _questions())


def test_build_dimension_scores_uses_neutral_fallback_for_missing_counts():
    scores = build_dimension_scores({})

    assert all(item["left_score"] == 50.0 for item in scores)
    assert all(item["right_score"] == 50.0 for item in scores)
    assert all(item["dominant"] == "neutral" for item in scores)
