"""Pure, explainable work-preference fit calculation (never ranks jobs)."""

from __future__ import annotations

from typing import Any, Mapping

PREFERENCE_FIT_ALGORITHM_VERSION = "preference-fit-v1"


def _axis_explanation(user_value: float, job_value: float, low_label: str, high_label: str) -> str:
    user_side = high_label if user_value >= 50 else low_label
    job_side = high_label if job_value >= 50 else low_label
    if abs(user_value - 50) <= 10:
        return f"你在这一轴较灵活；岗位更偏{job_side}，建议结合实际团队验证。"
    if (user_value - 50) * (job_value - 50) >= 0:
        return f"岗位偏{job_side}，与当前更自然的{user_side}方式方向一致。"
    return f"岗位偏{job_side}，与当前更自然的{user_side}方式存在差异，可通过访谈验证。"


def build_preference_fit(
    preference_snapshot: Mapping[str, Any] | None,
    job_workstyle: Mapping[str, Any] | None,
    *,
    min_axes: int = 2,
    min_confidence: float = 0.4,
) -> dict[str, Any]:
    base = {
        "score": None,
        "confidence": None,
        "axes": [],
        "influenced_ranking": False,
        "algorithm_version": PREFERENCE_FIT_ALGORITHM_VERSION,
    }
    if not preference_snapshot or preference_snapshot.get("status") != "measured":
        return {**base, "status": "missing_user_profile"}
    if not job_workstyle:
        return {**base, "status": "insufficient_job_evidence"}

    user_axes = {
        str(axis.get("code")): axis
        for axis in preference_snapshot.get("axes") or []
        if isinstance(axis, Mapping) and axis.get("code")
    }
    job_axes = {
        str(axis.get("code")): axis
        for axis in job_workstyle.get("axes") or []
        if isinstance(axis, Mapping) and axis.get("code")
    }
    results: list[dict[str, Any]] = []
    weighted_fit = 0.0
    weight_sum = 0.0
    confidence_sum = 0.0

    for code, user_axis in user_axes.items():
        job_axis = job_axes.get(code)
        if not job_axis or not job_axis.get("evidence"):
            continue
        user_value = float(user_axis.get("value") or 0)
        job_value = float(job_axis.get("value") or 0)
        strength = max(0.0, min(1.0, float(user_axis.get("preference_strength") or abs(user_value - 50) / 50)))
        quality = max(0.0, min(1.0, float(user_axis.get("measurement_quality") or 0)))
        job_confidence = max(0.0, min(1.0, float(job_axis.get("confidence") or 0)))
        confidence = job_confidence * quality
        axis_fit = max(0.0, min(100.0, 100.0 - strength * abs(user_value - job_value)))
        low_label = str(job_axis.get("low_label") or user_axis.get("low_label") or "低值方式")
        high_label = str(job_axis.get("high_label") or user_axis.get("high_label") or "高值方式")
        weighted_fit += axis_fit * confidence
        weight_sum += confidence
        confidence_sum += confidence
        results.append(
            {
                "code": code,
                "user_value": round(user_value, 2),
                "job_value": round(job_value, 2),
                "preference_strength": round(strength, 4),
                "fit": round(axis_fit, 1),
                "confidence": round(confidence, 4),
                "evidence": list(job_axis.get("evidence") or [])[:8],
                "source": str(job_axis.get("source") or ""),
                "inherited_from_job_title": bool(job_axis.get("inherited_from_job_title")),
                "explanation": _axis_explanation(user_value, job_value, low_label, high_label),
            }
        )

    fit_confidence = confidence_sum / len(results) if results else 0.0
    if len(results) < max(1, int(min_axes)) or weight_sum <= 0 or fit_confidence < float(min_confidence):
        return {
            **base,
            "status": "insufficient_job_evidence",
            "confidence": round(fit_confidence, 4),
            "axes": results,
            "evidenced_axes": len(results),
            "required_axes": max(1, int(min_axes)),
        }
    return {
        **base,
        "status": "available",
        "score": round(weighted_fit / weight_sum, 1),
        "confidence": round(fit_confidence, 4),
        "confidence_level": "high" if fit_confidence >= 0.7 else "medium",
        "axes": results,
        "evidenced_axes": len(results),
        "required_axes": max(1, int(min_axes)),
    }
