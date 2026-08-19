"""Cross-domain, privacy-minimized personality preference snapshots."""

from __future__ import annotations

from typing import Any, Mapping

from app.domains.personality.repository import get_active_profile, get_profile

PREFERENCE_SNAPSHOT_VERSION = "preference-profile-v1"
PREFERENCE_ALGORITHM_VERSION = "preference-explain-v1"


def _minimal_axes(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    axes: list[dict[str, Any]] = []
    for raw in profile.get("preference_axes") or []:
        if not isinstance(raw, Mapping):
            continue
        code = str(raw.get("code") or "").strip()
        if not code:
            continue
        axes.append(
            {
                "code": code,
                "value": round(float(raw.get("value") or 0.0), 2),
                "preference_strength": round(
                    float(raw.get("preference_strength") or 0.0), 4
                ),
                "measurement_quality": round(
                    float(raw.get("measurement_quality") or 0.0), 4
                ),
                "low_label": str(raw.get("low_label") or ""),
                "high_label": str(raw.get("high_label") or ""),
            }
        )
    return axes


def snapshot_from_profile(profile: Mapping[str, Any]) -> dict[str, Any] | None:
    """Build a reusable snapshot without raw answers or long-form analysis."""
    axes = _minimal_axes(profile)
    if profile.get("status") != "measured" or len(axes) != 4:
        return None
    return {
        "schema_version": PREFERENCE_SNAPSHOT_VERSION,
        "personality_profile_id": int(profile.get("profile_id") or 0),
        "status": "measured",
        "mbti_type": str(profile.get("mbti_type") or ""),
        "axes": axes,
        "question_set_version": str(profile.get("question_set_version") or ""),
        "scoring_version": str(profile.get("scoring_version") or ""),
        "completed_at": profile.get("completed_at"),
    }


def resolve_preference_profile(
    user_id: int,
    *,
    profile_id: int | None = None,
    require_personalization_enabled: bool = True,
) -> dict[str, Any]:
    """Resolve an owned profile and return an explicit non-error availability state."""
    profile = (
        get_profile(user_id, profile_id)
        if profile_id is not None
        else get_active_profile(user_id)
    )
    if not profile:
        return {
            "status": "missing",
            "requested_profile_id": profile_id,
            "snapshot": None,
        }
    summary = {
        "personality_profile_id": int(profile.get("profile_id") or 0),
        "mbti_type": str(profile.get("mbti_type") or ""),
        "completed_at": profile.get("completed_at"),
        "personalization_enabled": bool(profile.get("personalization_enabled")),
    }
    if profile.get("status") != "measured":
        return {**summary, "status": "legacy", "snapshot": None}
    if require_personalization_enabled and not profile.get("personalization_enabled"):
        return {**summary, "status": "disabled", "snapshot": None}
    snapshot = snapshot_from_profile(profile)
    if not snapshot:
        return {**summary, "status": "invalid", "snapshot": None}
    return {**summary, "status": "measured", "snapshot": snapshot}


def preference_context_summary(resolved: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    """Return the small public context attached to match responses."""
    return {
        "mode": mode,
        "status": str(resolved.get("status") or "missing"),
        "personality_profile_id": resolved.get("personality_profile_id"),
        "mbti_type": resolved.get("mbti_type"),
        "completed_at": resolved.get("completed_at"),
        "personalization_enabled": bool(resolved.get("personalization_enabled")),
        "influenced_ranking": False,
        "algorithm_version": PREFERENCE_ALGORITHM_VERSION,
    }
