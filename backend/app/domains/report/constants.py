"""生涯报告常量。"""
from __future__ import annotations

from typing import Dict, List

# 进步曲线（0–100）：沿横轴每经过 1 个月，相对上一节点进步度最多上涨多少
TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH = 15.0

DIM_LABELS: Dict[str, str] = {
    "cap_req_theory": "专业理论知识",
    "cap_req_cross": "交叉学科广度",
    "cap_req_practice": "专业实践技能",
    "cap_req_digital": "数字素养技能",
    "cap_req_innovation": "创新创业能力",
    "cap_req_teamwork": "团队协作能力",
    "cap_req_social": "社会实践网络",
    "cap_req_growth": "学习与发展潜力",
}

SHORT_TERM_ACTIONS: Dict[str, List[str]] = {
    "cap_req_theory": ["完成 1 门岗位核心课程并输出笔记", "每周整理 1 份知识图谱并复盘"],
    "cap_req_cross": ["选修 1 门跨学科课程", "每月完成 1 次跨领域案例拆解"],
    "cap_req_practice": ["完成 1 个可展示的实战小项目", "参与 1 次真实需求协作（校内/开源）"],
    "cap_req_digital": ["掌握目标岗位常用数字工具链", "完成 2 份数据分析或自动化练习"],
    "cap_req_innovation": ["每两周输出 1 个问题-方案提案", "参与 1 次创新/挑战赛"],
    "cap_req_teamwork": ["在团队项目中承担明确角色并记录产出", "每周进行一次协作复盘"],
    "cap_req_social": ["每月参加 1 次行业交流活动", "建立并维护 10 位职业联系人清单"],
    "cap_req_growth": ["建立双周学习节奏并固化复盘模板", "每月更新一次成长仪表板"],
}

MID_TERM_ACTIONS: Dict[str, List[str]] = {
    "cap_req_theory": ["完成岗位进阶知识体系并形成专题文章", "准备并通过 1 项专业认证"],
    "cap_req_cross": ["完成 1 个跨学科综合项目", "将主专业能力迁移到新场景并沉淀方法"],
    "cap_req_practice": ["完成 1 段岗位相关实习/长期项目", "建立可面试展示的项目作品集"],
    "cap_req_digital": ["完成 1 个数据/自动化中型项目", "形成可复用工具脚本与文档"],
    "cap_req_innovation": ["主导 1 个从方案到落地的创新实践", "形成个人创新案例库"],
    "cap_req_teamwork": ["承担小团队协调职责", "将协作流程标准化并沉淀模板"],
    "cap_req_social": ["建立稳定行业导师/前辈反馈机制", "完成 3 次目标岗位深度访谈"],
    "cap_req_growth": ["形成年度成长路线图并季度修订", "将学习成果固化为公开作品或分享"],
}
