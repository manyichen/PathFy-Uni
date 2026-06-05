"""生涯报告常量。"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# 进步曲线（0–100）：沿横轴每经过 1 个月，相对上一节点进步度最多上涨多少（12 个月分期 ≈ 100/12）
TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH = 10.0

# 月度评估指标 code → 面向用户的中文名（禁止在 UI 展示英文 code）
METRIC_LABELS: Dict[str, str] = {
    "dim_gap_reduction": "能力短板缩小",
    "project_completion": "计划完成",
    "match_score_change": "岗位贴合度",
    "delivery_output": "可展示成果",
}

# 复盘未达标时 growth_rationale 用的短标签
METRIC_FAIL_HINTS: Dict[str, str] = {
    "dim_gap_reduction": "能力短板缩小",
    "project_completion": "计划执行",
    "match_score_change": "岗位贴合度",
    "delivery_output": "成果产出",
}

# 评估指标在 UI 里偶现的长问句（LLM/旧数据），清洗时替换或删除
_METRIC_QUESTION_PHRASES: Dict[str, str] = {
    "能力短板补上了多少": "能力短板缩小",
    "本期计划做完了多少": "计划完成",
    "和目标岗位的贴合度变化": "岗位贴合度",
    "可拿出来展示的成果有多少": "可展示成果",
}

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


def metric_label(code: str) -> str:
    c = str(code or "").strip()
    if not c:
        return ""
    return METRIC_LABELS.get(c) or DIM_LABELS.get(c) or ""


def sanitize_user_facing_text(text: str) -> str:
    """将指标 code、开发术语替换/剔除，供里程碑、行动、说明等展示。"""
    raw = str(text or "").strip()
    if not raw:
        return raw
    out = raw
    tokens = {**METRIC_LABELS, **DIM_LABELS}
    for code, label in sorted(tokens.items(), key=lambda x: -len(x[0])):
        if not label or code not in out:
            continue
        out = re.sub(rf"`{re.escape(code)}`", label, out, flags=re.IGNORECASE)
        out = re.sub(rf"\b{re.escape(code)}\b", label, out, flags=re.IGNORECASE)
    for phrase, replacement in _METRIC_QUESTION_PHRASES.items():
        out = out.replace(phrase, replacement)
    # 去掉「拉动完成率/贴合度」等开发向表述
    out = re.sub(r"当前匹配约\s*\d+(?:\.\d+)?\s*分[,，]?\s*", "", out)
    out = re.sub(r"[,，]\s*拉动[^。；！？\n]+", "", out)
    out = re.sub(r"以拉动[^。；！？\n]+", "", out)
    out = re.sub(r"拉动(?:完成率|贴合度|成果|短板)[^。；！？\n]*", "", out)
    out = out.replace("四项评估指标", "月度目标")
    out = out.replace("短板收敛", "能力短板缩小")
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"[,，]{2,}", "，", out)
    out = re.sub(r"^[，,；;·\s]+", "", out)
    return out.strip()


def sanitize_plan_item_user_text(item: Dict[str, Any]) -> None:
    """原地清理计划条目中用户可见字段。"""
    if not isinstance(item, dict):
        return
    ms = item.get("milestone")
    if isinstance(ms, str) and ms.strip():
        item["milestone"] = sanitize_user_facing_text(ms)[:200]
    gr = item.get("growth_rationale")
    if isinstance(gr, str) and gr.strip():
        item["growth_rationale"] = sanitize_user_facing_text(gr)[:420]
    actions = item.get("custom_actions")
    if isinstance(actions, list):
        for act in actions:
            if isinstance(act, dict) and act.get("text"):
                act["text"] = sanitize_user_facing_text(str(act.get("text")))[:150]
    codes = item.get("metric_targets")
    if isinstance(codes, list) and codes:
        item["metric_target_labels"] = [
            metric_label(str(c)) or str(c) for c in codes if str(c).strip()
        ]
