from flask import Blueprint, request, jsonify, current_app
import os
import json
import pymysql
import requests
import re

from app.config import Config

personality_bp = Blueprint('personality', __name__, url_prefix='/api/personality')


def get_db():
    """自己实现数据库连接，不依赖项目db.py，零冲突"""
    return pymysql.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor
    )

@personality_bp.route('/questions', methods=['GET'])
def get_questions():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM personality_test_questions ORDER BY id")
        questions = cur.fetchall()
        conn.close()
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
        data = request.get_json()
        user_id = data.get('user_id')
        answers = data.get('answers')

        if not user_id or not answers:
            return jsonify({"code": 400, "msg": "参数不全"}), 400

        # 计算MBTI类型
        mbti_type = calculate_mbti(answers)

        # 生成性格分析
        personality_analysis = generate_personality_analysis(mbti_type)

        # 推荐岗位
        recommended_jobs = generate_recommended_jobs(mbti_type)

        # 保存答案
        conn = get_db()
        cur = conn.cursor()
        for answer in answers:
            cur.execute(
                "INSERT INTO personality_test_answers (user_id, question_id, user_choice) VALUES (%s, %s, %s)",
                (user_id, answer['question_id'], answer['user_choice'])
            )

        # 保存人物画像
        cur.execute(
            "INSERT INTO personality_profiles (user_id, mbti_type, personality_analysis, recommended_jobs) VALUES (%s, %s, %s, %s)",
            (user_id, mbti_type, personality_analysis, recommended_jobs)
        )

        conn.commit()
        conn.close()

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "mbti_type": mbti_type,
                "personality_analysis": personality_analysis,
                "recommended_jobs": recommended_jobs
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500

def calculate_mbti(answers):
    """根据答案计算MBTI类型"""
    # 统计各维度的选择
    dimensions = {
        'E': 0, 'I': 0,
        'S': 0, 'N': 0,
        'T': 0, 'F': 0,
        'J': 0, 'P': 0
    }

    conn = get_db()
    cur = conn.cursor()

    for answer in answers:
        cur.execute(
            "SELECT dimension, option_a_type, option_b_type FROM personality_test_questions WHERE id = %s",
            (answer['question_id'],)
        )
        question = cur.fetchone()
        if question:
            if answer['user_choice'] == 'A':
                dimensions[question['option_a_type']] += 1
            else:
                dimensions[question['option_b_type']] += 1

    conn.close()

    # 确定MBTI类型
    mbti = ''
    mbti += 'E' if dimensions['E'] > dimensions['I'] else 'I'
    mbti += 'S' if dimensions['S'] > dimensions['N'] else 'N'
    mbti += 'T' if dimensions['T'] > dimensions['F'] else 'F'
    mbti += 'J' if dimensions['J'] > dimensions['P'] else 'P'

    return mbti

def generate_personality_analysis(mbti_type):
    """生成性格分析"""
    # 这里可以调用千问大模型来生成更详细的性格分析
    # 暂时使用预设的分析结果
    analysis_map = {
        'ISTJ': '你是一个安静、严肃的人，注重事实和细节，有责任感，做事有条理，喜欢按照计划执行。你是一个可靠的人，善于完成任务，注重传统和秩序。',
        'ISFJ': '你是一个温暖、体贴的人，注重和谐和人际关系，有强烈的责任感，善于照顾他人。你是一个可靠的人，善于记住细节，注重传统和价值观。',
        'INFJ': '你是一个有洞察力、理想主义的人，注重意义和价值，有强烈的责任感，善于理解他人。你是一个有远见的人，善于规划未来，注重个人成长和发展。',
        'INTJ': '你是一个独立、理性的人，注重逻辑和分析，有强烈的责任感，善于解决问题。你是一个有远见的人，善于规划未来，注重效率和结果。',
        'ISTP': '你是一个冷静、务实的人，注重事实和实际，善于解决问题，喜欢动手实践。你是一个灵活的人，善于适应变化，注重自由和独立。',
        'ISFP': '你是一个温和、敏感的人，注重个人价值观和感受，善于表达自己，喜欢艺术和美学。你是一个灵活的人，善于适应变化，注重个人自由和享受当下。',
        'INFP': '你是一个理想主义、敏感的人，注重个人价值观和意义，善于理解他人，喜欢创造性表达。你是一个灵活的人，善于适应变化，注重个人成长和自我实现。',
        'INTP': '你是一个理性、好奇的人，注重逻辑和分析，善于解决问题，喜欢探索新 ideas。你是一个灵活的人，善于适应变化，注重知识和理解。',
        'ESTP': '你是一个活跃、务实的人，注重事实和实际，善于解决问题，喜欢冒险和挑战。你是一个灵活的人，善于适应变化，注重行动和结果。',
        'ESFP': '你是一个热情、友好的人，注重人际关系和享受当下，善于表达自己，喜欢社交和娱乐。你是一个灵活的人，善于适应变化，注重个人自由和快乐。',
        'ENFP': '你是一个热情、理想主义的人，注重个人价值观和意义，善于理解他人，喜欢创造性表达。你是一个灵活的人，善于适应变化，注重个人成长和自我实现。',
        'ENTP': '你是一个聪明、好奇的人，注重逻辑和分析，善于解决问题，喜欢探索新 ideas。你是一个灵活的人，善于适应变化，注重知识和理解。',
        'ESTJ': '你是一个果断、实际的人，注重事实和细节，有责任感，做事有条理，喜欢按照计划执行。你是一个可靠的人，善于组织和管理，注重传统和秩序。',
        'ESFJ': '你是一个热情、友好的人，注重和谐和人际关系，有强烈的责任感，善于照顾他人。你是一个可靠的人，善于组织和管理，注重传统和价值观。',
        'ENFJ': '你是一个热情、理想主义的人，注重意义和价值，有强烈的责任感，善于理解他人。你是一个有远见的人，善于领导和激励，注重个人成长和发展。',
        'ENTJ': '你是一个果断、理性的人，注重逻辑和分析，有强烈的责任感，善于解决问题。你是一个有远见的人，善于领导和规划，注重效率和结果。'
    }

    # 调用千问大模型生成更详细的分析
    if Config.DASHSCOPE_API_KEY:
        try:
            analysis = call_qwen_model(mbti_type)
            return analysis
        except Exception as e:
            print(f"调用千问模型失败: {e}")
            # 如果调用失败，使用预设的分析结果
            return analysis_map.get(mbti_type, '你的性格独特而复杂，需要进一步了解。')
    else:
        return analysis_map.get(mbti_type, '你的性格独特而复杂，需要进一步了解。')

def generate_recommended_jobs(mbti_type):
    """生成推荐岗位"""
    # 这里可以根据MBTI类型推荐适合的岗位
    # 暂时使用预设的推荐岗位
    jobs_map = {
        'ISTJ': '会计师、审计师、工程师、项目经理、律师、教师',
        'ISFJ': '护士、教师、社会工作者、行政助理、人力资源专员、咨询师',
        'INFJ': '咨询师、心理学家、教师、社会工作者、作家、艺术家',
        'INTJ': '工程师、科学家、设计师、项目经理、企业家、咨询师',
        'ISTP': '工程师、技术员、运动员、警察、消防员、手工艺人',
        'ISFP': '艺术家、设计师、音乐家、护士、教师、社会工作者',
        'INFP': '作家、艺术家、咨询师、心理学家、教师、社会工作者',
        'INTP': '科学家、工程师、程序员、设计师、哲学家、分析师',
        'ESTP': '企业家、销售、运动员、警察、消防员、技术员',
        'ESFP': '销售、演员、音乐家、教师、护士、社会工作者',
        'ENFP': '销售、教师、咨询师、艺术家、作家、企业家',
        'ENTP': '企业家、设计师、程序员、分析师、咨询师、记者',
        'ESTJ': '项目经理、企业家、律师、教师、行政主管、军官',
        'ESFJ': '教师、护士、社会工作者、销售、人力资源专员、行政主管',
        'ENFJ': '教师、咨询师、社会工作者、销售、企业家、政治家',
        'ENTJ': '企业家、项目经理、军官、律师、行政主管、咨询师'
    }

    return jobs_map.get(mbti_type, '根据你的性格特点，适合的岗位需要进一步评估。')

def call_qwen_model(mbti_type):
    """调用千问大模型生成性格分析"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.DASHSCOPE_API_KEY}"
    }
    data = {
        "model": "qwen-turbo",
        "input": f"请为MBTI类型为{mbti_type}的人生成一份详细的性格分析，包括性格特点、优势、劣势、适合的工作环境和职业发展建议。分析要专业、详细，并且易于理解。",
        "parameters": {
            "max_tokens": 500,
            "temperature": 0.7
        }
    }

    response = requests.post(url, headers=headers, json=data)
    result = response.json()

    if result.get('output') and result['output'].get('text'):
        return result['output']['text']
    else:
        raise Exception('Failed to generate analysis')
