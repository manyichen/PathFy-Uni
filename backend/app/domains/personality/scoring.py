"""Pure, versioned personality-assessment scoring and validation."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Mapping


QUESTION_SET_VERSION = "mbti-50-v1"
SCORING_VERSION = "mbti-count-v2"

DIMENSION_PAIRS = (
    ("EI", "E", "I", "能量来源"),
    ("SN", "S", "N", "信息获取"),
    ("TF", "T", "F", "决策方式"),
    ("JP", "J", "P", "生活方式"),
)
VALID_LETTERS = {letter for _, left, right, _ in DIMENSION_PAIRS for letter in (left, right)}


class PersonalityValidationError(ValueError):
    """Raised when an assessment cannot be scored as a complete question set."""


def _question_id(value: Any) -> int:
    try:
        question_id = int(value)
    except (TypeError, ValueError) as exc:
        raise PersonalityValidationError("答案包含无效 question_id") from exc
    if question_id <= 0:
        raise PersonalityValidationError("答案包含无效 question_id")
    return question_id


def _validated_questions(questions: Iterable[Mapping[str, Any]]) -> Dict[int, Mapping[str, Any]]:
    question_by_id: Dict[int, Mapping[str, Any]] = {}
    for question in questions:
        question_id = _question_id(question.get("id"))
        if question_id in question_by_id:
            raise PersonalityValidationError("题库包含重复题目")
        dimension = str(question.get("dimension") or "").strip().upper()
        option_a_type = str(question.get("option_a_type") or "").strip().upper()
        option_b_type = str(question.get("option_b_type") or "").strip().upper()
        if dimension not in {code for code, *_ in DIMENSION_PAIRS}:
            raise PersonalityValidationError(f"题目 {question_id} 的维度无效")
        expected = set(dimension)
        if {option_a_type, option_b_type} != expected or not expected <= VALID_LETTERS:
            raise PersonalityValidationError(f"题目 {question_id} 的选项计分配置无效")
        question_by_id[question_id] = question
    if not question_by_id:
        raise PersonalityValidationError("当前题库为空")
    return question_by_id


def build_dimension_scores(dimensions: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Convert counts to continuous scores without inventing a dominant side for ties."""
    scores: List[Dict[str, Any]] = []
    for code, left, right, label in DIMENSION_PAIRS:
        left_count = max(0, int(dimensions.get(left, 0) or 0))
        right_count = max(0, int(dimensions.get(right, 0) or 0))
        total = left_count + right_count
        left_score = round(left_count / total * 100, 2) if total else 50.0
        right_score = round(100 - left_score, 2)
        dominant = left if left_count > right_count else right if right_count > left_count else "neutral"
        preference_strength = round(abs(left_count - right_count) / total, 4) if total else 0.0
        scores.append(
            {
                "code": code,
                "label": label,
                "left": left,
                "right": right,
                "left_count": left_count,
                "right_count": right_count,
                "left_score": left_score,
                "right_score": right_score,
                "dominant": dominant,
                # Retain the legacy field for the existing fingerprint/type contract.
                "confidence": preference_strength,
                "preference_strength": preference_strength,
                "borderline": dominant == "neutral",
            }
        )
    return scores


def build_preference_axes(dimension_scores: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Map MBTI-oriented pairs to stable, consistently oriented work-preference axes."""
    by_code = {str(item.get("code") or "").upper(): item for item in dimension_scores}
    definitions = (
        ("interaction_intensity", "EI", "left_score", "独立恢复", "互动恢复"),
        ("abstraction_preference", "SN", "right_score", "具体事实", "模式可能"),
        ("analytical_decision", "TF", "left_score", "关系价值", "规则分析"),
        ("structure_preference", "JP", "left_score", "灵活开放", "计划确定"),
    )
    axes: List[Dict[str, Any]] = []
    for code, source_code, score_key, low_label, high_label in definitions:
        source = by_code.get(source_code)
        if not source:
            continue
        value = max(0.0, min(100.0, float(source.get(score_key) or 0.0)))
        axes.append(
            {
                "code": code,
                "source_dimension": source_code,
                "value": round(value, 2),
                "preference_strength": round(abs(value - 50.0) / 50.0, 4),
                "measurement_quality": 1.0,
                "low_label": low_label,
                "high_label": high_label,
            }
        )
    return axes


def score_assessment(
    answers: Iterable[Mapping[str, Any]],
    questions: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate a complete assessment and return its versioned deterministic score."""
    question_by_id = _validated_questions(questions)
    normalized_answers: List[Dict[str, Any]] = []
    seen: set[int] = set()
    dimensions = {letter: 0 for letter in VALID_LETTERS}

    for raw_answer in answers:
        if not isinstance(raw_answer, Mapping):
            raise PersonalityValidationError("答案项必须为对象")
        question_id = _question_id(raw_answer.get("question_id"))
        if question_id in seen:
            raise PersonalityValidationError(f"题目 {question_id} 重复作答")
        question = question_by_id.get(question_id)
        if not question:
            raise PersonalityValidationError(f"题目 {question_id} 不属于当前题库")
        choice = str(raw_answer.get("user_choice") or "").strip().upper()
        if choice not in {"A", "B"}:
            raise PersonalityValidationError(f"题目 {question_id} 的选项仅支持 A 或 B")
        seen.add(question_id)
        score_letter = str(question[f"option_{choice.lower()}_type"]).strip().upper()
        dimensions[score_letter] += 1
        normalized_answers.append({"question_id": question_id, "user_choice": choice})

    expected_ids = set(question_by_id)
    if seen != expected_ids:
        missing = sorted(expected_ids - seen)
        if missing:
            suffix = "、".join(str(value) for value in missing[:5])
            raise PersonalityValidationError(f"请完成全部题目，尚缺少：{suffix}")
        raise PersonalityValidationError("答案与当前题库不一致")

    # MBTI remains a four-letter display summary. Ties use the right-hand letter
    # consistently, while continuous scores explicitly mark the axis neutral.
    mbti_type = "".join(
        left if dimensions[left] > dimensions[right] else right
        for _, left, right, _ in DIMENSION_PAIRS
    )
    dimension_scores = build_dimension_scores(dimensions)
    canonical_answers = "|".join(
        f"{item['question_id']}:{item['user_choice']}"
        for item in sorted(normalized_answers, key=lambda item: item["question_id"])
    )
    answer_signature = hashlib.sha256(canonical_answers.encode("utf-8")).hexdigest()
    return {
        "mbti_type": mbti_type,
        "dimensions": dimensions,
        "dimension_scores": dimension_scores,
        "preference_axes": build_preference_axes(dimension_scores),
        "borderline_axes": [item["code"] for item in dimension_scores if item["borderline"]],
        "measurement_quality": 1.0,
        "question_set_version": QUESTION_SET_VERSION,
        "scoring_version": SCORING_VERSION,
        "answer_signature": answer_signature,
        "answers": normalized_answers,
    }
