"""Persistence and serialization for versioned personality assessments."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, Iterable, Mapping

from app.db import db_cursor
from app.domains.personality.scoring import build_preference_axes


def _json_value(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return default


def _iso(value: Any) -> str | None:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value or "").strip()
    return text or None


def _recommended_jobs(value: Any, detailed: Mapping[str, Any]) -> list[str]:
    nested = detailed.get("job_recommendations")
    if isinstance(nested, Mapping) and isinstance(nested.get("recommended_jobs"), list):
        return [str(item).strip() for item in nested["recommended_jobs"] if str(item).strip()]
    parsed = _json_value(value, None)
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def serialize_profile(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the stable API result shape consumed by the fingerprint and future domains."""
    detailed = _json_value(row.get("detailed_analysis"), {})
    if not isinstance(detailed, dict):
        detailed = {}
    dimension_scores = _json_value(row.get("dimension_scores_json"), None)
    if not isinstance(dimension_scores, list):
        dimension_scores = detailed.get("dimension_scores")
    if not isinstance(dimension_scores, list):
        dimension_scores = []
    dimension_analysis = detailed.get("dimension_analysis")
    if not isinstance(dimension_analysis, list):
        dimension_analysis = []
    complete_analysis = detailed.get("complete_analysis")
    if not isinstance(complete_analysis, dict):
        complete_analysis = {}
    job_recommendations = detailed.get("job_recommendations")
    if not isinstance(job_recommendations, dict):
        job_recommendations = {}
    measured = len(dimension_scores) == 4
    result_status = str(row.get("result_status") or ("measured" if measured else "legacy_signature"))
    return {
        "id": int(row.get("id") or row.get("profile_id") or 0),
        "profile_id": int(row.get("id") or row.get("profile_id") or 0),
        "mbti_type": str(row.get("mbti_type") or ""),
        "personality_analysis": str(row.get("personality_analysis") or ""),
        "recommended_jobs": _recommended_jobs(row.get("recommended_jobs"), detailed),
        "dimension_analysis": dimension_analysis,
        "dimension_scores": dimension_scores,
        "preference_axes": build_preference_axes(dimension_scores),
        "complete_analysis": complete_analysis,
        "job_recommendations": job_recommendations,
        "detailed_analysis": detailed or None,
        "status": "measured" if result_status == "measured" and measured else "legacy",
        "result_status": result_status,
        "question_set_version": str(row.get("question_set_version") or "legacy-v1"),
        "scoring_version": str(row.get("scoring_version") or "legacy"),
        "answer_signature": str(row.get("answer_signature") or "") or None,
        "is_active": bool(row.get("is_active")),
        "personalization_enabled": bool(row.get("personalization_enabled")),
        "completed_at": _iso(row.get("completed_at") or row.get("created_at")),
        "created_at": _iso(row.get("created_at")),
    }


def list_questions() -> list[dict[str, Any]]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT * FROM personality_test_questions ORDER BY id")
        return list(cur.fetchall() or [])


def create_assessment(
    *,
    user_id: int,
    scored: Mapping[str, Any],
    personality_analysis: str,
    dimension_analysis: list[dict[str, Any]],
    complete_analysis: Mapping[str, Any],
    job_recommendations: Mapping[str, Any],
) -> int:
    """Persist a profile and its answers atomically, then make it the active result."""
    detailed_analysis = {
        "dimension_analysis": dimension_analysis,
        "dimension_scores": scored["dimension_scores"],
        "preference_axes": scored["preference_axes"],
        "complete_analysis": dict(complete_analysis),
        "job_recommendations": dict(job_recommendations),
        "borderline_axes": list(scored.get("borderline_axes") or []),
        "measurement_quality": float(scored.get("measurement_quality") or 0.0),
        "question_set_version": scored["question_set_version"],
        "scoring_version": scored["scoring_version"],
    }
    answers = list(scored.get("answers") or [])
    with db_cursor() as (_, cur):
        cur.execute(
            "UPDATE personality_profiles SET is_active=0 WHERE user_id=%s AND is_active=1",
            (user_id,),
        )
        cur.execute(
            """
            INSERT INTO personality_profiles (
              user_id, mbti_type, personality_analysis, recommended_jobs,
              detailed_analysis, dimension_scores_json, question_set_version,
              scoring_version, result_status, is_active, personalization_enabled,
              completed_at, answer_signature
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'measured',1,0,UTC_TIMESTAMP(),%s)
            """,
            (
                user_id,
                scored["mbti_type"],
                personality_analysis,
                ", ".join(str(item) for item in job_recommendations.get("recommended_jobs") or []),
                json.dumps(detailed_analysis, ensure_ascii=False),
                json.dumps(scored["dimension_scores"], ensure_ascii=False),
                scored["question_set_version"],
                scored["scoring_version"],
                scored["answer_signature"],
            ),
        )
        profile_id = int(cur.lastrowid)
        if answers:
            cur.executemany(
                """
                INSERT INTO personality_test_answers (
                  user_id, personality_profile_id, question_id, user_choice, question_set_version
                ) VALUES (%s,%s,%s,%s,%s)
                """,
                [
                    (
                        user_id,
                        profile_id,
                        int(answer["question_id"]),
                        str(answer["user_choice"]),
                        scored["question_set_version"],
                    )
                    for answer in answers
                ],
            )
        cur.execute(
            """
            UPDATE personality_profiles
            SET superseded_by_profile_id=%s
            WHERE user_id=%s AND id<>%s AND superseded_by_profile_id IS NULL
            """,
            (profile_id, user_id, profile_id),
        )
    return profile_id


def get_profile(user_id: int, profile_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT * FROM personality_profiles WHERE id=%s AND user_id=%s LIMIT 1",
            (profile_id, user_id),
        )
        row = cur.fetchone()
    return serialize_profile(row) if row else None


def get_active_profile(user_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT * FROM personality_profiles
            WHERE user_id=%s AND is_active=1
            ORDER BY COALESCE(completed_at, created_at) DESC, id DESC LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT * FROM personality_profiles
                WHERE user_id=%s
                ORDER BY COALESCE(completed_at, created_at) DESC, id DESC LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
    return serialize_profile(row) if row else None


def list_profiles(user_id: int, *, limit: int = 30) -> list[Dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 80))
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT * FROM personality_profiles
            WHERE user_id=%s
            ORDER BY COALESCE(completed_at, created_at) DESC, id DESC
            LIMIT %s
            """,
            (user_id, safe_limit),
        )
        rows = list(cur.fetchall() or [])
    return [serialize_profile(row) for row in rows]


def activate_profile(user_id: int, profile_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id FROM personality_profiles WHERE id=%s AND user_id=%s LIMIT 1",
            (profile_id, user_id),
        )
        if not cur.fetchone():
            return None
        cur.execute("UPDATE personality_profiles SET is_active=0 WHERE user_id=%s", (user_id,))
        cur.execute(
            "UPDATE personality_profiles SET is_active=1 WHERE id=%s AND user_id=%s",
            (profile_id, user_id),
        )
    return get_profile(user_id, profile_id)


def update_personalization(
    user_id: int,
    profile_id: int,
    *,
    enabled: bool,
) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id FROM personality_profiles WHERE id=%s AND user_id=%s LIMIT 1",
            (profile_id, user_id),
        )
        if not cur.fetchone():
            return None
        cur.execute(
            """
            UPDATE personality_profiles SET personalization_enabled=%s
            WHERE id=%s AND user_id=%s
            """,
            (1 if enabled else 0, profile_id, user_id),
        )
    return get_profile(user_id, profile_id)


def delete_profile(user_id: int, profile_id: int) -> Dict[str, int] | None:
    """Delete one owned assessment and scrub its directly-derived match snapshots."""
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id, is_active FROM personality_profiles WHERE id=%s AND user_id=%s LIMIT 1",
            (profile_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        was_active = bool(row.get("is_active"))
        cur.execute(
            "SELECT COUNT(*) AS count FROM match_runs WHERE user_id=%s AND personality_profile_id=%s",
            (user_id, profile_id),
        )
        affected_match_runs = int((cur.fetchone() or {}).get("count") or 0)
        cur.execute(
            """
            UPDATE match_runs
            SET personality_profile_id=NULL,
                preference_mode='off',
                preference_snapshot_json=NULL,
                preference_algorithm_version=NULL,
                workstyle_snapshot_version=NULL
            WHERE user_id=%s AND personality_profile_id=%s
            """,
            (user_id, profile_id),
        )
        cur.execute(
            "DELETE FROM personality_profiles WHERE id=%s AND user_id=%s",
            (profile_id, user_id),
        )
        if was_active:
            cur.execute(
                """
                UPDATE personality_profiles SET is_active=1
                WHERE id=(
                  SELECT id FROM (
                    SELECT id FROM personality_profiles
                    WHERE user_id=%s
                    ORDER BY COALESCE(completed_at, created_at) DESC, id DESC LIMIT 1
                  ) latest
                )
                """,
                (user_id,),
            )
    return {"deleted_profiles": 1, "scrubbed_match_runs": affected_match_runs}
