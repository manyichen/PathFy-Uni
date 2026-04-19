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

# ===================== MBTI四维度详细分析数据 =====================
MBTI_DIMENSION_ANALYSIS = {
    "E": {
        "name": "外向型（Extraversion）",
        "energy_direction": "能量来源",
        "description": "你倾向于从外部世界和人际交往中获得能量",
        "characteristics": [
            "喜欢与人交流和互动，容易认识新朋友",
            "喜欢在团队中工作，享受协作的乐趣",
            "善于表达自己的想法和感受",
            "倾向于快速做出决策和行动",
            "喜欢多样性，容易适应新环境"
        ],
        "work_preference": [
            "适合需要大量人际互动的工作",
            "偏好团队协作的工作环境",
            "喜欢快速变化的工作节奏",
            "倾向于公开讨论和头脑风暴"
        ],
        "growth_suggestions": [
            "培养独处和深度思考的能力",
            "学习在决策前收集更多信息",
            "练习倾听和理解不同观点",
            "培养专注力和耐心"
        ]
    },
    "I": {
        "name": "内向型（Introversion）",
        "energy_direction": "能量来源",
        "description": "你倾向于从内部世界和独处中获得能量",
        "characteristics": [
            "喜欢深度思考和内省",
            "善于独立工作，享受独处时间",
            "倾向于在表达前深思熟虑",
            "喜欢深度而非广度的交流",
            "倾向于专注和持续的工作节奏"
        ],
        "work_preference": [
            "适合需要深度专注的工作",
            "偏好独立或小团队的工作环境",
            "喜欢有计划和可预测的工作节奏",
            "倾向于书面沟通和深度讨论"
        ],
        "growth_suggestions": [
            "主动走出舒适区，参与社交活动",
            "练习在团队中表达自己的想法",
            "学习适应快速变化的环境",
            "培养公开演讲和展示的能力"
        ]
    },
    "S": {
        "name": "感觉型（Sensing）",
        "energy_direction": "信息获取",
        "description": "你倾向于关注具体的、实际的细节",
        "characteristics": [
            "注重事实和具体的数据",
            "善于观察细节和实际情况",
            "喜欢使用既定的程序和方法",
            "注重实用性和可操作性",
            "倾向于谨慎和保守的决策方式"
        ],
        "work_preference": [
            "适合需要处理具体数据和细节的工作",
            "偏好有明确流程和标准的任务",
            "喜欢可预测和稳定的工作环境",
            "倾向于遵循既定的规则和程序"
        ],
        "growth_suggestions": [
            "培养全局思维和战略眼光",
            "练习从宏观角度看待问题",
            "学习接受一定的不确定性",
            "发展创新思维和冒险精神"
        ]
    },
    "N": {
        "name": "直觉型（Intuition）",
        "energy_direction": "信息获取",
        "description": "你倾向于关注可能性和未来的潜力",
        "characteristics": [
            "善于发现模式和联系",
            "喜欢探索新的可能性和创新点子",
            "注重想象力和创造力",
            "倾向于整体把握而非细节",
            "喜欢抽象思维和理论分析"
        ],
        "work_preference": [
            "适合需要创新和战略思考的工作",
            "偏好可以探索新想法的环境",
            "喜欢有挑战性和变化的工作",
            "倾向于追求长远目标"
        ],
        "growth_suggestions": [
            "培养对细节和事实的关注",
            "练习将创意转化为实际行动",
            "学习使用具体数据支持观点",
            "发展项目管理和执行能力"
        ]
    },
    "T": {
        "name": "思维型（Thinking）",
        "energy_direction": "决策方式",
        "description": "你倾向于基于逻辑和客观分析做出决策",
        "characteristics": [
            "注重逻辑和客观分析",
            "善于分析和评估各种选项",
            "倾向于公正和一致的决策",
            "善于发现论证中的漏洞",
            "注重效率和公平性"
        ],
        "work_preference": [
            "适合需要分析和技术能力的工作",
            "偏好基于数据和逻辑的工作环境",
            "喜欢解决复杂问题的挑战",
            "倾向于独立做出客观决策"
        ],
        "growth_suggestions": [
            "关注决策对他人的影响",
            "培养同理心和情感智慧",
            "学习在适当时候考虑情感因素",
            "发展人际沟通和协调能力"
        ]
    },
    "F": {
        "name": "情感型（Feeling）",
        "energy_direction": "决策方式",
        "description": "你倾向于基于个人价值观和情感做出决策",
        "characteristics": [
            "注重人际关系和他人感受",
            "善于理解和关心他人",
            "倾向于创造和谐的工作环境",
            "善于激励和鼓舞他人",
            "注重个人价值观和意义"
        ],
        "work_preference": [
            "适合需要人际沟通和协调的工作",
            "偏好协作和支持性的工作环境",
            "喜欢帮助他人发展的工作",
            "倾向于追求有意义的职业"
        ],
        "growth_suggestions": [
            "培养客观分析和逻辑思维能力",
            "练习在必要时做出艰难的决策",
            "学习接受建设性的批评",
            "发展在压力下保持理性的能力"
        ]
    },
    "J": {
        "name": "判断型（Judging）",
        "energy_direction": "生活方式",
        "description": "你倾向于喜欢有计划、有组织的生活方式",
        "characteristics": [
            "喜欢制定计划并按计划执行",
            "善于组织和管理时间",
            "倾向于按时完成任务和承诺",
            "喜欢明确的目标和截止日期",
            "注重秩序和控制"
        ],
        "work_preference": [
            "适合需要项目管理和组织的岗位",
            "偏好有明确目标和时间表的工作",
            "喜欢有结构和可预测的环境",
            "倾向于在截止日期前完成工作"
        ],
        "growth_suggestions": [
            "培养灵活性和适应性",
            "练习接受变化和不确定性",
            "学习在混乱中保持冷静",
            "发展创造力和即兴发挥的能力"
        ]
    },
    "P": {
        "name": "知觉型（Perceiving）",
        "energy_direction": "生活方式",
        "description": "你倾向于喜欢灵活、开放的生活方式",
        "characteristics": [
            "喜欢保持开放的选择权",
            "善于适应变化和新情况",
            "倾向于灵活而非僵化的计划",
            "喜欢探索和尝试新事物",
            "注重过程而非固定的结果"
        ],
        "work_preference": [
            "适合需要适应性和灵活性的工作",
            "偏好自由度高的工作环境",
            "喜欢可以探索多种可能性的任务",
            "倾向于在压力下表现出色"
        ],
        "growth_suggestions": [
            "培养组织能力和时间管理技巧",
            "练习设定和遵守截止日期",
            "学习提前规划和准备",
            "发展自律和坚持的能力"
        ]
    }
}

# ===================== MBTI完整类型详细分析 =====================
MBTI_COMPLETE_ANALYSIS = {
    "ISTJ": {
        "name": "物流师型",
        "summary": "安静、严肃、可靠、有责任感，是值得信赖的伙伴和朋友",
        "core_strengths": [
            "高度责任感，对承诺认真负责",
            "注重细节，做事有条不紊",
            "脚踏实地，重视实际成果",
            "守时守规矩，尊重传统和秩序",
            "善于组织和管理"
        ],
        "career_tendencies": [
            "偏好稳定、有序的工作环境",
            "适合需要高度精确和责任感的工作",
            "善于管理工作流程和系统"
        ],
        "workplace_relationships": [
            "是团队中可靠的后盾",
            "不善言辞但值得信赖",
            "尊重规则和层级结构"
        ],
        "development_areas": [
            "需要学会灵活应对变化",
            "需要表达情感和感受",
            "需要接受他人的不同工作方式"
        ],
        "stress_response": "在压力下可能变得固执或批判，需要学会放松和接受不完美"
    },
    "ISFJ": {
        "name": "守卫者型",
        "summary": "温暖、体贴、忠诚、有责任感，是家庭的守护者",
        "core_strengths": [
            "温暖善良，善于照顾他人",
            "忠诚可靠，重视承诺",
            "注重细节，观察力强",
            "有责任感，善于完成份内工作",
            "谦逊低调，不追求名利"
        ],
        "career_tendencies": [
            "适合需要细心和耐心的岗位",
            "偏好支持性和帮助他人的工作",
            "善于维护传统和秩序"
        ],
        "workplace_relationships": [
            "是团队的稳定力量",
            "善于记住重要细节和截止日期",
            "不喜欢冲突，追求和谐"
        ],
        "development_areas": [
            "需要学会说\"不\"",
            "需要接受变化和新挑战",
            "需要发展自信和主张"
        ],
        "stress_response": "在压力下可能过度自责或忽视自己需求，需要学会自我关怀"
    },
    "INFJ": {
        "name": "倡导者型",
        "summary": "有理想、有洞察力、善于理解他人，是理想主义者",
        "core_strengths": [
            "富有理想和愿景",
            "洞察力强，善于理解他人",
            "有强烈的价值观和原则",
            "善于影响和激励他人",
            "富有创造力和想象力"
        ],
        "career_tendencies": [
            "适合有意义和目的的工作",
            "偏好创造性和独立的工作",
            "善于战略规划和长远思考"
        ],
        "workplace_relationships": [
            "是深度连接的建立者",
            "有强烈的道德指南针",
            "追求真诚和一致"
        ],
        "development_areas": [
            "需要学会接受不完美",
            "需要设置边界和保护自己",
            "需要将想法付诸实践"
        ],
        "stress_response": "在压力下可能变得理想化或脱离现实，需要保持脚踏实地"
    },
    "INTJ": {
        "name": "建筑师型",
        "summary": "独立、理性、有战略眼光，是天生的领导者",
        "core_strengths": [
            "独立思考能力强",
            "战略眼光和全局思维",
            "分析能力强，善于解决问题",
            "高标准，追求卓越",
            "有决心和毅力"
        ],
        "career_tendencies": [
            "适合需要战略和技术能力的工作",
            "偏好自主和创新",
            "善于规划和执行复杂项目"
        ],
        "workplace_relationships": [
            "是高效和独立的贡献者",
            "尊重能力和专业知识",
            "可能显得冷漠或疏远"
        ],
        "development_areas": [
            "需要发展情商和人际技巧",
            "需要接受他人的帮助",
            "需要关注情感和感受"
        ],
        "stress_response": "在压力下可能变得批判或完美主义，需要学会放松和接受帮助"
    },
    "ISTP": {
        "name": "鉴赏家型",
        "summary": "务实、灵活、善于动手，是解决实际问题的高手",
        "core_strengths": [
            "善于解决实际问题",
            "动手能力强，技术精湛",
            "观察力敏锐，善于发现细节",
            "务实冷静，在压力下表现稳定",
            "灵活适应，善于即兴发挥"
        ],
        "career_tendencies": [
            "适合需要技术能力和动手能力的工作",
            "偏好可以独立工作的环境",
            "善于分析和排除故障"
        ],
        "workplace_relationships": [
            "是安静但可靠的合作伙伴",
            "尊重他人的空间和独立性",
            "不喜欢无意义的规则和会议"
        ],
        "development_areas": [
            "需要发展长期规划能力",
            "需要表达情感和感受",
            "需要保持专注和持续努力"
        ],
        "stress_response": "在压力下可能冲动或冒险，需要谨慎评估风险"
    },
    "ISFP": {
        "name": "探险家型",
        "summary": "温柔、敏感、艺术性强，是美的追求者和生活的艺术家",
        "core_strengths": [
            "艺术感强，善于创造美",
            "温柔敏感，善于理解他人感受",
            "灵活开放，善于适应变化",
            "脚踏实地，注重当下体验",
            "谦逊不张扬"
        ],
        "career_tendencies": [
            "适合需要创造力和审美的工作",
            "偏好自由和灵活的工作环境",
            "善于将创意转化为实际成果"
        ],
        "workplace_relationships": [
            "是温暖和支持性的同事",
            "不喜欢冲突和竞争",
            "需要空间和自由"
        ],
        "development_areas": [
            "需要发展决断力和自信",
            "需要面对困难和挑战",
            "需要规划未来"
        ],
        "stress_response": "在压力下可能逃避或消极，需要学会面对问题"
    },
    "INFP": {
        "name": "调停者型",
        "summary": "理想主义、敏感、有价值观，是梦想家和治愈者",
        "core_strengths": [
            "理想主义，追求意义和价值",
            "富有同理心，善于理解他人",
            "创造力和想象力丰富",
            "灵活开放，接受可能性",
            "有原则，忠于自己的价值观"
        ],
        "career_tendencies": [
            "适合有意义和目的的工作",
            "偏好创造性和独立的工作",
            "善于文字和语言表达"
        ],
        "workplace_relationships": [
            "是深度连接的建立者",
            "追求真诚和一致",
            "不喜欢冲突和竞争"
        ],
        "development_areas": [
            "需要学会说\"不\"",
            "需要将想法付诸行动",
            "需要处理现实问题"
        ],
        "stress_response": "在压力下可能变得理想化或拖延，需要保持行动力"
    },
    "INTP": {
        "name": "逻辑学家型",
        "summary": "好奇、理性、分析性强，是思想的哲学家",
        "core_strengths": [
            "逻辑思维和分析能力强",
            "知识渊博，好奇心强",
            "善于发现模式和问题",
            "客观理性，不受情感影响",
            "富有创造力和想象力"
        ],
        "career_tendencies": [
            "适合需要分析和技术能力的工作",
            "偏好独立和自主的工作",
            "善于处理复杂概念"
        ],
        "workplace_relationships": [
            "是独立的思想者",
            "尊重知识和能力",
            "可能显得冷漠或脱离"
        ],
        "development_areas": [
            "需要发展实践能力",
            "需要关注细节和现实",
            "需要表达情感和感受"
        ],
        "stress_response": "在压力下可能过度分析或拖延，需要注重行动"
    },
    "ESTP": {
        "name": "企业家型",
        "summary": "务实、冒险、充满活力，是行动者和谈判高手",
        "core_strengths": [
            "务实，脚踏实地",
            "善于解决问题和排除故障",
            "充满活力，享受冒险",
            "适应力强，善于即兴发挥",
            "社交能力强，善于谈判"
        ],
        "career_tendencies": [
            "适合需要行动和冒险的工作",
            "偏好快节奏和高挑战的环境",
            "善于销售和谈判"
        ],
        "workplace_relationships": [
            "是魅力四射的同事",
            "喜欢社交和团队活动",
            "善于读懂他人和即时反应"
        ],
        "development_areas": [
            "需要培养耐心和专注",
            "需要考虑长期后果",
            "需要学习计划和准备"
        ],
        "stress_response": "在压力下可能冲动或冒险，需要冷静思考"
    },
    "ESFP": {
        "name": "表演者型",
        "summary": "热情、外向、富有表现力，是社交的明星和娱乐者",
        "core_strengths": [
            "热情开朗，善于社交",
            "富有表现力和感染力",
            "适应力强，善于应变",
            "注重当下，享受生活",
            "真诚友善，容易相处"
        ],
        "career_tendencies": [
            "适合需要社交和表现能力的工作",
            "偏好有趣和灵活的工作",
            "善于销售和客户服务"
        ],
        "workplace_relationships": [
            "是团队的活力源泉",
            "善于调动气氛",
            "不喜欢冲突和批评"
        ],
        "development_areas": [
            "需要培养专注和计划能力",
            "需要接受建设性批评",
            "需要考虑长期目标"
        ],
        "stress_response": "在压力下可能逃避或过度消费，需要学会面对问题"
    },
    "ENFP": {
        "name": "竞选者型",
        "summary": "热情、创意、有感染力，是灵感的激发者和梦想家",
        "core_strengths": [
            "热情洋溢，富有感染力",
            "创造力和想象力丰富",
            "洞察力强，善于理解他人",
            "适应力强，善于应变",
            "善于激励和鼓舞他人"
        ],
        "career_tendencies": [
            "适合需要创造力和人际的工作",
            "偏好自由和多样化的环境",
            "善于营销和推广"
        ],
        "workplace_relationships": [
            "是灵感的激发者",
            "善于建立联系和协作",
            "追求意义和可能性"
        ],
        "development_areas": [
            "需要培养专注和持续力",
            "需要学会说\"不\"",
            "需要处理细节和执行"
        ],
        "stress_response": "在压力下可能过度理想化或分心，需要保持脚踏实地"
    },
    "ENTP": {
        "name": "辩论家型",
        "summary": "聪明、好奇、善于辩论，是创新的思想家和发明家",
        "core_strengths": [
            "聪明机智，反应敏捷",
            "善于辩论和逻辑思考",
            "创造力和想象力丰富",
            "适应力强，善于应变",
            "善于发现机会和创新点"
        ],
        "career_tendencies": [
            "适合需要创新和战略的工作",
            "偏好自主和有挑战性的环境",
            "善于创业和项目管理"
        ],
        "workplace_relationships": [
            "是有趣的辩论伙伴",
            "喜欢智识挑战",
            "可能显得好辩或争议"
        ],
        "development_areas": [
            "需要培养执行力和耐心",
            "需要关注他人感受",
            "需要学会坚持到底"
        ],
        "stress_response": "在压力下可能过度分析或好辩，需要关注行动"
    },
    "ESTJ": {
        "name": "总经理型",
        "summary": "务实、有决断、有组织能力，是天生的管理者",
        "core_strengths": [
            "有决断力和执行力",
            "善于组织和管理",
            "务实可靠，尊重传统",
            "有责任感和正直",
            "善于规划和执行"
        ],
        "career_tendencies": [
            "适合需要管理能力的工作",
            "偏好有结构和秩序的环境",
            "善于执行政策和程序"
        ],
        "workplace_relationships": [
            "是可靠的领导者和同事",
            "尊重规则和层级",
            "直接明了"
        ],
        "development_areas": [
            "需要发展灵活性和同理心",
            "需要接受新的想法",
            "需要关注他人的感受"
        ],
        "stress_response": "在压力下可能变得固执或强硬，需要学会放松"
    },
    "ESFJ": {
        "name": "执政官型",
        "summary": "温暖、热情、有责任感，是受欢迎的照顾者",
        "core_strengths": [
            "温暖友善，善于社交",
            "有责任感，重视承诺",
            "善于照顾他人和提供服务",
            "善于协调和调解",
            "受欢迎，有影响力"
        ],
        "career_tendencies": [
            "适合需要人际和服务的工作",
            "偏好和谐和支持性的环境",
            "善于销售和客户服务"
        ],
        "workplace_relationships": [
            "是团队凝聚力的核心",
            "善于记住重要细节",
            "不喜欢冲突"
        ],
        "development_areas": [
            "需要学会说\"不\"",
            "需要接受建设性批评",
            "需要发展决断力"
        ],
        "stress_response": "在压力下可能过度照顾他人而忽视自己，需要学会自我关怀"
    },
    "ENFJ": {
        "name": "主人公型",
        "summary": "有魅力、有领导力、有理想，是激励者和领袖",
        "core_strengths": [
            "有魅力和影响力",
            "善于激励和鼓舞他人",
            "有理想和愿景",
            "富有同理心和理解力",
            "有领导力和组织能力"
        ],
        "career_tendencies": [
            "适合需要领导力和人际的工作",
            "偏好有意义和有目的的工作",
            "善于培训和发展他人"
        ],
        "workplace_relationships": [
            "是激励人心的领导者",
            "善于建立团队凝聚力",
            "追求和谐和共赢"
        ],
        "development_areas": [
            "需要学会接受不完美",
            "需要设置边界",
            "需要发展韧性"
        ],
        "stress_response": "在压力下可能过度承担责任，需要学会放手"
    },
    "ENTJ": {
        "name": "指挥官型",
        "summary": "有决断、有领导力、有战略眼光，是天生的领袖",
        "core_strengths": [
            "有决断力和执行力",
            "有战略眼光和领导力",
            "自信和有影响力",
            "善于分析和解决问题",
            "追求效率和成果"
        ],
        "career_tendencies": [
            "适合需要领导和管理的工作",
            "偏好有挑战性和目标导向的环境",
            "善于创业和战略规划"
        ],
        "workplace_relationships": [
            "是有力的领导者",
            "尊重能力和效率",
            "直接明了"
        ],
        "development_areas": [
            "需要发展同理心和情感智慧",
            "需要学会接受他人的意见",
            "需要关注他人的感受"
        ],
        "stress_response": "在压力下可能变得霸道或苛刻，需要学会倾听"
    }
}

# ===================== 岗位推荐映射 =====================
MBTI_JOB_RECOMMENDATIONS = {
    "ISTJ": {
        "recommended_jobs": ["审计师", "会计", "财务分析师", "行政经理", "项目经理", "软件工程师", "数据库管理员", "律师"],
        "career_advice": "适合在稳定、有结构的环境中发挥组织能力，建议选择有明确职责和流程的岗位。"
    },
    "ISFJ": {
        "recommended_jobs": ["护士", "教师", "社会工作者", "人力资源专员", "行政助理", "图书馆员", "营养师", "心理咨询师"],
        "career_advice": "适合在支持性、服务性的环境中发挥照顾他人的能力，建议选择能帮助他人的岗位。"
    },
    "INFJ": {
        "recommended_jobs": ["心理咨询师", "作家", "教师", "社会工作者", "艺术家", "人力资源经理", "策划专员", "非营利组织管理者"],
        "career_advice": "适合在有意义、有目的的工作中发挥理想主义，建议选择能实现个人价值观的岗位。"
    },
    "INTJ": {
        "recommended_jobs": ["软件架构师", "科学家", "工程师", "财务顾问", "战略分析师", "教授", "律师", "企业管理者"],
        "career_advice": "适合在需要战略眼光和技术能力的环境中发挥分析能力，建议选择能独立工作的岗位。"
    },
    "ISTP": {
        "recommended_jobs": ["工程师", "技术员", "机械师", "厨师", "飞行员", "警察", "运动员", "数据分析师"],
        "career_advice": "适合在需要技术能力和动手能力的环境中发挥解决问题的能力，建议选择能独立操作的工作。"
    },
    "ISFP": {
        "recommended_jobs": ["艺术家", "设计师", "音乐家", "摄影师", "护士", "时尚设计师", "园丁", "室内设计师"],
        "career_advice": "适合在需要创造力和审美能力的环境中发挥艺术天赋，建议选择能表达自我的工作。"
    },
    "INFP": {
        "recommended_jobs": ["作家", "编辑", "心理咨询师", "教师", "艺术家", "社会工作者", "人力资源专员", "翻译"],
        "career_advice": "适合在有意义、创造性的工作中发挥理想主义，建议选择能实现个人价值观的岗位。"
    },
    "INTP": {
        "recommended_jobs": ["科学家", "研究员", "软件工程师", "数据科学家", "教授", "哲学家", "系统分析师", "法律顾问"],
        "career_advice": "适合在需要智识能力和独立思考的环境中发挥分析能力，建议选择能深入研究的岗位。"
    },
    "ESTP": {
        "recommended_jobs": ["企业家", "销售经理", "营销专员", "房地产经纪人", "急诊医生", "运动员", "厨师", "投资者"],
        "career_advice": "适合在快节奏、高挑战的环境中发挥行动力，建议选择能带来即时反馈的工作。"
    },
    "ESFP": {
        "recommended_jobs": ["演员", "歌手", "设计师", "教师", "销售代表", "活动策划", "公关专员", "空乘人员"],
        "career_advice": "适合在需要表现力和社交能力的环境中发挥魅力，建议选择能展示自我的工作。"
    },
    "ENFP": {
        "recommended_jobs": ["营销经理", "广告创意", "记者", "作家", "教师", "人力资源经理", "培训师", "社会企业家"],
        "career_advice": "适合在需要创造力和人际能力的工作中发挥灵感，建议选择有多样性和自由的工作。"
    },
    "ENTP": {
        "recommended_jobs": ["企业家", "律师", "管理顾问", "营销策略师", "软件开发者", "政治家", "投资人", "发明家"],
        "career_advice": "适合在需要创新和战略的环境中发挥辩论能力，建议选择有挑战性和自主性的工作。"
    },
    "ESTJ": {
        "recommended_jobs": ["总经理", "项目经理", "行政经理", "法官", "军官", "会计师", "销售经理", "保险经理"],
        "career_advice": "适合在需要组织和管理能力的环境中发挥领导力，建议选择有结构和目标的工作。"
    },
    "ESFJ": {
        "recommended_jobs": ["教师", "护士", "人力资源专员", "销售代表", "公关专员", "社会工作者", "美容师", "空乘人员"],
        "career_advice": "适合在需要服务和人际能力的环境中发挥照顾他人的能力，建议选择能帮助他人的工作。"
    },
    "ENFJ": {
        "recommended_jobs": ["教师", "培训师", "人力资源经理", "政治家", "心理咨询师", "社工", "营销经理", "非营利组织管理者"],
        "career_advice": "适合在需要领导力和人际能力的工作中发挥激励他人的能力，建议选择能影响他人的工作。"
    },
    "ENTJ": {
        "recommended_jobs": ["企业家", "CEO", "律师", "管理顾问", "政治家", "投资人", "项目经理", "营销总监"],
        "career_advice": "适合在需要决断力和领导力的环境中发挥指挥能力，建议选择有挑战性和权力的工作。"
    }
}

def calculate_mbti(answers):
    """根据答案计算MBTI类型"""
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

    return mbti, dimensions

def generate_dimension_analysis(dimensions):
    """生成四维度详细分析"""
    analysis = []

    # 能量来源维度
    ei_result = 'E' if dimensions['E'] >= dimensions['I'] else 'I'
    ei_data = MBTI_DIMENSION_ANALYSIS[ei_result]
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
    sn_data = MBTI_DIMENSION_ANALYSIS[sn_result]
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
    tf_data = MBTI_DIMENSION_ANALYSIS[tf_result]
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
    jp_data = MBTI_DIMENSION_ANALYSIS[jp_result]
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
    complete_data = MBTI_COMPLETE_ANALYSIS.get(mbti_type, {})

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
    job_data = MBTI_JOB_RECOMMENDATIONS.get(mbti_type, {})

    return {
        "recommended_jobs": job_data.get("recommended_jobs", []),
        "career_advice": job_data.get("career_advice", "")
    }

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

        # 保存答案
        conn = get_db()
        cur = conn.cursor()
        for answer in answers:
            cur.execute(
                "INSERT INTO personality_test_answers (user_id, question_id, user_choice) VALUES (%s, %s, %s)",
                (user_id, answer['question_id'], answer['user_choice'])
            )

        # 检查表结构是否包含detailed_analysis字段
        cur.execute("SHOW COLUMNS FROM personality_profiles LIKE 'detailed_analysis'")
        has_detailed_analysis = cur.fetchone() is not None
        
        if has_detailed_analysis:
            # 保存人物画像
            cur.execute(
                """INSERT INTO personality_profiles
                (user_id, mbti_type, personality_analysis, recommended_jobs, detailed_analysis)
                VALUES (%s, %s, %s, %s, %s)""",
                (user_id, mbti_type, personality_analysis, ", ".join(job_recommendations["recommended_jobs"]),
                 json.dumps({
                     "dimension_analysis": dimension_analysis,
                     "complete_analysis": complete_analysis,
                     "job_recommendations": job_recommendations
                 }, ensure_ascii=False))
            )
        else:
            # 如果没有detailed_analysis字段，使用旧的SQL语句
            cur.execute(
                """INSERT INTO personality_profiles
                (user_id, mbti_type, personality_analysis, recommended_jobs)
                VALUES (%s, %s, %s, %s)""",
                (user_id, mbti_type, personality_analysis, ", ".join(job_recommendations["recommended_jobs"]))
            )

        conn.commit()
        profile_id = cur.lastrowid
        conn.close()

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

@personality_bp.route('/profile/<int:profile_id>', methods=['GET'])
def get_profile(profile_id):
    """获取性格测试结果"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM personality_profiles WHERE id = %s", (profile_id,))
        result = cur.fetchone()
        conn.close()

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
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, mbti_type, personality_analysis, recommended_jobs, created_at
            FROM personality_profiles
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        results = cur.fetchall()
        conn.close()

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
