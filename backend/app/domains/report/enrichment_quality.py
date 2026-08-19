"""Career report enrichment snapshots and deterministic quality gates.

The LLM never becomes the source of truth.  This module freezes the evidence
available when a report is created, validates that snapshot before enrichment,
and decides whether AI-owned copy may be merged, repaired, or discarded.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from app.domains.report.constants import DIM_LABELS

_PHASE_KEYS = ("early", "mid", "late")
_ACTION_KINDS = {"learn", "practice", "deliverable"}
_VAGUE_ONLY = (
    "持续提升",
    "全面加强",
    "积极参与",
    "不断提高",
    "进一步提升",
    "增强综合能力",
)
_CONCRETE_MARKERS = (
    "完成",
    "提交",
    "输出",
    "产出",
    "作品",
    "报告",
    "截图",
    "链接",
    "记录",
    "复盘",
    "项目",
    "证书",
    "笔记",
    "README",
)
_FORBIDDEN_PROMISES = ("保证就业", "确保入职", "一定录用", "保证拿到 offer", "百分百录用")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_hash(snapshot_without_hash: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(snapshot_without_hash).encode("utf-8")).hexdigest()


def create_input_snapshot(
    report_obj: Dict[str, Any],
    *,
    resume_id: int,
    primary_job_id: str,
    target_job_ids: List[str],
    match_goal: str,
    settings_revision: int | None,
    captured_at: str | None = None,
    constraints: Dict[str, Any] | None = None,
    preference_snapshot: Dict[str, Any] | None = None,
    preference_revisions: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Freeze the exact profile/job evidence used by this report version."""
    target_roles = [
        {
            "job_id": job_id,
            "role": "primary" if job_id == primary_job_id else ("alternative" if index < 3 else "observe"),
            "order": index + 1,
        }
        for index, job_id in enumerate(target_job_ids)
    ]
    payload: Dict[str, Any] = {
        "schema_version": 2,
        "captured_at": captured_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "resume_id": int(resume_id),
        "personality_profile_id": (
            int(preference_snapshot.get("personality_profile_id") or 0)
            if preference_snapshot and preference_snapshot.get("personality_profile_id")
            else None
        ),
        "profile": copy.deepcopy(report_obj.get("student") or {}),
        "preference_profile": copy.deepcopy(preference_snapshot),
        "targets": copy.deepcopy(report_obj.get("targets") or []),
        "constraints": {
            "match_goal": match_goal,
            "primary_job_id": primary_job_id,
            "target_job_ids": list(target_job_ids),
            "target_roles": target_roles,
            **copy.deepcopy(constraints or {}),
        },
        "revisions": {
            "settings_revision": settings_revision,
            "profile_scoring_version": str((report_obj.get("student") or {}).get("scoring_version") or "legacy"),
            "job_snapshot_version": str(report_obj.get("job_snapshot_version") or "report-generated"),
            "graph_revision": str(report_obj.get("graph_revision") or "not-recorded"),
            "matching_algorithm": str(report_obj.get("matching_algorithm") or "current"),
            **copy.deepcopy(preference_revisions or {}),
        },
    }
    payload["sha256"] = snapshot_hash(payload)
    return payload


def verify_input_snapshot(snapshot: Any) -> bool:
    if not isinstance(snapshot, dict) or int(snapshot.get("schema_version") or 0) not in {1, 2}:
        return False
    expected = str(snapshot.get("sha256") or "").strip()
    if len(expected) != 64:
        return False
    unsigned = {key: copy.deepcopy(value) for key, value in snapshot.items() if key != "sha256"}
    return snapshot_hash(unsigned) == expected


def ensure_input_snapshot(
    report_obj: Dict[str, Any],
    *,
    resume_id: int,
    primary_job_id: str,
    target_job_ids: List[str],
    match_goal: str,
    settings_revision: int | None,
    preference_snapshot: Dict[str, Any] | None = None,
    preference_revisions: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, Any], bool]:
    existing = report_obj.get("input_snapshot")
    if existing is not None:
        if not verify_input_snapshot(existing):
            raise ValueError("input_snapshot_hash_mismatch")
        return copy.deepcopy(existing), False
    snapshot = create_input_snapshot(
        report_obj,
        resume_id=resume_id,
        primary_job_id=primary_job_id,
        target_job_ids=target_job_ids,
        match_goal=match_goal,
        settings_revision=settings_revision,
        captured_at=str(report_obj.get("generated_at") or "") or None,
        preference_snapshot=preference_snapshot,
        preference_revisions=preference_revisions,
    )
    return snapshot, True


def profile_from_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    profile = snapshot.get("profile")
    return copy.deepcopy(profile) if isinstance(profile, dict) else {}


def create_evidence_packet(
    report_obj: Dict[str, Any],
    *,
    input_snapshot_sha256: str,
    collected_at: str | None = None,
) -> Dict[str, Any]:
    """Freeze the post-retrieval facts/resources that AI is allowed to cite."""
    resources_by_target: List[Dict[str, Any]] = []
    recommendations = report_obj.get("recommendations") if isinstance(report_obj.get("recommendations"), dict) else {}
    for block in recommendations.get("by_target") or []:
        if not isinstance(block, dict):
            continue
        resources = []
        for item in block.get("learning_resources") or []:
            if isinstance(item, dict) and item.get("resource_id"):
                resources.append({
                    "kind": "learning_resource", "id": str(item.get("resource_id")),
                    "label": str(item.get("resource_name") or ""), "url": str(item.get("resource_url") or ""),
                })
        for item in block.get("competitions") or []:
            if isinstance(item, dict) and item.get("competition_id"):
                resources.append({
                    "kind": "competition", "id": str(item.get("competition_id")),
                    "label": str(item.get("competition_name") or ""), "url": str(item.get("official_url") or ""),
                })
        resources_by_target.append({"job_id": str(block.get("job_id") or ""), "resources": resources})

    target_facts = []
    for target in report_obj.get("targets") or []:
        if not isinstance(target, dict):
            continue
        preview = target.get("match_preview") if isinstance(target.get("match_preview"), dict) else {}
        target_facts.append({
            "job_id": _target_id(target),
            "match_score": preview.get("match_score"),
            "student_scores": copy.deepcopy(preview.get("student_scores") or {}),
            "job_requirement_scores": copy.deepcopy(preview.get("job_requirement_scores") or {}),
            "dimension_gaps": copy.deepcopy(preview.get("dimension_gaps") or {}),
        })
    packet: Dict[str, Any] = {
        "schema_version": 1,
        "collected_at": collected_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "input_snapshot_sha256": input_snapshot_sha256,
        "target_facts": target_facts,
        "resources_by_target": resources_by_target,
    }
    packet["sha256"] = snapshot_hash(packet)
    return packet


def _target_id(target: Dict[str, Any]) -> str:
    return str(target.get("id") or target.get("job_id") or "").strip()


def _plan_index(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(plan.get("job_id") or "").strip(): plan
        for plan in report.get("plans_by_target") or []
        if isinstance(plan, dict) and str(plan.get("job_id") or "").strip()
    }


def _iter_plan_items(plan: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    phases = plan.get("phases") if isinstance(plan.get("phases"), dict) else {}
    for phase_key in _PHASE_KEYS:
        phase = phases.get(phase_key) if isinstance(phases.get(phase_key), dict) else {}
        for item in phase.get("items") or []:
            if isinstance(item, dict):
                yield phase_key, item


def _is_specific_action(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    if any(term.lower() in value.lower() for term in _FORBIDDEN_PROMISES):
        return False
    has_concrete = any(marker.lower() in value.lower() for marker in _CONCRETE_MARKERS)
    has_quantity = bool(re.search(r"\d|一[次份项页周月]|两[次份项页周月]", value))
    vague = any(term in value for term in _VAGUE_ONLY)
    return (has_concrete or has_quantity) and not (vague and not has_concrete and not has_quantity)


def _resource_ids(report: Dict[str, Any]) -> set[str]:
    result: set[str] = set()
    recommendations = report.get("recommendations") if isinstance(report.get("recommendations"), dict) else {}
    for block in recommendations.get("by_target") or []:
        if not isinstance(block, dict):
            continue
        for item in (block.get("learning_resources") or []) + (block.get("competitions") or []):
            if not isinstance(item, dict):
                continue
            value = item.get("resource_id") or item.get("competition_id") or item.get("id")
            if value:
                result.add(str(value))
    return result


def _assess(base: Dict[str, Any], candidate: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    expected_ids = [str(value) for value in (snapshot.get("constraints") or {}).get("target_job_ids") or []]
    candidate_ids = [_target_id(target) for target in candidate.get("targets") or [] if isinstance(target, dict)]
    plan_by_id = _plan_index(candidate)
    base_plans = _plan_index(base)

    traceability = 0.0
    if verify_input_snapshot(snapshot):
        traceability += 10
    else:
        issues.append({"code": "snapshot_invalid", "severity": "error", "repairable": False})
    if candidate_ids == expected_ids:
        traceability += 15
    else:
        issues.append({"code": "target_set_changed", "severity": "error", "repairable": True})
    dimensions_valid = True
    for job_id, plan in plan_by_id.items():
        for phase_key, item in _iter_plan_items(plan):
            dimension = str(item.get("focus_dimension") or "")
            if dimension and dimension not in DIM_LABELS:
                dimensions_valid = False
                issues.append({"code": "unknown_dimension", "severity": "error", "repairable": True, "job_id": job_id, "path": f"phases.{phase_key}.{dimension}"})
    if dimensions_valid:
        traceability += 10

    invalid_fact_refs = []
    missing_structured_fact_refs = 0

    actions: List[Tuple[str, str, Dict[str, Any]]] = []
    milestone_count = 0
    item_count = 0
    for job_id, plan in plan_by_id.items():
        for _, item in _iter_plan_items(plan):
            item_count += 1
            if str(item.get("milestone") or "").strip():
                milestone_count += 1
            for action in item.get("custom_actions") or []:
                if isinstance(action, dict):
                    actions.append((job_id, str(action.get("text") or "").strip(), action))
                    allowed_facts = {
                        value
                        for dimension in DIM_LABELS
                        for value in (
                            f"profile:{dimension}",
                            f"job:{job_id}:{dimension}",
                            f"gap:{job_id}:{dimension}",
                        )
                    }
                    refs = [str(value) for value in action.get("fact_refs") or []]
                    invalid_fact_refs.extend(value for value in refs if value not in allowed_facts)
                    if (action.get("deliverable") or action.get("acceptance_rule")) and not refs:
                        missing_structured_fact_refs += 1
    if invalid_fact_refs:
        traceability = max(0.0, traceability - 7.0)
        issues.append({"code": "unknown_fact_refs", "severity": "error", "repairable": True, "count": len(invalid_fact_refs)})
    if missing_structured_fact_refs:
        traceability = max(0.0, traceability - 5.0)
        issues.append({"code": "missing_structured_fact_refs", "severity": "warning", "repairable": True, "count": missing_structured_fact_refs})
    specific_count = sum(1 for _, text, _ in actions if _is_specific_action(text))
    specificity = 20.0 * ((specific_count / len(actions)) if actions else 0.0)
    if actions and specific_count < len(actions):
        issues.append({"code": "vague_actions", "severity": "warning", "repairable": True, "count": len(actions) - specific_count})
    if item_count:
        specificity = min(20.0, specificity * 0.8 + 4.0 * milestone_count / item_count)

    valid_kind_count = sum(1 for _, _, action in actions if str(action.get("kind") or "") in _ACTION_KINDS)
    normalized_texts = [re.sub(r"\s+", "", text).lower() for _, text, _ in actions if text]
    unique_ratio = len(set(normalized_texts)) / len(normalized_texts) if normalized_texts else 0.0
    allowed_resources = _resource_ids(candidate) | _resource_ids(base)
    invalid_refs = []
    for job_id, _, action in actions:
        for ref_id in action.get("resource_refs") or []:
            if str(ref_id) not in allowed_resources:
                invalid_refs.append((job_id, "action", str(ref_id)))
    for job_id, plan in plan_by_id.items():
        for phase_key, item in _iter_plan_items(plan):
            for ref in (item.get("learning_path_refs") or []) + (item.get("practice_plan_refs") or []):
                if not isinstance(ref, dict):
                    continue
                ref_id = str(ref.get("id") or "").strip()
                if ref_id and ref_id not in allowed_resources:
                    invalid_refs.append((job_id, phase_key, ref_id))
    actionability = 8.0 * (valid_kind_count / len(actions) if actions else 0.0) + 5.0 * unique_ratio
    if not invalid_refs:
        actionability += 7.0
    else:
        issues.append({"code": "unknown_resource_refs", "severity": "error", "repairable": True, "count": len(invalid_refs)})

    plans_covered = sum(1 for job_id in expected_ids if job_id in plan_by_id)
    plan_coverage = plans_covered / len(expected_ids) if expected_ids else 0.0
    narrative_texts = [
        str(((plan_by_id.get(job_id) or {}).get("narrative") or {}).get("path_advice") or "").strip()
        for job_id in expected_ids
    ]
    narratives = sum(1 for text in narrative_texts if text)
    specific_narratives = sum(1 for text in narrative_texts if _is_specific_action(text))
    narrative_coverage = specific_narratives / len(expected_ids) if expected_ids else 0.0
    coverage = 10.0 * plan_coverage + 5.0 * narrative_coverage
    if plan_coverage < 1:
        issues.append({"code": "missing_target_plans", "severity": "error", "repairable": True})
    if narrative_coverage < 1:
        issues.append({"code": "generic_or_missing_target_narratives", "severity": "warning", "repairable": True})

    consistent_scores = 0
    snapshot_targets = {_target_id(target): target for target in snapshot.get("targets") or [] if isinstance(target, dict)}
    for job_id in expected_ids:
        expected_score = float(((snapshot_targets.get(job_id) or {}).get("match_preview") or {}).get("match_score") or 0)
        actual_score = float((plan_by_id.get(job_id) or {}).get("match_score") or 0)
        if abs(expected_score - actual_score) < 0.01:
            consistent_scores += 1
        else:
            issues.append({"code": "match_score_changed", "severity": "error", "repairable": True, "job_id": job_id})
    consistency = 10.0 * (consistent_scores / len(expected_ids) if expected_ids else 0.0)
    normalized_narratives = [re.sub(r"\s+", "", text).lower() for text in narrative_texts if text]
    duplicate_target_narratives = len(normalized_narratives) > 1 and len(set(normalized_narratives)) == 1
    if duplicate_target_narratives:
        consistency = max(0.0, consistency - 3.0)
        issues.append({"code": "duplicate_target_narratives", "severity": "warning", "repairable": True})

    dimensions = {
        "traceability": round(traceability, 1),
        "specificity": round(specificity, 1),
        "actionability": round(actionability, 1),
        "coverage": round(coverage, 1),
        "consistency": round(consistency, 1),
    }
    score = round(sum(dimensions.values()), 1)
    hard_gate_codes = {
        "snapshot_invalid", "target_set_changed", "unknown_dimension", "unknown_fact_refs",
        "missing_structured_fact_refs", "unknown_resource_refs", "match_score_changed",
        "duplicate_target_narratives",
    }
    if any(issue.get("code") in hard_gate_codes for issue in issues):
        score = min(score, 84.0)
    return {
        "score": score,
        "dimensions": dimensions,
        "issues": issues,
        "stats": {
            "target_count": len(expected_ids),
            "action_count": len(actions),
            "specific_action_count": specific_count,
            "plan_coverage": round(plan_coverage, 3),
            "narrative_coverage": round(narrative_coverage, 3),
        },
        "base_plan_count": len(base_plans),
    }


def _repair_candidate(base: Dict[str, Any], candidate: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    repaired = copy.deepcopy(candidate)
    expected_ids = [str(value) for value in (snapshot.get("constraints") or {}).get("target_job_ids") or []]
    base_targets = {_target_id(target): target for target in base.get("targets") or [] if isinstance(target, dict)}
    repaired["targets"] = [copy.deepcopy(base_targets[job_id]) for job_id in expected_ids if job_id in base_targets]
    base_plans = _plan_index(base)
    candidate_plans = _plan_index(repaired)
    allowed_resources = _resource_ids(repaired) | _resource_ids(base)
    output_plans: List[Dict[str, Any]] = []
    narrative_counts: Dict[str, int] = {}
    for plan in candidate_plans.values():
        text = str((plan.get("narrative") or {}).get("path_advice") or "").strip() if isinstance(plan.get("narrative"), dict) else ""
        key = re.sub(r"\s+", "", text).lower()
        if key:
            narrative_counts[key] = narrative_counts.get(key, 0) + 1

    for job_id in expected_ids:
        baseline = base_plans.get(job_id)
        plan = copy.deepcopy(candidate_plans.get(job_id) or baseline or {})
        if not plan:
            continue
        expected_score = float((baseline or {}).get("match_score") or 0)
        plan["match_score"] = expected_score
        phases = plan.get("phases") if isinstance(plan.get("phases"), dict) else {}
        base_phases = (baseline or {}).get("phases") if isinstance((baseline or {}).get("phases"), dict) else {}
        for phase_key in _PHASE_KEYS:
            phase = phases.get(phase_key) if isinstance(phases.get(phase_key), dict) else None
            if phase is None:
                if isinstance(base_phases.get(phase_key), dict):
                    phases[phase_key] = copy.deepcopy(base_phases[phase_key])
                continue
            base_items = {
                str(item.get("focus_dimension") or ""): item
                for item in (base_phases.get(phase_key) or {}).get("items") or []
                if isinstance(item, dict)
            }
            fixed_items = []
            for item in phase.get("items") or []:
                if not isinstance(item, dict):
                    continue
                dimension = str(item.get("focus_dimension") or "")
                if dimension not in DIM_LABELS:
                    continue
                baseline_item = base_items.get(dimension) or {}
                seen: set[str] = set()
                fixed_actions = []
                for action in item.get("custom_actions") or []:
                    if not isinstance(action, dict):
                        continue
                    text = str(action.get("text") or "").strip()
                    key = re.sub(r"\s+", "", text).lower()
                    if not text or key in seen or not _is_specific_action(text):
                        continue
                    seen.add(key)
                    fixed_action = copy.deepcopy(action)
                    fixed_action["kind"] = str(action.get("kind") or "practice") if str(action.get("kind") or "") in _ACTION_KINDS else "practice"
                    fixed_action["text"] = text[:150]
                    allowed_facts = {
                        f"profile:{dimension}",
                        f"job:{job_id}:{dimension}",
                        f"gap:{job_id}:{dimension}",
                    }
                    fixed_action["fact_refs"] = [
                        str(value) for value in action.get("fact_refs") or [] if str(value) in allowed_facts
                    ]
                    if (action.get("deliverable") or action.get("acceptance_rule")) and not fixed_action["fact_refs"]:
                        fixed_action["fact_refs"] = [f"gap:{job_id}:{dimension}"]
                    fixed_action["resource_refs"] = [
                        str(value) for value in action.get("resource_refs") or [] if str(value) in allowed_resources
                    ]
                    fixed_actions.append(fixed_action)
                if not fixed_actions:
                    fixed_actions = copy.deepcopy(baseline_item.get("custom_actions") or [])
                item["custom_actions"] = fixed_actions[:5]
                for refs_key in ("learning_path_refs", "practice_plan_refs"):
                    item[refs_key] = [
                        ref
                        for ref in item.get(refs_key) or []
                        if isinstance(ref, dict) and (not ref.get("id") or str(ref.get("id")) in allowed_resources)
                    ]
                if not str(item.get("milestone") or "").strip():
                    item["milestone"] = baseline_item.get("milestone") or f"形成一项{DIM_LABELS.get(dimension, dimension)}可查看成果"
                fixed_items.append(item)
            phase["items"] = fixed_items or copy.deepcopy((base_phases.get(phase_key) or {}).get("items") or [])
        plan["phases"] = phases
        narrative_text = str((plan.get("narrative") or {}).get("path_advice") or "").strip() if isinstance(plan.get("narrative"), dict) else ""
        narrative_key = re.sub(r"\s+", "", narrative_text).lower()
        if not _is_specific_action(narrative_text) or narrative_counts.get(narrative_key, 0) > 1:
            plan["narrative"] = copy.deepcopy((baseline or {}).get("narrative") or {})
        output_plans.append(plan)
    repaired["plans_by_target"] = output_plans
    return repaired


def gate_enrichment(
    base_report: Dict[str, Any],
    candidate_report: Dict[str, Any],
    input_snapshot: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return a safe candidate plus a compact, user-safe quality report."""
    initial = _assess(base_report, candidate_report, input_snapshot)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if initial["score"] >= 85:
        quality = {**initial, "status": "accepted", "initial_score": initial["score"], "repair_attempts": 0, "checked_at": now}
        return copy.deepcopy(candidate_report), quality

    repaired = _repair_candidate(base_report, candidate_report, input_snapshot)
    repaired_score = _assess(base_report, repaired, input_snapshot)
    if repaired_score["score"] >= 70:
        quality = {**repaired_score, "status": "repaired", "initial_score": initial["score"], "repair_attempts": 1, "checked_at": now}
        return repaired, quality

    fallback = copy.deepcopy(base_report)
    fallback["llm_enrich_pending"] = False
    fallback_score = _assess(base_report, fallback, input_snapshot)
    quality = {
        **fallback_score,
        "status": "fallback",
        "initial_score": initial["score"],
        "repair_score": repaired_score["score"],
        "repair_attempts": 1,
        "checked_at": now,
        "fallback_reason": "quality_below_threshold",
    }
    return fallback, quality
