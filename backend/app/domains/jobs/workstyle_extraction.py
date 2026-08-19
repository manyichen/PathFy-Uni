"""Conservative text-evidence extraction for job work-environment axes."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from app.domains.jobs.workstyle import WORKSTYLE_SCORING_VERSION

WORKSTYLE_TEXT_VERSION = "workstyle-text-rules-v1"

_SIGNALS = {
    "interaction_intensity": {
        "field": "interaction",
        "high": ("客户沟通", "跨部门", "跨团队", "公开汇报", "演讲", "用户访谈", "团队协作"),
        "low": ("独立完成", "独立负责", "独立研究", "独立开发", "深度工作", "独立分析"),
    },
    "abstraction_preference": {
        "field": "abstraction",
        "high": ("战略", "研究", "探索", "创新", "方案设计", "架构设计", "开放问题"),
        "low": ("标准流程", "具体操作", "数据录入", "日常维护", "作业指导", "SOP"),
    },
    "analytical_decision": {
        "field": "analytical",
        "high": ("数据分析", "指标体系", "逻辑分析", "风险控制", "合规", "量化", "规则"),
        "low": ("用户体验", "关系维护", "同理心", "服务意识", "人际协调", "员工关怀"),
    },
    "structure_preference": {
        "field": "structure",
        "high": ("固定流程", "项目计划", "里程碑", "合规要求", "规范", "项目管理", "质量标准"),
        "low": ("快速变化", "灵活调整", "敏捷", "多任务", "不确定性", "0到1", "从0到1"),
    },
}


def workstyle_input_fingerprint(payload: Mapping[str, Any]) -> str:
    text = "\n".join(str(payload.get(key) or "").strip() for key in ("demand", "company_detail", "experience"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence_snippet(text: str, keyword: str) -> str:
    position = text.find(keyword)
    if position < 0:
        return keyword
    start = max(0, position - 35)
    end = min(len(text), position + len(keyword) + 55)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def extract_workstyle_profile(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only axes supported by explicit recruitment-text signals."""
    text = "\n".join(str(payload.get(key) or "") for key in ("demand", "company_detail", "experience"))
    evidence: dict[str, list[dict[str, str]]] = {}
    properties: dict[str, Any] = {
        "workstyle_source": "job_text_rules",
        "workstyle_scoring_version": WORKSTYLE_TEXT_VERSION,
        "workstyle_input_fingerprint": workstyle_input_fingerprint(payload),
    }
    for code, config in _SIGNALS.items():
        high_hits = [word for word in config["high"] if word.lower() in text.lower()]
        low_hits = [word for word in config["low"] if word.lower() in text.lower()]
        total = len(high_hits) + len(low_hits)
        if not total:
            continue
        balance = (len(high_hits) - len(low_hits)) / total
        value = round(50 + 35 * balance, 2)
        confidence = round(min(0.85, 0.45 + 0.08 * total), 4)
        field = str(config["field"])
        properties[f"workstyle_{field}"] = value
        properties[f"workstyle_conf_{field}"] = confidence
        items = []
        for keyword in (high_hits + low_hits)[:8]:
            items.append({"text": _evidence_snippet(text, keyword), "source": "job_description", "signal": keyword})
        evidence[code] = items
    properties["workstyle_evidence_json"] = json.dumps(evidence, ensure_ascii=False)
    properties["workstyle_extractor_base_version"] = WORKSTYLE_SCORING_VERSION
    return properties
