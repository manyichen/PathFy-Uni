"""Deterministic report execution strategies derived from preference snapshots.

Personality preferences change *how* a plan is executed.  They never change
capability requirements, gaps, target jobs, or evidence.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping


PREFERENCE_STRATEGY_VERSION = "preference-strategy-v1"
PREFERENCE_REVIEW_SIGNAL_VERSION = "preference-review-signals-v1"

_TEMPLATES = {
    "interaction_intensity": {
        "title": "协作与启动方式",
        "low": ("先独立准备，再进行一对一沟通，最后进入小组协作。", "也可以直接参加小组活动，但提前写下自己的问题和输出。"),
        "high": ("用结对、公开演示或短交流推动任务启动，再留出独立沉淀时间。", "也可以先独立完成最小草稿，再邀请同伴评审。"),
    },
    "abstraction_preference": {
        "title": "学习切入方式",
        "low": ("先从案例、模板和可操作步骤开始，再回看原理与体系。", "也可以先看一页概念地图，再立即用一个真实案例验证。"),
        "high": ("先理解体系、场景和关键假设，再进入工具练习与交付。", "也可以从一个具体案例反推规律，避免前期分析过长。"),
    },
    "analytical_decision": {
        "title": "反馈与决策方式",
        "low": ("先说明用户价值和协作影响，再用量化指标完成验收。", "也可以先按评分表自检，再请利益相关方补充体验反馈。"),
        "high": ("先用清单、评分表和数据自检，再补充他人体验与协作反馈。", "也可以先收集开放反馈，再归纳为可验证的决策标准。"),
    },
    "structure_preference": {
        "title": "时间组织方式",
        "low": ("使用短冲刺、任务池和阶段性交付，为变化保留调整空间。", "也可以设置固定周检查点，只把中间路径保持开放。"),
        "high": ("设置明确里程碑、截止日期和每周检查点，按节奏推进同一交付物。", "也可以保留一个机动时段，用于处理探索和临时变化。"),
    },
}

_SIGNAL_AXIS = {
    "energy_after_tasks": "interaction_intensity",
    "collaboration_fit": "interaction_intensity",
    "structure_fit": "structure_preference",
    "task_mode_fit": "abstraction_preference",
}


def build_preference_strategy(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    base = {
        "status": "missing",
        "version": PREFERENCE_STRATEGY_VERSION,
        "sections": [],
        "calibration": {"status": "insufficient_cycles", "completed_cycles": 0, "required_cycles": 3},
        "influences_capability": False,
        "disclaimer": "这些建议只调整行动形式，不改变岗位能力要求、能力缺口或目标岗位。",
    }
    if not snapshot or snapshot.get("status") != "measured":
        return base
    sections: list[dict[str, Any]] = []
    for axis in snapshot.get("axes") or []:
        if not isinstance(axis, Mapping):
            continue
        code = str(axis.get("code") or "")
        template = _TEMPLATES.get(code)
        if not template:
            continue
        value = max(0.0, min(100.0, float(axis.get("value") or 0.0)))
        strength = max(0.0, min(1.0, float(axis.get("preference_strength") or 0.0)))
        side = "high" if value >= 50 else "low"
        recommendation, alternative = template[side]
        sections.append(
            {
                "code": code,
                "title": template["title"],
                "recommendation": recommendation,
                "alternative": alternative,
                "rationale": f"测评中该维度为 {value:.0f}/100，偏好强度 {strength:.0%}；建议作为起步方式，而不是限制。",
                "source": {"axis_code": code, "value": round(value, 2), "preference_strength": round(strength, 4)},
            }
        )
    return {
        **base,
        "status": "suggested" if sections else "missing",
        "personality_profile_id": snapshot.get("personality_profile_id"),
        "mbti_type": snapshot.get("mbti_type"),
        "sections": sections,
    }


def sanitize_preference_signals(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, Any] = {}
    for code in _SIGNAL_AXIS:
        if code not in raw:
            continue
        try:
            value = int(raw[code])
        except (TypeError, ValueError):
            continue
        if 1 <= value <= 5:
            out[code] = value
    note = str(raw.get("note") or "").strip()
    if note:
        out["note"] = note[:500]
    return out


def behavioral_evidence_rows(signals: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, axis_code in _SIGNAL_AXIS.items():
        if code not in signals:
            continue
        value = int(signals[code])
        rows.append(
            {
                "axis_code": axis_code,
                "observed_value": round((value - 1) * 25.0, 2),
                "source_type": "confirmed_review_signal",
                "source": {"signal_code": code, "rating_1_5": value, "version": PREFERENCE_REVIEW_SIGNAL_VERSION},
            }
        )
    return rows


def update_calibration(strategy: Mapping[str, Any] | None, review_metrics: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a three-cycle prompt without mutating or re-scoring the profile."""
    result = copy.deepcopy(dict(strategy or {}))
    cycles: list[dict[str, Any]] = []
    for payload in review_metrics:
        signals = sanitize_preference_signals(payload.get("preference_signals"))
        if signals:
            cycles.append(signals)
    recent = cycles[-3:]
    calibration: dict[str, Any] = {
        "status": "insufficient_cycles",
        "completed_cycles": len(cycles),
        "required_cycles": 3,
        "candidate_axes": [],
        "message": "连续记录 3 个复盘周期后，系统才会提示可能需要校准的偏好；不会自动修改测评。",
    }
    if len(recent) == 3:
        candidates: list[dict[str, Any]] = []
        for signal_code, axis_code in _SIGNAL_AXIS.items():
            values = [int(item[signal_code]) for item in recent if signal_code in item]
            if len(values) == 3 and (max(values) <= 2 or min(values) >= 4):
                direction = "lower" if max(values) <= 2 else "higher"
                candidates.append({"axis_code": axis_code, "signal_code": signal_code, "direction": direction, "ratings": values})
        calibration.update(
            {
                "status": "review_recommended" if candidates else "stable",
                "candidate_axes": candidates,
                "message": (
                    "连续 3 个周期出现同方向体验，建议核对偏好画像或重新测评；当前画像未被修改。"
                    if candidates
                    else "最近 3 个周期未出现持续同方向偏差，当前执行建议可继续观察。"
                ),
            }
        )
    result["calibration"] = calibration
    return result


def apply_strategy_decision(strategy: Mapping[str, Any], body: Mapping[str, Any]) -> dict[str, Any]:
    decision = str(body.get("decision") or "").strip().lower()
    if decision not in {"accept", "edit", "use_alternative"}:
        raise ValueError("decision must be accept, edit, or use_alternative")
    result = copy.deepcopy(dict(strategy))
    sections = result.get("sections") if isinstance(result.get("sections"), list) else []
    edits = body.get("sections") if isinstance(body.get("sections"), list) else []
    edit_map = {str(item.get("code") or ""): item for item in edits if isinstance(item, Mapping)}
    for section in sections:
        if not isinstance(section, dict):
            continue
        code = str(section.get("code") or "")
        edit = edit_map.get(code)
        if decision == "use_alternative":
            section["recommendation"], section["alternative"] = section.get("alternative"), section.get("recommendation")
        elif decision == "edit" and edit:
            for field in ("recommendation", "alternative"):
                value = str(edit.get(field) or "").strip()
                if value:
                    section[field] = value[:500]
            section["user_edited"] = True
    result["status"] = "accepted" if decision == "accept" else "edited"
    result["last_decision"] = decision
    return result
