from decimal import Decimal

from flask import Blueprint, request, jsonify, current_app
import os
import json
import pymysql

from app.auth import get_bearer_user_id
from app.config import Config
from app.utils import ocr_image, pdf_to_image, score_resume, create_radar_chart

portrait_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


def _jsonable_row(row: dict | None) -> dict | None:
    if not row:
        return row
    out: dict = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out

def get_db():
    """自己实现数据库连接,不依赖项目db.py,零冲突"""
    return pymysql.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor
    )

# ===================== 行业能力要求数据 =====================
INDUSTRY_REQUIREMENTS = {
    "互联网/IT": {
        "权重": {"cap_req_theory": 0.15, "cap_req_cross": 0.10, "cap_req_practice": 0.25, "cap_req_digital": 0.20, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.05, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_practice", "cap_req_digital", "cap_req_theory"],
        "描述": "互联网/IT行业注重技术实践能力和数字素养，需要具备扎实的专业基础和持续学习能力"
    },
    "金融/银行": {
        "权重": {"cap_req_theory": 0.25, "cap_req_cross": 0.10, "cap_req_practice": 0.15, "cap_req_digital": 0.15, "cap_req_innovation": 0.05, "cap_req_teamwork": 0.10, "cap_req_social": 0.15, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_social", "cap_req_digital"],
        "描述": "金融行业注重专业理论知识和社交网络，需要具备扎实的金融理论基础和良好的职业素养"
    },
    "教育/培训": {
        "权重": {"cap_req_theory": 0.25, "cap_req_cross": 0.15, "cap_req_practice": 0.15, "cap_req_digital": 0.10, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.10, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_teamwork", "cap_req_social"],
        "描述": "教育培训行业注重专业理论知识和团队协作能力，需要具备良好的表达能力和持续学习精神"
    },
    "制造/工程": {
        "权重": {"cap_req_theory": 0.25, "cap_req_cross": 0.10, "cap_req_practice": 0.25, "cap_req_digital": 0.10, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.05, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_practice", "cap_req_innovation"],
        "描述": "制造工程行业注重专业理论和实践技能，需要具备扎实的工程基础和创新思维"
    },
    "医疗/健康": {
        "权重": {"cap_req_theory": 0.30, "cap_req_cross": 0.10, "cap_req_practice": 0.20, "cap_req_digital": 0.10, "cap_req_innovation": 0.05, "cap_req_teamwork": 0.10, "cap_req_social": 0.10, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_practice", "cap_req_teamwork"],
        "描述": "医疗健康行业注重专业理论知识和实践技能，需要具备扎实的医学基础和高度的责任心"
    },
    "销售/市场": {
        "权重": {"cap_req_theory": 0.10, "cap_req_cross": 0.15, "cap_req_practice": 0.10, "cap_req_digital": 0.15, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.15, "cap_req_social": 0.20, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_social", "cap_req_teamwork", "cap_req_digital"],
        "描述": "销售市场行业注重社交网络和团队协作能力，需要具备良好的沟通能力和市场洞察力"
    },
    "政府/事业单位": {
        "权重": {"cap_req_theory": 0.20, "cap_req_cross": 0.15, "cap_req_practice": 0.15, "cap_req_digital": 0.10, "cap_req_innovation": 0.05, "cap_req_teamwork": 0.15, "cap_req_social": 0.15, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_teamwork", "cap_req_social"],
        "描述": "政府事业单位注重综合素质和服务意识，需要具备扎实的理论基础和良好的职业素养"
    },
    "咨询/专业服务": {
        "权重": {"cap_req_theory": 0.15, "cap_req_cross": 0.20, "cap_req_practice": 0.15, "cap_req_digital": 0.10, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.15, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_cross", "cap_req_social", "cap_req_theory"],
        "描述": "咨询专业服务行业注重跨学科能力和社交网络，需要具备广博的知识面和良好的分析能力"
    }
}

# ===================== 能力维度中文名称映射 =====================
DIMENSION_NAMES = {
    "cap_req_theory": "专业理论知识",
    "cap_req_cross": "交叉学科广度",
    "cap_req_practice": "专业实践技能",
    "cap_req_digital": "数字素养技能",
    "cap_req_innovation": "创新创业能力",
    "cap_req_teamwork": "团队协作能力",
    "cap_req_social": "社会实践网络",
    "cap_req_growth": "学习与发展潜力"
}

# ===================== 能力提升建议库 =====================
SKILL_IMPROVEMENT_SUGGESTIONS = {
    "cap_req_theory": {
        "短期": [
            "参加专业相关的在线课程（Coursera、MOOC等平台）",
            "阅读2-3本专业核心教材和参考书目",
            "整理并复习专业课程笔记，构建知识图谱",
            "参加专业讲座和学术报告，了解学科前沿动态"
        ],
        "长期": [
            "考取相关专业资格证书（如CPA、PMP、司考等）",
            "参与科研项目或学术论文写作",
            "建立个人专业博客或技术文档库",
            "定期阅读行业白皮书和研究报告"
        ]
    },
    "cap_req_cross": {
        "短期": [
            "选修1-2门跨学科选修课",
            "参加跨学科讲座或工作坊",
            "阅读不同领域的科普书籍",
            "加入跨学科学习小组"
        ],
        "长期": [
            "辅修或双学位学习",
            "参与跨学科项目实践",
            "建立跨学科人脉网络",
            "培养T型知识结构（深耕一个领域的同时拓展相关领域）"
        ]
    },
    "cap_req_practice": {
        "短期": [
            "完成课程设计和实验报告",
            "参加专业技能竞赛",
            "申请实验室或课题组助研岗位",
            "使用所学知识解决一个实际问题"
        ],
        "长期": [
            "寻找与专业相关的实习机会",
            "参与企业实际项目或课题研究",
            "建立个人项目作品集（GitHub、Portfolio）",
            "考取行业认可的技术认证"
        ]
    },
    "cap_req_digital": {
        "短期": [
            "学习办公软件高级功能（Excel数据分析、PPT设计）",
            "掌握文献管理工具（EndNote、Zotero）",
            "学习基础编程技能（Python、R）",
            "了解AI工具的基本原理和应用场景"
        ],
        "长期": [
            "学习数据分析和可视化工具",
            "掌握机器学习和人工智能基础",
            "建立数据分析项目经验",
            "探索数字技术在专业领域的应用"
        ]
    },
    "cap_req_innovation": {
        "短期": [
            "参加创新思维训练工作坊",
            "尝试用新方法解决熟悉的问题",
            "记录并分析创新想法",
            "参与头脑风暴活动"
        ],
        "长期": [
            "参加创新创业大赛",
            "尝试将创意转化为实际项目",
            "申请发明专利或软件著作权",
            "关注并分析行业创新趋势"
        ]
    },
    "cap_req_teamwork": {
        "短期": [
            "在课程项目中主动承担不同角色",
            "学习团队协作工具（Notion、Trello、飞书）",
            "参加团队体育运动或集体活动",
            "练习有效的会议组织和时间管理"
        ],
        "长期": [
            "争取学生组织或社团的组织管理机会",
            "参与跨部门或跨专业合作项目",
            "学习冲突管理和团队激励技巧",
            "培养服务意识和领导者视野"
        ]
    },
    "cap_req_social": {
        "短期": [
            "主动与同学、老师建立联系",
            "参加学术会议或行业活动",
            "维护和拓展社交媒体专业网络",
            "学习职业礼仪和沟通技巧"
        ],
        "长期": [
            "建立个人职业社交圈",
            "寻找行业导师或职业榜样",
            "参与行业协会或专业社群",
            "维护和发展长期人际关系网络"
        ]
    },
    "cap_req_growth": {
        "短期": [
            "制定个人学习计划和目标",
            "养成每日阅读和反思的习惯",
            "记录学习笔记和成长日志",
            "寻求反馈并持续改进"
        ],
        "长期": [
            "建立个人知识管理体系（PKM）",
            "培养元认知能力和学习方法论",
            "关注行业趋势和新兴技术",
            "制定并执行3-5年职业发展规划"
        ]
    }
}

def calculate_industry_match(scores):
    """计算用户与各行业的匹配度"""
    results = []
    for industry, req in INDUSTRY_REQUIREMENTS.items():
        weighted_sum = 0
        for dim, weight in req["权重"].items():
            weighted_sum += scores.get(dim, 60) * weight

        # 计算与核心能力的匹配度
        core_match = sum([scores.get(cap, 60) for cap in req["核心能力"]]) / len(req["核心能力"])

        # 综合得分
        total_score = (weighted_sum * 0.6 + core_match * 0.4)

        results.append({
            "industry": industry,
            "match_score": round(total_score, 1),
            "description": req["描述"],
            "core_abilities": [DIMENSION_NAMES[c] for c in req["核心能力"]]
        })

    # 按匹配度排序
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results

def generate_short_term_plan(scores):
    """生成短期提升计划（3-6个月）"""
    # 选择分数在40-70分之间的维度作为提升目标
    improvement_targets = []
    for dim, score in scores.items():
        if 40 <= score <= 70:
            improvement_targets.append((dim, score))

    # 按分数升序排列，优先提升较低分数的维度
    improvement_targets.sort(key=lambda x: x[1])

    # 选择2-3个最需要提升的维度
    top_targets = improvement_targets[:3]

    plan = []
    for dim, score in top_targets:
        suggestions = SKILL_IMPROVEMENT_SUGGESTIONS.get(dim, {}).get("短期", [])
        plan.append({
            "dimension": DIMENSION_NAMES.get(dim, dim),
            "current_score": score,
            "suggestions": suggestions[:2]  # 每个维度提供2条短期建议
        })

    return plan

def generate_long_term_goals(scores):
    """生成长期发展目标（1-2年）"""
    # 选择分数低于50或高于70的维度
    goals = []

    for dim, score in scores.items():
        if score < 50:
            # 低分维度作为需要重点培养的能力
            suggestions = SKILL_IMPROVEMENT_SUGGESTIONS.get(dim, {}).get("长期", [])
            goals.append({
                "dimension": DIMENSION_NAMES.get(dim, dim),
                "current_score": score,
                "goal_type": "重点培养",
                "suggestions": suggestions[:2]
            })
        elif score > 80:
            # 高分维度作为可以深化的优势
            suggestions = SKILL_IMPROVEMENT_SUGGESTIONS.get(dim, {}).get("长期", [])
            goals.append({
                "dimension": DIMENSION_NAMES.get(dim, dim),
                "current_score": score,
                "goal_type": "深化优势",
                "suggestions": suggestions[:2]
            })

    # 按分数升序排列
    goals.sort(key=lambda x: x["current_score"])
    return goals[:4]  # 最多返回4个目标

def extract_resume_keywords(resume_text):
    """提取简历关键词并分析"""
    # 常见技能关键词库
    skill_keywords = {
        "编程语言": ["Python", "Java", "C++", "JavaScript", "Go", "Rust", "SQL", "R", "MATLAB", "PHP"],
        "框架工具": ["Spring", "Django", "React", "Vue", "Angular", "Node.js", "Flask", "FastAPI", "TensorFlow", "PyTorch"],
        "数据处理": ["Excel", "SPSS", "SAS", "Power BI", "Tableau", "FineBI", "ETL", "Hadoop", "Spark"],
        "设计工具": ["Photoshop", "Illustrator", "Figma", "Sketch", "Premiere", "After Effects"],
        "文档写作": ["Word", "LaTeX", "Markdown", "Notion", "Obsidian"],
        "协作工具": ["Git", "SVN", "Jira", "Confluence", "飞书", "钉钉", "企业微信"],
        "语言能力": ["英语", "CET-4", "CET-6", "IELTS", "TOEFL", "日语", "法语", "德语"],
        "软技能": ["沟通", "协调", "领导", "团队合作", "项目管理", "时间管理", "问题解决", "批判性思维"]
    }

    found_keywords = {category: [] for category in skill_keywords}

    for category, keywords in skill_keywords.items():
        for keyword in keywords:
            if keyword.lower() in resume_text.lower():
                found_keywords[category].append(keyword)

    # 计算技能密度
    total_skills = sum(len(kws) for kws in found_keywords.values())
    skill_density = min(total_skills / 10, 1.0)  # 假设10个技能为理想状态

    return {
        "found_keywords": found_keywords,
        "total_skills": total_skills,
        "skill_density": round(skill_density * 100, 1),
        "suggestions": generate_keyword_suggestions(found_keywords, skill_density)
    }

def generate_keyword_suggestions(found_keywords, skill_density):
    """生成简历关键词优化建议"""
    suggestions = []

    # 检查缺失的技能类别
    missing_categories = [cat for cat, kws in found_keywords.items() if not kws]

    if missing_categories:
        suggestions.append(f"建议补充以下技能领域：{', '.join(missing_categories[:3])}")

    if skill_density < 50:
        suggestions.append("简历中技能关键词较少，建议增加技术技能描述，如熟练使用的工具、掌握的技术栈等")

    # 检查软硬技能比例
    soft_skills = found_keywords.get("软技能", [])
    hard_skills_count = sum(len(kws) for cat, kws in found_keywords.items() if cat != "软技能")

    if len(soft_skills) > hard_skills_count:
        suggestions.append("建议增加更多硬技能描述，如编程语言、工具使用等，使简历更具技术说服力")
    elif len(soft_skills) < 2 and hard_skills_count > 5:
        suggestions.append("建议适当增加软技能描述，如团队协作、沟通能力等，展现综合素质")

    return suggestions

def generate_detailed_analysis(scores, resume_text=""):
    """生成详细的能力分析报告"""
    analysis = {
        "dimension_analysis": [],  # 各维度详细分析
        "advantage_dimensions": [],  # 优势维度
        "劣势_dimensions": [],  # 劣势维度
        "overall_evaluation": "",  # 整体评价
        "short_term_plan": [],  # 短期提升计划
        "long_term_goals": [],  # 长期发展目标
        "industry_match": [],  # 行业适配性分析
        "resume_analysis": {}  # 简历关键词分析
    }

    # 1. 各维度详细分析
    for dim, score in scores.items():
        dim_name = DIMENSION_NAMES.get(dim, dim)
        analysis["dimension_analysis"].append({
            "dimension": dim_name,
            "score": score,
            "level": "高" if score >= 75 else ("中" if score >= 50 else "低"),
            "interpretation": get_dimension_interpretation(dim, score)
        })

    # 2. 优势和劣势维度排序
    sorted_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    analysis["advantage_dimensions"] = [
        {"dimension": DIMENSION_NAMES.get(dim, dim), "score": score}
        for dim, score in sorted_dims[:3]
    ]
    analysis["劣势_dimensions"] = [
        {"dimension": DIMENSION_NAMES.get(dim, dim), "score": score}
        for dim, score in sorted_dims[-3:]
    ]

    # 3. 整体评价
    avg_score = sum(scores.values()) / len(scores)
    analysis["overall_evaluation"] = generate_overall_evaluation(scores, avg_score)

    # 4. 生成发展计划
    analysis["short_term_plan"] = generate_short_term_plan(scores)
    analysis["long_term_goals"] = generate_long_term_goals(scores)

    # 5. 行业适配性分析
    analysis["industry_match"] = calculate_industry_match(scores)

    # 6. 简历关键词分析
    if resume_text:
        analysis["resume_analysis"] = extract_resume_keywords(resume_text)

    return analysis

def get_dimension_interpretation(dim, score):
    """获取维度的详细解读"""
    interpretations = {
        "cap_req_theory": {
            "高": "您展现出扎实的专业理论基础，能够深入理解学科核心概念并灵活应用。建议继续保持理论学习的深度和广度，关注学科前沿动态。",
            "中": "您的专业理论基础处于中等水平，对核心概念有基本理解。建议加强系统性学习，构建完整的知识体系。",
            "低": "您的专业理论基础相对薄弱，建议从核心教材入手，系统性地补足基础知识，建立扎实的理论根基。"
        },
        "cap_req_cross": {
            "高": "您具备优秀的跨学科视野，能够整合多领域知识解决问题。建议继续拓展知识边界，培养T型知识结构。",
            "中": "您有一定的跨学科学习经历，但知识整合能力有待加强。建议选择性学习相关领域课程，培养跨学科思维。",
            "低": "您的知识面相对单一，建议主动学习其他领域的知识，培养跨学科思维和问题解决能力。"
        },
        "cap_req_practice": {
            "高": "您具备丰富的实践经验和出色的动手能力，能够将理论知识转化为实际成果。建议积累更多项目经验，建立个人作品集。",
            "中": "您有一定的实践经验，但项目经历相对有限。建议主动寻找实习和项目机会，提升动手能力。",
            "低": "您的实践经验相对不足，建议从课程项目和基础实验开始，逐步积累实际工作经验。"
        },
        "cap_req_digital": {
            "高": "您具备优秀的数字素养，熟练使用各种数字化工具和平台。建议继续学习数据分析和AI工具，保持技术敏感度。",
            "中": "您基本掌握常用办公软件，但数据分析能力有待提升。建议学习Python、R等数据分析工具。",
            "低": "您的数字化能力需要加强，建议从基础办公软件开始，系统学习数据分析工具和编程技能。"
        },
        "cap_req_innovation": {
            "高": "您具备出色的创新思维和创业精神，善于发现问题和提出新解决方案。建议将创新想法转化为实际项目。",
            "中": "您有一定的创新意识，但创新实践相对有限。建议参与创新竞赛或尝试小规模创新实践。",
            "低": "您的创新思维需要培养，建议多接触新事物，练习发散性思考，积极参与创新活动。"
        },
        "cap_req_teamwork": {
            "高": "您具备优秀的团队协作能力，善于沟通和协调。建议争取团队领导机会，提升项目管理能力。",
            "中": "您能够融入团队工作，但领导协调经验有限。建议在团队项目中主动承担不同角色，积累协作经验。",
            "低": "您的团队协作经验较少，建议积极参与团队活动和学生组织，培养沟通和协调能力。"
        },
        "cap_req_social": {
            "高": "您拥有广泛的社会实践网络和良好的人际关系。建议维护并拓展人脉，为职业发展积累资源。",
            "中": "您有一定的社会实践经历，但人脉网络有限。建议主动参与行业活动，建立职业社交圈。",
            "低": "您的社会实践经验和人脉资源相对不足，建议积极参加社会实践和行业交流，拓展社交网络。"
        },
        "cap_req_growth": {
            "高": "您具备出色的学习能力和成长潜力，能够快速适应新环境。建议制定清晰的职业发展规划，持续提升竞争力。",
            "中": "您有较好的学习能力，但成长目标不够明确。建议设定具体的学习和发展目标，制定实施计划。",
            "低": "您的学习和发展潜力有待挖掘，建议从培养良好学习习惯开始，制定阶段性成长目标。"
        }
    }
    level = "高" if score >= 75 else ("中" if score >= 50 else "低")
    return interpretations.get(dim, {}).get(level, "该维度分析暂未完善。")

def generate_overall_evaluation(scores, avg_score):
    """生成整体评价"""
    # 计算各维度均衡度
    max_score = max(scores.values())
    min_score = min(scores.values())
    balance = 1 - (max_score - min_score) / 100

    # 计算能力分布特征
    high_dims = [DIMENSION_NAMES.get(k, k) for k, v in scores.items() if v >= 75]
    low_dims = [DIMENSION_NAMES.get(k, k) for k, v in scores.items() if v < 50]

    evaluation = f"您的能力雷达图呈现"

    if balance >= 0.8:
        evaluation += "均衡发展型特征，各维度发展较为平衡，没有明显的短板。"
    elif balance >= 0.6:
        evaluation += "略有差异型特征，能力分布相对均衡，但仍有提升空间。"
    else:
        evaluation += "差异明显型特征，能力发展有一定偏向，建议关注薄弱维度。"

    if high_dims:
        evaluation += f"优势维度包括{'、'.join(high_dims)}，这些是您的核心竞争力。"

    if low_dims:
        evaluation += f"需要重点关注的维度包括{'、'.join(low_dims)}，建议制定针对性的提升计划。"

    evaluation += f"综合平均分为{avg_score:.1f}分，整体处于{'优秀' if avg_score >= 75 else ('良好' if avg_score >= 60 else ('中等' if avg_score >= 50 else '较低'))}水平。"

    return evaluation


def _resolve_upload_user_id() -> tuple[int | None, str | None]:
    jwt_uid = get_bearer_user_id()
    raw = request.form.get("user_id")
    if jwt_uid is not None:
        return jwt_uid, None
    if not raw:
        return None, "未登录时请提供 user_id；已登录请携带 Authorization: Bearer"
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, "user_id 格式无效"


@portrait_bp.route("/resumes", methods=["GET"])
def list_my_resumes():
    """当前登录用户的能力画像（简历分析）列表，供人岗匹配选用。"""
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, major, create_time,
              cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
              cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
              completeness, competitiveness
            FROM student_resume
            WHERE user_id = %s
            ORDER BY id DESC
            """,
            (uid,),
        )
        rows = cur.fetchall()
        conn.close()

        out = []
        for r in rows:
            dims = [
                r["cap_req_theory"],
                r["cap_req_cross"],
                r["cap_req_practice"],
                r["cap_req_digital"],
                r["cap_req_innovation"],
                r["cap_req_teamwork"],
                r["cap_req_social"],
                r["cap_req_growth"],
            ]
            nums = [float(x) for x in dims if x is not None]
            score_avg = round(sum(nums) / len(nums), 2) if nums else 0.0
            scores = {
                "cap_req_theory": int(r["cap_req_theory"] or 0),
                "cap_req_cross": int(r["cap_req_cross"] or 0),
                "cap_req_practice": int(r["cap_req_practice"] or 0),
                "cap_req_digital": int(r["cap_req_digital"] or 0),
                "cap_req_innovation": int(r["cap_req_innovation"] or 0),
                "cap_req_teamwork": int(r["cap_req_teamwork"] or 0),
                "cap_req_social": int(r["cap_req_social"] or 0),
                "cap_req_growth": int(r["cap_req_growth"] or 0),
            }
            out.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "major": r["major"],
                    "create_time": str(r["create_time"]) if r.get("create_time") else None,
                    "completeness": r.get("completeness"),
                    "competitiveness": r.get("competitiveness"),
                    "score_avg": score_avg,
                    "scores": scores,
                }
            )

        return jsonify({"code": 200, "msg": "success", "data": out})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500


@portrait_bp.route("/upload", methods=["POST"])
def upload_resume():
    try:
        uid, err = _resolve_upload_user_id()
        if err or uid is None:
            return jsonify({"code": 400, "msg": err or "无法确定用户"}), 400

        name = request.form.get("name")
        major = request.form.get("major")
        file = request.files.get("resume")

        if not all([name, major, file]):
            return jsonify({"code": 400, "msg": "参数不全"}), 400

        upload_dir = os.path.join(current_app.static_folder, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        file.save(file_path)

        if file.filename.lower().endswith(".pdf"):
            ocr_path = pdf_to_image(file_path)
        else:
            ocr_path = file_path

        resume_text = ocr_image(ocr_path)
        scores, confidences = score_resume(resume_text)
        radar_html = create_radar_chart(scores)

        detailed_analysis = generate_detailed_analysis(scores, resume_text)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SHOW COLUMNS FROM student_resume LIKE 'detailed_analysis'")
        has_detailed_analysis = cur.fetchone() is not None

        total = sum(scores.values())
        completeness = total // 8
        competitiveness = total // 8

        row_vals = (
            uid,
            name,
            major,
            resume_text,
            scores["cap_req_theory"],
            scores["cap_req_cross"],
            scores["cap_req_practice"],
            scores["cap_req_digital"],
            scores["cap_req_innovation"],
            scores["cap_req_teamwork"],
            scores["cap_req_social"],
            scores["cap_req_growth"],
            confidences["cap_conf_theory"],
            confidences["cap_conf_cross"],
            confidences["cap_conf_practice"],
            confidences["cap_conf_digital"],
            confidences["cap_conf_innovation"],
            confidences["cap_conf_teamwork"],
            confidences["cap_conf_social"],
            confidences["cap_conf_growth"],
            completeness,
            competitiveness,
            radar_html,
        )

        if has_detailed_analysis:
            sql = """
            INSERT INTO student_resume
            (user_id, name, major, resume_text,
            cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
            cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
            cap_conf_theory, cap_conf_cross, cap_conf_practice, cap_conf_digital,
            cap_conf_innovation, cap_conf_teamwork, cap_conf_social, cap_conf_growth,
            completeness, competitiveness, radar_html, detailed_analysis)
            VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s)
            """
            cur.execute(
                sql,
                row_vals + (json.dumps(detailed_analysis, ensure_ascii=False, indent=2),),
            )
        else:
            sql = """
            INSERT INTO student_resume
            (user_id, name, major, resume_text,
            cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
            cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
            cap_conf_theory, cap_conf_cross, cap_conf_practice, cap_conf_digital,
            cap_conf_innovation, cap_conf_teamwork, cap_conf_social, cap_conf_growth,
            completeness, competitiveness, radar_html)
            VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s)
            """
            cur.execute(sql, row_vals)

        conn.commit()
        resume_id = cur.lastrowid
        conn.close()

        return jsonify(
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "resume_id": resume_id,
                    "scores": scores,
                    "confidences": confidences,
                    "completeness": completeness,
                    "competitiveness": competitiveness,
                    "detailed_analysis": detailed_analysis,
                },
            }
        )
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500


@portrait_bp.route("/result/<int:resume_id>", methods=["GET"])
def get_result(resume_id):
    try:
        uid = get_bearer_user_id()
        conn = get_db()
        cur = conn.cursor()
        if uid is not None:
            cur.execute(
                "SELECT * FROM student_resume WHERE id = %s AND user_id = %s",
                (resume_id, uid),
            )
        else:
            cur.execute("SELECT * FROM student_resume WHERE id = %s", (resume_id,))
        result = cur.fetchone()
        conn.close()
        if not result:
            return jsonify({"code": 404, "msg": "结果不存在或无权查看"}), 404

        if result.get("detailed_analysis") and isinstance(result["detailed_analysis"], str):
            result["detailed_analysis"] = json.loads(result["detailed_analysis"])

        return jsonify({"code": 200, "data": _jsonable_row(result)})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"错误: {str(e)}"}), 500

@portrait_bp.route('/history/<int:user_id>', methods=['GET'])
def get_user_history(user_id):
    """获取用户的历史能力画像记录"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, major, create_time,
            cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
            cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
            completeness, competitiveness
            FROM student_resume
            WHERE user_id = %s
            ORDER BY create_time DESC
        """, (user_id,))
        results = cur.fetchall()
        conn.close()

        # 解析每个记录的能力数据
        history = []
        for r in results:
            history.append({
                "id": r["id"],
                "name": r["name"],
                "major": r["major"],
                "create_time": r["create_time"].isoformat() if r.get("create_time") else None,
                "scores": {
                    "cap_req_theory": r["cap_req_theory"],
                    "cap_req_cross": r["cap_req_cross"],
                    "cap_req_practice": r["cap_req_practice"],
                    "cap_req_digital": r["cap_req_digital"],
                    "cap_req_innovation": r["cap_req_innovation"],
                    "cap_req_teamwork": r["cap_req_teamwork"],
                    "cap_req_social": r["cap_req_social"],
                    "cap_req_growth": r["cap_req_growth"]
                },
                "completeness": r["completeness"],
                "competitiveness": r["competitiveness"]
            })

        return jsonify({"code": 200, "data": history})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"错误: {str(e)}"}), 500

@portrait_bp.route('/trend/<int:user_id>', methods=['GET'])
def get_ability_trend(user_id):
    """获取用户能力变化趋势"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, create_time,
            cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
            cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
            completeness, competitiveness
            FROM student_resume
            WHERE user_id = %s
            ORDER BY create_time ASC
        """, (user_id,))
        results = cur.fetchall()
        conn.close()

        if not results:
            return jsonify({"code": 404, "msg": "暂无历史数据"}), 404

        trend = []
        for r in results:
            trend.append({
                "id": r["id"],
                "date": r["create_time"].isoformat() if r.get("create_time") else None,
                "scores": {
                    "cap_req_theory": r["cap_req_theory"],
                    "cap_req_cross": r["cap_req_cross"],
                    "cap_req_practice": r["cap_req_practice"],
                    "cap_req_digital": r["cap_req_digital"],
                    "cap_req_innovation": r["cap_req_innovation"],
                    "cap_req_teamwork": r["cap_req_teamwork"],
                    "cap_req_social": r["cap_req_social"],
                    "cap_req_growth": r["cap_req_growth"]
                },
                "completeness": r["completeness"],
                "competitiveness": r["competitiveness"]
            })

        # 计算变化趋势
        if len(trend) >= 2:
            latest = trend[-1]["scores"]
            previous = trend[-2]["scores"]
            changes = {}
            for dim in latest:
                diff = latest[dim] - previous[dim]
                changes[dim] = {
                    "change": round(diff, 1),
                    "direction": "上升" if diff > 0 else ("下降" if diff < 0 else "持平"),
                    "percentage": round((diff / previous[dim]) * 100, 1) if previous[dim] != 0 else 0
                }
            trend[-1]["changes"] = changes

        return jsonify({"code": 200, "data": trend})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"错误: {str(e)}"}), 500
