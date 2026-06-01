"""人格测评业务逻辑。"""
from __future__ import annotations

import json

from app.db import db_cursor
from app.domains.personality.mbti_data import (
    complete_analysis as mbti_complete,
    dimension_analysis as mbti_dimension,
    job_recommendations as mbti_jobs,
)

def calculate_mbti(answers):
    """根据答案计算MBTI类型"""
    dimensions = {
        'E': 0, 'I': 0,
        'S': 0, 'N': 0,
        'T': 0, 'F': 0,
        'J': 0, 'P': 0
    }

    with db_cursor() as (_, cur):
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

    # 确定MBTI类型
    mbti = ''
    mbti += 'E' if dimensions['E'] > dimensions['I'] else 'I'
    mbti += 'S' if dimensions['S'] > dimensions['N'] else 'N'
    mbti += 'T' if dimensions['T'] > dimensions['F'] else 'F'
    mbti += 'J' if dimensions['J'] > dimensions['P'] else 'P'

    return mbti, dimensions

def generate_dimension_analysis(dimensions):
    """生成四维度详细分析"""
    analysis = []

    # 能量来源维度
    ei_result = 'E' if dimensions['E'] >= dimensions['I'] else 'I'
    ei_data = mbti_dimension()[ei_result]
    analysis.append({
        "dimension": "能量来源",
        "type": ei_result,
        "name": ei_data["name"],
        "description": ei_data["description"],
        "characteristics": ei_data["characteristics"],
        "work_preference": ei_data["work_preference"],
        "growth_suggestions": ei_data["growth_suggestions"]
    })

    # 信息获取维度
    sn_result = 'S' if dimensions['S'] >= dimensions['N'] else 'N'
    sn_data = mbti_dimension()[sn_result]
    analysis.append({
        "dimension": "信息获取",
        "type": sn_result,
        "name": sn_data["name"],
        "description": sn_data["description"],
        "characteristics": sn_data["characteristics"],
        "work_preference": sn_data["work_preference"],
        "growth_suggestions": sn_data["growth_suggestions"]
    })

    # 决策方式维度
    tf_result = 'T' if dimensions['T'] >= dimensions['F'] else 'F'
    tf_data = mbti_dimension()[tf_result]
    analysis.append({
        "dimension": "决策方式",
        "type": tf_result,
        "name": tf_data["name"],
        "description": tf_data["description"],
        "characteristics": tf_data["characteristics"],
        "work_preference": tf_data["work_preference"],
        "growth_suggestions": tf_data["growth_suggestions"]
    })

    # 生活方式维度
    jp_result = 'J' if dimensions['J'] >= dimensions['P'] else 'P'
    jp_data = mbti_dimension()[jp_result]
    analysis.append({
        "dimension": "生活方式",
        "type": jp_result,
        "name": jp_data["name"],
        "description": jp_data["description"],
        "characteristics": jp_data["characteristics"],
        "work_preference": jp_data["work_preference"],
        "growth_suggestions": jp_data["growth_suggestions"]
    })

    return analysis

def generate_complete_analysis(mbti_type):
    """生成完整的MBTI类型分析"""
    complete_data = mbti_complete().get(mbti_type, {})

    return {
        "type": mbti_type,
        "name": complete_data.get("name", ""),
        "summary": complete_data.get("summary", ""),
        "core_strengths": complete_data.get("core_strengths", []),
        "career_tendencies": complete_data.get("career_tendencies", []),
        "workplace_relationships": complete_data.get("workplace_relationships", []),
        "development_areas": complete_data.get("development_areas", []),
        "stress_response": complete_data.get("stress_response", "")
    }

def generate_job_recommendations(mbti_type):
    """生成岗位推荐"""
    job_data = mbti_jobs().get(mbti_type, {})

    return {
        "recommended_jobs": job_data.get("recommended_jobs", []),
        "career_advice": job_data.get("career_advice", "")
    }
def generate_comprehensive_report(mbti_type, dimension_analysis, complete_analysis, job_recommendations):
    """生成综合性格分析报告"""
    report = f"""您的MBTI性格类型为{mbti_type}（{complete_analysis['name']}），{complete_analysis['summary']}

【性格核心特征】
"""
    for strength in complete_analysis.get("core_strengths", []):
        report += f"• {strength}\n"

    report += "\n【工作环境偏好】\n"
    for tendency in complete_analysis.get("career_tendencies", []):
        report += f"• {tendency}\n"

    report += "\n【职场人际关系】\n"
    for relationship in complete_analysis.get("workplace_relationships", []):
        report += f"• {relationship}\n"

    report += "\n【个人发展建议】\n"
    for area in complete_analysis.get("development_areas", []):
        report += f"• {area}\n"

    report += f"\n【压力应对方式】\n{complete_analysis.get('stress_response', '')}\n"

    report += f"\n【推荐岗位】\n"
    for job in job_recommendations.get("recommended_jobs", []):
        report += f"• {job}\n"

    report += f"\n【职业发展建议】\n{job_recommendations.get('career_advice', '')}\n"

    return report
def call_qwen_model(mbti_type, dimension_analysis):
    """调用千问大模型生成更详细的性格分析"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.DASHSCOPE_API_KEY}"
    }

    dimension_info = "\n".join([
        f"{d['dimension']}（{d['type']}）：{d['description']}"
        for d in dimension_analysis
    ])

    data = {
        "model": "qwen-turbo",
        "input": f"""请为MBTI类型为{mbti_type}的人生成一份详细的专业性格分析报告。

维度分析：
{dimension_info}

请从以下方面进行分析：
1. 性格优势：详细描述该类型的核心优势和天赋
2. 潜在挑战：该类型可能面临的困难和挑战
3. 职场表现：该类型在工作中的典型行为模式
4. 人际交往：该类型与人相处的方式和偏好
5. 发展建议：具体的个人成长和职业发展建议
6. 领导风格：如果成为管理者，该类型的领导风格特点

请用专业、温暖、鼓励的语气撰写报告，内容要详尽深入（不少于800字），让读者能够真正了解自己并获得启发。""",
        "parameters": {
            "max_tokens": 1000,
            "temperature": 0.7
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()

        if result.get('output') and result['output'].get('text'):
            return result['output']['text']
        else:
            raise Exception('Failed to generate analysis')
    except Exception as e:
        print(f"调用千问模型失败: {e}")
        return None
