"""人格测评 HTTP 路由。"""
from __future__ import annotations

import json

import requests
from flask import Blueprint, jsonify, request

from app.core.config import Config
from app.core.security import assert_self_user_id, get_bearer_user_id
from app.db import db_cursor
from app.domains.personality.services import (
    calculate_mbti,
    generate_complete_analysis,
    generate_comprehensive_report,
    generate_dimension_analysis,
    generate_job_recommendations,
)

personality_bp = Blueprint("personality", __name__, url_prefix="/api/personality")

@personality_bp.route('/questions', methods=['GET'])
def get_questions():
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT * FROM personality_test_questions ORDER BY id")
            questions = cur.fetchall()
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": questions
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500

@personality_bp.route('/submit', methods=['POST'])
def submit_answers():
    try:
        uid = get_bearer_user_id()
        if uid is None:
            return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401

        data = request.get_json(silent=True) or {}
        answers = data.get('answers')

        if not answers or not isinstance(answers, list):
            return jsonify({"code": 400, "msg": "参数不全"}), 400

        # 计算MBTI类型和维度统计
        mbti_type, dimensions = calculate_mbti(answers)

        # 生成详细分析
        dimension_analysis = generate_dimension_analysis(dimensions)
        complete_analysis = generate_complete_analysis(mbti_type)
        job_recommendations = generate_job_recommendations(mbti_type)

        # 生成综合分析报告
        personality_analysis = generate_comprehensive_report(
            mbti_type,
            dimension_analysis,
            complete_analysis,
            job_recommendations
        )

        with db_cursor() as (_, cur):
            for answer in answers:
                cur.execute(
                    "INSERT INTO personality_test_answers (user_id, question_id, user_choice) VALUES (%s, %s, %s)",
                    (uid, answer['question_id'], answer['user_choice'])
                )

            cur.execute("SHOW COLUMNS FROM personality_profiles LIKE 'detailed_analysis'")
            has_detailed_analysis = cur.fetchone() is not None

            if has_detailed_analysis:
                cur.execute(
                    """INSERT INTO personality_profiles
                    (user_id, mbti_type, personality_analysis, recommended_jobs, detailed_analysis)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (uid, mbti_type, personality_analysis, ", ".join(job_recommendations["recommended_jobs"]),
                     json.dumps({
                         "dimension_analysis": dimension_analysis,
                         "complete_analysis": complete_analysis,
                         "job_recommendations": job_recommendations
                     }, ensure_ascii=False))
                )
            else:
                cur.execute(
                    """INSERT INTO personality_profiles
                    (user_id, mbti_type, personality_analysis, recommended_jobs)
                    VALUES (%s, %s, %s, %s)""",
                    (uid, mbti_type, personality_analysis, ", ".join(job_recommendations["recommended_jobs"]))
                )

            profile_id = cur.lastrowid

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "mbti_type": mbti_type,
                "personality_analysis": personality_analysis,
                "recommended_jobs": job_recommendations["recommended_jobs"],
                "dimension_analysis": dimension_analysis,
                "complete_analysis": complete_analysis,
                "job_recommendations": job_recommendations,
                "profile_id": profile_id
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500
@personality_bp.route('/profile/<int:profile_id>', methods=['GET'])
def get_profile(profile_id):
    """获取性格测试结果"""
    try:
        uid = get_bearer_user_id()
        if uid is None:
            return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401

        with db_cursor() as (_, cur):
            cur.execute(
                "SELECT * FROM personality_profiles WHERE id = %s AND user_id = %s",
                (profile_id, uid),
            )
            result = cur.fetchone()

        if not result:
            return jsonify({"code": 404, "msg": "结果不存在"}), 404

        # 解析详细分析
        if result.get('detailed_analysis') and isinstance(result['detailed_analysis'], str):
            result['detailed_analysis'] = json.loads(result['detailed_analysis'])

        return jsonify({"code": 200, "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500

@personality_bp.route('/history/<int:user_id>', methods=['GET'])
def get_user_history(user_id):
    """获取用户的历史性格测试记录"""
    try:
        uid = get_bearer_user_id()
        if uid is None:
            return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401
        if not assert_self_user_id(user_id, uid):
            return jsonify({"code": 403, "msg": "无权访问该用户数据"}), 403

        with db_cursor() as (_, cur):
            cur.execute("""
                SELECT id, mbti_type, personality_analysis, recommended_jobs, created_at
                FROM personality_profiles
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            results = cur.fetchall()

        history = []
        for r in results:
            history.append({
                "id": r["id"],
                "mbti_type": r["mbti_type"],
                "personality_analysis": r["personality_analysis"],
                "recommended_jobs": r["recommended_jobs"],
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None
            })

        return jsonify({"code": 200, "data": history})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500
