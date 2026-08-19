"""Deterministic Career Report V2 decision and evidence model.

The adapter deliberately derives claims and actions from persisted report
facts. It keeps legacy reports readable and gives the frontend a stable,
grounded contract before any LLM copywriting is applied.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from app.domains.report.constants import DIM_LABELS

_DIM_KEYS = tuple(DIM_LABELS.keys())
_ACTION_KIND = {
    "learning": "learn",
    "learn": "learn",
    "practice": "practice",
    "project": "deliverable",
    "evidence": "deliverable",
    "deliverable": "deliverable",
}
_EFFORT_HOURS = {"learn": 4.0, "practice": 6.0, "deliverable": 3.0}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _target_id(target: Dict[str, Any]) -> str:
    return str(target.get("id") or target.get("job_id") or "").strip()


def _role(index: int, job_id: str, primary_job_id: str) -> str:
    if job_id == primary_job_id:
        return "primary"
    return "alternative" if index < 3 else "observe"


def _role_label(role: str) -> str:
    return {"primary": "主目标", "alternative": "备选目标", "observe": "观察目标"}.get(role, "目标")


def _plan_for_job(report_obj: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    return next(
        (
            plan
            for plan in report_obj.get("plans_by_target") or []
            if isinstance(plan, dict) and str(plan.get("job_id") or "").strip() == job_id
        ),
        {},
    )


def _confidence(report_obj: Dict[str, Any], target: Dict[str, Any], dimension: str) -> float:
    student_conf = (report_obj.get("student") or {}).get("confidences") or {}
    job_conf = target.get("confidences") or {}
    conf_key = dimension.replace("cap_req_", "cap_conf_")
    values = [
        _number(student_conf.get(conf_key), -1.0),
        _number(job_conf.get(conf_key), -1.0),
    ]
    valid = [value for value in values if value >= 0]
    return round(sum(valid) / len(valid), 3) if valid else 0.6


def _fact(
    *,
    fact_id: str,
    label: str,
    value: float,
    unit: str,
    observed_at: str,
    source_type: str = "system_calculated",
    evidence_grade: str = "B",
) -> Dict[str, Any]:
    return {
        "id": fact_id,
        "label": label,
        "value": round(value, 2),
        "unit": unit,
        "source_type": source_type,
        "source_label": "系统计算" if source_type == "system_calculated" else "用户确认",
        "evidence_grade": evidence_grade,
        "observed_at": observed_at,
        "verified": evidence_grade in ("A", "B"),
    }


def _claims_for_target(
    report_obj: Dict[str, Any],
    target: Dict[str, Any],
    *,
    job_id: str,
    observed_at: str,
    focus_dimensions: List[str] | None = None,
) -> List[Dict[str, Any]]:
    preview = target.get("match_preview") or {}
    student_scores = preview.get("student_scores") or (report_obj.get("student") or {}).get("scores") or {}
    requirements = preview.get("job_requirement_scores") or target.get("scores") or {}
    gaps = preview.get("dimension_gaps") or {}
    raw_delta = preview.get("dimension_raw_delta") if isinstance(preview.get("dimension_raw_delta"), dict) else {
        dimension: round(_number(requirements.get(dimension)) - _number(student_scores.get(dimension)), 2)
        for dimension in _DIM_KEYS
        if dimension in student_scores and dimension in requirements
    }
    gap_rows = sorted(
        (
            (dimension, _number(gap))
            for dimension, gap in gaps.items()
            if dimension in _DIM_KEYS and _number(gap) > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    claims: List[Dict[str, Any]] = []
    for index, (dimension, gap) in enumerate(gap_rows[:3]):
        label = DIM_LABELS.get(dimension, dimension)
        student = _number(student_scores.get(dimension))
        requirement = _number(requirements.get(dimension))
        confidence = _confidence(report_obj, target, dimension)
        job_importance = max(0.35, min(1.0, requirement / 100.0))
        priority = gap * job_importance * confidence * 0.8 * (1.0 if index == 0 else 0.85)
        claims.append(
            {
                "id": f"claim:{job_id}:gap:{dimension}",
                "kind": "gap",
                "dimension": dimension,
                "title": f"{label}是当前{'首要' if index == 0 else '关键'}补齐项",
                "summary": f"当前 {student:.0f} 分，对照岗位要求 {requirement:.0f} 分，有效差距 {gap:.0f} 分。",
                "impact": f"该差距会影响面向此岗位时的{label}任务交付与成果说服力。",
                "fact_refs": [
                    f"profile:{dimension}",
                    f"job:{job_id}:{dimension}",
                    f"gap:{job_id}:{dimension}",
                ],
                "facts": [
                    _fact(fact_id=f"profile:{dimension}", label="当前能力", value=student, unit="分", observed_at=observed_at),
                    _fact(fact_id=f"job:{job_id}:{dimension}", label="岗位要求", value=requirement, unit="分", observed_at=observed_at),
                    _fact(fact_id=f"gap:{job_id}:{dimension}", label="有效差距", value=gap, unit="分", observed_at=observed_at),
                ],
                "priority": round(priority, 2),
                "priority_factors": {
                    "gap_size": round(gap, 2),
                    "job_importance": round(job_importance, 3),
                    "confidence": confidence,
                    "improvability": 0.8,
                    "urgency": 1.0 if index == 0 else 0.85,
                },
                "quality": {
                    "grounded": True,
                    "evidence_grade": "B",
                    "source_type": "system_calculated",
                    "freshness": observed_at,
                },
            }
        )

    hard_gap_dimensions = {dimension for dimension, _ in gap_rows}
    tolerance_rows = sorted(
        (
            (dimension, _number(delta))
            for dimension, delta in raw_delta.items()
            if dimension in _DIM_KEYS and _number(delta) > 0 and dimension not in hard_gap_dimensions
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    for dimension, delta in tolerance_rows[:2]:
        label = DIM_LABELS.get(dimension, dimension)
        student = _number(student_scores.get(dimension))
        requirement = _number(requirements.get(dimension))
        confidence = _confidence(report_obj, target, dimension)
        claims.append(
            {
                "id": f"claim:{job_id}:risk:{dimension}",
                "kind": "risk",
                "dimension": dimension,
                "title": f"{label}低于岗位标尺，仍需成果验证",
                "summary": f"当前 {student:.0f} 分，岗位要求 {requirement:.0f} 分，原始差值 {delta:.0f} 分；因处于匹配软容差内，未计为硬缺口。",
                "impact": f"匹配分暂未扣除这部分差值，但仍应通过{label}相关作品、测试或反馈验证真实胜任度。",
                "fact_refs": [
                    f"profile:{dimension}", f"job:{job_id}:{dimension}", f"raw-gap:{job_id}:{dimension}",
                ],
                "facts": [
                    _fact(fact_id=f"profile:{dimension}", label="当前能力", value=student, unit="分", observed_at=observed_at),
                    _fact(fact_id=f"job:{job_id}:{dimension}", label="岗位要求", value=requirement, unit="分", observed_at=observed_at),
                    _fact(fact_id=f"raw-gap:{job_id}:{dimension}", label="容差内差值", value=delta, unit="分", observed_at=observed_at),
                ],
                "priority": round(delta * max(0.35, requirement / 100.0) * confidence, 2),
                "priority_factors": {
                    "raw_gap_size": round(delta, 2), "confidence": confidence,
                    "within_soft_margin": 1.0,
                },
                "quality": {
                    "grounded": True, "evidence_grade": "B", "source_type": "system_calculated", "freshness": observed_at,
                },
            }
        )

    relative = sorted(
        (
            (dimension, _number(student_scores.get(dimension)) - _number(requirements.get(dimension)))
            for dimension in _DIM_KEYS
            if dimension in student_scores and dimension in requirements
            and _number(student_scores.get(dimension)) >= _number(requirements.get(dimension))
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    preferred_strengths = [dimension for dimension in focus_dimensions or [] if any(row[0] == dimension for row in relative)]
    selected_strengths: List[tuple[str, float]] = []
    for row in relative:
        if len(selected_strengths) >= 2 and row[0] not in preferred_strengths:
            continue
        if row[0] not in {item[0] for item in selected_strengths}:
            selected_strengths.append(row)
        if len(selected_strengths) >= 4 or (len(selected_strengths) >= 2 and all(value in {item[0] for item in selected_strengths} for value in preferred_strengths)):
            break
    for dimension, margin in selected_strengths:
        label = DIM_LABELS.get(dimension, dimension)
        student = _number(student_scores.get(dimension))
        requirement = _number(requirements.get(dimension))
        claims.append(
            {
                "id": f"claim:{job_id}:strength:{dimension}",
                "kind": "strength",
                "dimension": dimension,
                "title": f"{label}是当前相对优势",
                "summary": f"当前 {student:.0f} 分，岗位要求 {requirement:.0f} 分，相对差值 {margin:+.0f} 分。",
                "impact": f"可优先把{label}转化为项目说明、作品或面试案例。",
                "fact_refs": [f"profile:{dimension}", f"job:{job_id}:{dimension}"],
                "facts": [
                    _fact(fact_id=f"profile:{dimension}", label="当前能力", value=student, unit="分", observed_at=observed_at),
                    _fact(fact_id=f"job:{job_id}:{dimension}", label="岗位要求", value=requirement, unit="分", observed_at=observed_at),
                ],
                "priority": round(max(0.0, margin), 2),
                "quality": {
                    "grounded": True,
                    "evidence_grade": "B",
                    "source_type": "system_calculated",
                    "freshness": observed_at,
                },
            }
        )
    return claims


def _actions_for_target(plan: Dict[str, Any], job_id: str) -> List[Dict[str, Any]]:
    next_plan = plan.get("next_month_plan") if isinstance(plan.get("next_month_plan"), dict) else {}
    items = next_plan.get("items") if isinstance(next_plan.get("items"), list) else []
    if not items:
        early = ((plan.get("phases") or {}).get("early") or {})
        items = early.get("items") if isinstance(early.get("items"), list) else []
    plan_month = int(next_plan.get("plan_month") or plan.get("current_plan_month") or 1)
    actions: List[Dict[str, Any]] = []
    for item_index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        custom = [action for action in item.get("custom_actions") or [] if isinstance(action, dict)]
        deliverable_action = next(
            (action for action in custom if _ACTION_KIND.get(str(action.get("kind") or ""), "practice") == "deliverable"),
            None,
        )
        deliverable = str(
            (deliverable_action or {}).get("text")
            or item.get("milestone")
            or f"形成一项{item.get('focus_label') or '岗位能力'}成果"
        ).strip()
        for action_index, action in enumerate(custom):
            if len(actions) >= 12:
                break
            text = str(action.get("text") or "").strip()
            if not text:
                continue
            kind = _ACTION_KIND.get(str(action.get("kind") or "").strip().lower(), "practice")
            action_id = str(action.get("action_uid") or f"action:{job_id}:{plan_month}:{item_index}:{action_index}")
            action_deliverable = str(action.get("deliverable") or deliverable).strip()
            acceptance_rule = str(action.get("acceptance_rule") or "").strip()
            acceptance_criteria = [
                f"完成行动：{text}",
                f"提交可查看的产物：{action_deliverable}",
                "在报告中勾选完成，并在月度复盘记录结果或链接",
            ]
            if acceptance_rule:
                acceptance_criteria[2] = acceptance_rule
            decision_action = {
                    "id": action_id,
                    "job_id": job_id,
                    "item_index": item_index,
                    "action_index": action_index,
                    "title": text,
                    "kind": kind,
                    "focus_dimension": item.get("focus_dimension"),
                    "focus_label": item.get("focus_label"),
                    "deliverable": action_deliverable,
                    "deadline": str(action.get("deadline") or f"第 {min(4, len(actions) + 1)} 周末"),
                    "effort_hours": max(0.5, min(20.0, _number(action.get("effort_hours"), _EFFORT_HOURS[kind]))),
                    "acceptance_criteria": acceptance_criteria,
                    "evidence_required": True,
                    "evidence_grade_required": "B",
                    "evidence_type": str(action.get("evidence_type") or "other"),
                    "status": "done" if action.get("done") else "todo",
                    "done": bool(action.get("done")),
                    "source_claim_ids": [f"claim:{job_id}:gap:{item.get('focus_dimension')}"] if item.get("focus_dimension") else [],
                    "source_fact_refs": [str(value) for value in action.get("fact_refs") or [] if str(value)],
                    "resource_refs": [str(value) for value in action.get("resource_refs") or [] if str(value)],
                }
            if action.get("done_at"):
                decision_action["done_at"] = str(action["done_at"])
            actions.append(decision_action)
    return actions


def build_decision_support(
    report_obj: Dict[str, Any],
    *,
    primary_job_id: str,
    evidence_records: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    observed_at = str(report_obj.get("generated_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    targets = [target for target in report_obj.get("targets") or [] if isinstance(target, dict)]
    target_decisions: List[Dict[str, Any]] = []
    top_dimension_counts: Counter[str] = Counter()

    for index, target in enumerate(targets):
        job_id = _target_id(target)
        if not job_id:
            continue
        role = _role(index, job_id, primary_job_id)
        plan = _plan_for_job(report_obj, job_id)
        focus_dimensions = [
            str(item.get("focus_dimension") or "")
            for item in ((plan.get("next_month_plan") or {}).get("items") or [])
            if isinstance(item, dict) and item.get("focus_dimension")
        ]
        claims = _claims_for_target(
            report_obj, target, job_id=job_id, observed_at=observed_at, focus_dimensions=focus_dimensions
        )
        gap_claims = [claim for claim in claims if claim.get("kind") == "gap"]
        risk_claims = [claim for claim in claims if claim.get("kind") == "risk"]
        strength_claims = [claim for claim in claims if claim.get("kind") == "strength"]
        for claim in (gap_claims + risk_claims)[:2]:
            if claim.get("dimension"):
                top_dimension_counts[str(claim["dimension"])] += 1
        match_score = _number((target.get("match_preview") or {}).get("match_score") or plan.get("match_score"))
        actions = _actions_for_target(plan, job_id)
        claim_ids = {str(claim.get("id") or "") for claim in claims}
        fact_ids = {
            str(fact.get("id") or "")
            for claim in claims
            for fact in claim.get("facts") or []
            if isinstance(fact, dict)
        }
        claims_by_dimension: Dict[str, List[Dict[str, Any]]] = {}
        for claim in claims:
            dimension = str(claim.get("dimension") or "")
            if dimension:
                claims_by_dimension.setdefault(dimension, []).append(claim)
        for action in actions:
            action["source_claim_ids"] = [
                claim_id
                for claim_id in action.get("source_claim_ids") or []
                if claim_id in claim_ids
            ]
            if not action["source_claim_ids"]:
                candidates = claims_by_dimension.get(str(action.get("focus_dimension") or ""), [])
                candidates.sort(key=lambda item: {"gap": 0, "risk": 1, "strength": 2}.get(str(item.get("kind")), 9))
                if candidates:
                    action["source_claim_ids"] = [str(candidates[0]["id"])]
            action["source_fact_refs"] = [
                fact_id
                for fact_id in action.get("source_fact_refs") or []
                if fact_id in fact_ids
            ]
            if not action["source_fact_refs"] and action["source_claim_ids"]:
                linked_claim = next((claim for claim in claims if claim.get("id") == action["source_claim_ids"][0]), None)
                if linked_claim:
                    action["source_fact_refs"] = list(linked_claim.get("fact_refs") or [])
        data_gaps: List[str] = []
        if not (target.get("match_preview") or {}).get("job_requirement_scores"):
            data_gaps.append("岗位能力要求缺少完整评分快照")
        if not (report_obj.get("student") or {}).get("confidences"):
            data_gaps.append("画像置信度信息不足")
        grounded_claims = sum(1 for claim in claims if (claim.get("quality") or {}).get("grounded"))
        all_facts = [fact for claim in claims for fact in claim.get("facts") or [] if isinstance(fact, dict)]
        verified_facts = sum(1 for fact in all_facts if fact.get("verified"))
        traceable_actions = sum(
            1 for action in actions if action.get("source_claim_ids") and action.get("source_fact_refs")
        )
        claim_grounding = grounded_claims / max(1, len(claims))
        fact_verification = verified_facts / max(1, len(all_facts))
        action_traceability = traceable_actions / max(1, len(actions))
        input_completeness = 1.0 if not data_gaps else max(0.0, 1.0 - len(data_gaps) * 0.35)
        evidence_coverage = round(
            claim_grounding * 0.35 + action_traceability * 0.35 + fact_verification * 0.2 + input_completeness * 0.1,
            3,
        )
        target_evidence = []
        for record in evidence_records or []:
            if not isinstance(record, dict):
                continue
            record_job_id = str(record.get("job_id") or "").strip()
            record_scope = str(record.get("scope") or "target").strip()
            if record_job_id != job_id and record_scope != "all" and not (not record_job_id and role == "primary"):
                continue
            target_evidence.append(
                {
                    "id": str(record.get("id") or ""),
                    "review_id": record.get("review_id"),
                    "evidence_type": str(record.get("evidence_type") or "other"),
                    "label": str(record.get("label") or "复盘成果"),
                    "value": str(record.get("value_text") or ""),
                    "source_url": str(record.get("source_url") or ""),
                    "source_text": str(record.get("source_text") or ""),
                    "verification_status": str(record.get("verification_status") or "user_confirmed"),
                    "created_at": str(record.get("created_at") or ""),
                }
            )
        target_decisions.append(
            {
                "job_id": job_id,
                "display_title": target.get("display_title") or target.get("title") or job_id,
                "company": target.get("company") or "",
                "role": role,
                "role_label": _role_label(role),
                "judgement": {
                    "recommendation": {"primary": "优先推进", "alternative": "保留备选", "observe": "低成本观察"}[role],
                    "match_score": round(match_score, 2),
                    "reasons": [claim.get("title") for claim in strength_claims[:2]],
                    "risks": [claim.get("title") for claim in (gap_claims + risk_claims)[:2]],
                    "data_gaps": data_gaps,
                },
                "claims": claims,
                "actions": actions,
                "outcome_evidence": target_evidence,
                "primary_action_id": actions[0].get("id") if actions else None,
                "evidence_metrics": {
                    "coverage": evidence_coverage,
                    "claim_grounding": round(claim_grounding, 3),
                    "action_traceability": round(action_traceability, 3),
                    "fact_verification": round(fact_verification, 3),
                    "claim_count": len(claims),
                    "fact_count": len(all_facts),
                    "action_count": len(actions),
                    "unlinked_action_count": max(0, len(actions) - traceable_actions),
                    "outcome_evidence_count": len(target_evidence),
                },
                "freshness": {
                    "profile": {"as_of": observed_at, "source_label": "画像快照", "evidence_grade": "B"},
                    "job": {"as_of": observed_at, "source_label": "岗位库快照", "evidence_grade": "B"},
                    "plan": {"as_of": str((plan.get("next_month_plan") or {}).get("updated_at") or observed_at), "source_label": "规则规划", "evidence_grade": "B"},
                },
            }
        )

    comparison = [
        {
            "job_id": decision["job_id"],
            "display_title": decision["display_title"],
            "role": decision["role"],
            "role_label": decision["role_label"],
            "match_score": decision["judgement"]["match_score"],
            "top_gap": next(
                (claim.get("title") for claim in decision["claims"] if claim.get("kind") in ("gap", "risk")),
                "暂无测得硬缺口",
            ),
            "primary_action": decision["actions"][0].get("title") if decision["actions"] else "待生成",
            "evidence_coverage": decision["evidence_metrics"]["coverage"],
        }
        for decision in target_decisions
    ]
    shared_actions = [
        {
            "dimension": dimension,
            "label": DIM_LABELS.get(dimension, dimension),
            "target_count": count,
            "reason": f"同时出现在 {count} 个目标的关键差距中，优先投入可复用。",
        }
        for dimension, count in top_dimension_counts.most_common()
        if count >= 2
    ][:3]
    return {
        "schema_version": 2,
        "generated_at": observed_at,
        "updated_at": str(
            ((report_obj.get("evaluation") or {}).get("latest_review") or {}).get("created_at")
            or (report_obj.get("enrichment") or {}).get("completed_at")
            or observed_at
        ),
        "fact_model": "fact-claim-impact-action-deliverable-metric",
        "target_decisions": target_decisions,
        "target_comparison": comparison,
        "shared_actions": shared_actions,
        "evidence_legend": [
            {"grade": "A", "label": "已验证成果", "objective": True},
            {"grade": "B", "label": "系统记录", "objective": True},
            {"grade": "C", "label": "用户确认", "objective": False},
            {"grade": "D", "label": "AI 待确认", "objective": False},
        ],
    }


def attach_decision_support(
    report_obj: Dict[str, Any],
    *,
    primary_job_id: str,
    evidence_records: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    report_obj["decision_support"] = build_decision_support(
        report_obj,
        primary_job_id=primary_job_id,
        evidence_records=evidence_records,
    )
    return report_obj["decision_support"]
