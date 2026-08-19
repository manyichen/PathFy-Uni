"""Personality assessment HTTP routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.core.security import assert_self_user_id, get_bearer_user_id
from app.domains.personality.repository import (
    activate_profile,
    create_assessment,
    delete_profile,
    get_active_profile,
    get_profile as load_profile,
    list_profiles,
    list_questions,
    update_personalization,
)
from app.domains.personality.scoring import PersonalityValidationError, score_assessment
from app.domains.personality.services import (
    generate_complete_analysis,
    generate_comprehensive_report,
    generate_dimension_analysis,
    generate_job_recommendations,
)

personality_bp = Blueprint("personality", __name__, url_prefix="/api/personality")


def _auth_user_id():
    user_id = get_bearer_user_id()
    if user_id is None:
        return None, (jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401)
    return user_id, None


def _success(data, *, message: str = "success"):
    return jsonify({"code": 200, "msg": message, "data": data})


@personality_bp.route("/questions", methods=["GET"])
def get_questions():
    try:
        return _success(list_questions())
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


@personality_bp.route("/submit", methods=["POST"])
def submit_answers():
    user_id, error = _auth_user_id()
    if error:
        return error

    body = request.get_json(silent=True) or {}
    answers = body.get("answers")
    if not isinstance(answers, list):
        return jsonify({"code": 400, "msg": "answers 必须是数组"}), 400

    try:
        scored = score_assessment(answers, list_questions())
    except PersonalityValidationError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400

    try:
        dimension_analysis = generate_dimension_analysis(scored["dimensions"])
        complete_analysis = generate_complete_analysis(scored["mbti_type"])
        job_recommendations = generate_job_recommendations(scored["mbti_type"])
        personality_analysis = generate_comprehensive_report(
            scored["mbti_type"],
            dimension_analysis,
            complete_analysis,
            job_recommendations,
        )
        profile_id = create_assessment(
            user_id=user_id,
            scored=scored,
            personality_analysis=personality_analysis,
            dimension_analysis=dimension_analysis,
            complete_analysis=complete_analysis,
            job_recommendations=job_recommendations,
        )
        profile = load_profile(user_id, profile_id)
        if not profile:
            raise RuntimeError("测评结果保存后无法读取")
        return _success(profile)
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


def _profile_response(user_id: int, profile_id: int):
    profile = load_profile(user_id, profile_id)
    if not profile:
        return jsonify({"code": 404, "msg": "结果不存在"}), 404
    return _success(profile)


@personality_bp.route("/me/latest", methods=["GET"])
def get_latest_profile():
    user_id, error = _auth_user_id()
    if error:
        return error
    try:
        profile = get_active_profile(user_id)
        return _success(profile or {"status": "missing"})
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


@personality_bp.route("/me/profiles", methods=["GET"])
def get_my_profiles():
    user_id, error = _auth_user_id()
    if error:
        return error
    try:
        limit = request.args.get("limit", 30, type=int) or 30
        return _success(list_profiles(user_id, limit=limit))
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


@personality_bp.route("/profiles/<int:profile_id>", methods=["GET"])
@personality_bp.route("/profile/<int:profile_id>", methods=["GET"])
def get_profile(profile_id: int):
    user_id, error = _auth_user_id()
    if error:
        return error
    try:
        return _profile_response(user_id, profile_id)
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


@personality_bp.route("/profiles/<int:profile_id>/activate", methods=["POST"])
def set_active_profile(profile_id: int):
    user_id, error = _auth_user_id()
    if error:
        return error
    try:
        profile = activate_profile(user_id, profile_id)
        if not profile:
            return jsonify({"code": 404, "msg": "结果不存在"}), 404
        return _success(profile)
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


@personality_bp.route("/profiles/<int:profile_id>/preferences", methods=["PATCH"])
def set_profile_preferences(profile_id: int):
    user_id, error = _auth_user_id()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    enabled = body.get("personalization_enabled")
    if not isinstance(enabled, bool):
        return jsonify({"code": 400, "msg": "personalization_enabled 必须是布尔值"}), 400
    try:
        profile = update_personalization(user_id, profile_id, enabled=enabled)
        if not profile:
            return jsonify({"code": 404, "msg": "结果不存在"}), 404
        return _success(profile)
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


@personality_bp.route("/profiles/<int:profile_id>", methods=["DELETE"])
def remove_profile(profile_id: int):
    user_id, error = _auth_user_id()
    if error:
        return error
    try:
        impact = delete_profile(user_id, profile_id)
        if impact is None:
            return jsonify({"code": 404, "msg": "结果不存在"}), 404
        return _success(impact, message="已删除测评及其个性化派生数据")
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500


@personality_bp.route("/history/<int:user_id>", methods=["GET"])
def get_user_history(user_id: int):
    """Backward-compatible history endpoint; prefer /me/profiles."""
    authenticated_user_id, error = _auth_user_id()
    if error:
        return error
    if not assert_self_user_id(user_id, authenticated_user_id):
        return jsonify({"code": 403, "msg": "无权访问该用户数据"}), 403
    try:
        return _success(list_profiles(user_id))
    except Exception as exc:
        return jsonify({"code": 500, "msg": f"服务器错误: {exc}"}), 500
