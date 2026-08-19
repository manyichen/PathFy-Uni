"""Two-step review confirmation and plan-proposal helpers.

The functions in this module are deliberately pure.  Natural-language values are
only candidates; evaluation and plan mutation happen after an explicit decision.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


REVIEW_CYCLES = {"weekly", "monthly"}
REVIEW_STATUSES = {
    "on_track",
    "partial",
    "overloaded",
    "evidence_missing",
    "goal_changed",
    "data_insufficient",
    "stalled",
}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_review_cycle(value: Any) -> str:
    cycle = str(value or "monthly").strip().lower()
    if cycle not in REVIEW_CYCLES:
        raise ValueError("review_cycle 仅支持 weekly 或 monthly")
    return cycle


def _source_excerpt(text: str, value: float) -> str:
    variants = [str(value), f"{value:g}"]
    indexes = [text.find(item) for item in variants if item and text.find(item) >= 0]
    if not indexes:
        return text[:120]
    start = max(0, min(indexes) - 32)
    end = min(len(text), min(indexes) + 72)
    return text[start:end].strip()


def build_metric_candidates(
    *,
    review_text: str,
    metric_definitions: List[Dict[str, Any]],
    extracted_metrics: Dict[str, Any],
    extraction_source: str,
    system_metrics: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Create review candidates with evidence and confidence, never confirmation."""
    definitions = {
        str(item.get("code") or "").strip(): item
        for item in metric_definitions
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    }
    candidates: List[Dict[str, Any]] = []
    merged: Dict[str, tuple[Any, str]] = {
        str(code): (value, extraction_source or "heuristic")
        for code, value in (extracted_metrics or {}).items()
        if value is not None
    }
    for code, value in (system_metrics or {}).items():
        if value is not None and code not in merged:
            merged[str(code)] = (value, "system")

    for code, (raw_value, origin) in merged.items():
        try:
            value = round(float(raw_value), 4)
        except (TypeError, ValueError):
            continue
        definition = definitions.get(code) or {}
        source_text = (
            "由当前简历能力快照与目标岗位基线重新计算"
            if origin == "system"
            else _source_excerpt(review_text, value)
        )
        confidence = 1.0 if origin in {"system", "user_submitted"} else (0.86 if origin == "heuristic_fallback" else 0.72)
        candidates.append(
            {
                "code": code,
                "label": str(definition.get("label") or code),
                "target": str(definition.get("target") or ""),
                "value": value,
                "source_text": source_text,
                "source_type": "system_calculation" if origin == "system" else ("user_input" if origin == "user_submitted" else "review_text"),
                "origin": origin,
                "confidence": confidence,
                "decision": "pending",
            }
        )
    return candidates


def confirmed_metrics_from_decisions(
    stored_candidates: List[Dict[str, Any]],
    decisions: Iterable[Dict[str, Any]],
) -> tuple[Dict[str, float], List[Dict[str, Any]]]:
    allowed = {
        str(item.get("code") or ""): item
        for item in stored_candidates
        if isinstance(item, dict) and str(item.get("code") or "")
    }
    metrics: Dict[str, float] = {}
    audited: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in decisions:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or "").strip()
        if not code or code in seen or code not in allowed:
            continue
        seen.add(code)
        decision = str(raw.get("decision") or "ignore").strip().lower()
        if decision not in {"confirm", "ignore"}:
            raise ValueError(f"指标 {code} 的 decision 仅支持 confirm 或 ignore")
        item = copy.deepcopy(allowed[code])
        item["decision"] = decision
        if decision == "confirm":
            try:
                value = float(raw.get("value", item.get("value")))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"指标 {code} 的确认值无效") from exc
            if not (-1_000_000 <= value <= 1_000_000):
                raise ValueError(f"指标 {code} 的确认值超出允许范围")
            value = round(value, 4)
            item["value"] = value
            metrics[code] = value
        audited.append(item)
    for code, item in allowed.items():
        if code not in seen:
            ignored = copy.deepcopy(item)
            ignored["decision"] = "ignore"
            audited.append(ignored)
    return metrics, audited


def classify_review_status(
    metric_eval: Dict[str, Any],
    *,
    signals: Dict[str, Any] | None = None,
    evidence_records: List[Dict[str, Any]] | None = None,
) -> str:
    signals = signals or {}
    if bool(signals.get("goal_changed")):
        return "goal_changed"
    if bool(signals.get("overloaded")):
        return "overloaded"
    planned = _optional_float(signals.get("planned_hours"))
    actual = _optional_float(signals.get("actual_hours"))
    if planned and actual is not None and actual > planned * 1.2:
        return "overloaded"
    if bool(signals.get("stalled")):
        return "stalled"
    has_metric_evidence = bool(metric_eval.get("has_evidence"))
    has_action_evidence = bool(metric_eval.get("has_action_evidence"))
    if not has_metric_evidence and not has_action_evidence:
        return "data_insufficient"
    if bool(signals.get("evidence_missing")):
        return "evidence_missing"
    if evidence_records is not None and not evidence_records and bool(signals.get("expected_deliverable")):
        return "evidence_missing"
    if bool(metric_eval.get("all_passed")):
        return "on_track"
    if int(metric_eval.get("evaluated_count") or 0) > 0:
        return "partial" if float(metric_eval.get("pass_rate") or 0) > 0 else "stalled"
    if has_action_evidence:
        completion_rate = float(metric_eval.get("action_completion_rate") or 0.0)
        return "on_track" if completion_rate >= 0.8 else "partial"
    return "data_insufficient"


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def build_plan_diff(
    current_report: Dict[str, Any],
    proposed_report: Dict[str, Any],
    *,
    scope: str,
    job_id: str | None,
) -> List[Dict[str, Any]]:
    """Build coarse, independently applicable changes for partial acceptance."""
    changes: List[Dict[str, Any]] = []
    current_plans = {
        str(plan.get("job_id") or ""): plan
        for plan in current_report.get("plans_by_target") or []
        if isinstance(plan, dict)
    }
    proposed_plans = {
        str(plan.get("job_id") or ""): plan
        for plan in proposed_report.get("plans_by_target") or []
        if isinstance(plan, dict)
    }
    allowed_ids = {job_id} if scope == "target" and job_id else set(proposed_plans)
    for target_id in sorted(allowed_ids):
        before_plan = current_plans.get(target_id) or {}
        after_plan = proposed_plans.get(target_id) or {}
        before = {
            "current_plan_month": before_plan.get("current_plan_month"),
            "next_month_plan": before_plan.get("next_month_plan"),
        }
        after = {
            "current_plan_month": after_plan.get("current_plan_month"),
            "next_month_plan": after_plan.get("next_month_plan"),
        }
        if before != after:
            changes.append(_change("replace_target_plan", target_id, before, after, summary=_target_plan_summary(before, after)))

    if scope == "all" and current_report.get("growth_plan") != proposed_report.get("growth_plan"):
        changes.append(_change("replace_growth_plan", None, current_report.get("growth_plan"), proposed_report.get("growth_plan")))

    current_adjustments = (((current_report.get("development_lines") or {}).get("adjustments")) or [])
    proposed_adjustments = (((proposed_report.get("development_lines") or {}).get("adjustments")) or [])
    current_ids = {str(item.get("id") or "") for item in current_adjustments if isinstance(item, dict)}
    added = [item for item in proposed_adjustments if isinstance(item, dict) and str(item.get("id") or "") not in current_ids]
    if added:
        changes.append(_change("append_adjustments", job_id, [], added))
    return changes


def _action_rows(plan_slice: Any) -> List[Dict[str, Any]]:
    next_plan = plan_slice.get("next_month_plan") if isinstance(plan_slice, dict) else {}
    rows: List[Dict[str, Any]] = []
    for item in (next_plan or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        for action in item.get("custom_actions") or []:
            if not isinstance(action, dict):
                continue
            title = str(action.get("title") or action.get("text") or action.get("deliverable") or "").strip()
            if title:
                rows.append(
                    {
                        "title": title,
                        "deadline": str(action.get("deadline") or ""),
                        "effort_hours": action.get("effort_hours"),
                    }
                )
    return rows


def _target_plan_summary(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    previous = _action_rows(before)
    proposed = _action_rows(after)
    previous_titles = {item["title"] for item in previous}
    proposed_titles = {item["title"] for item in proposed}
    return {
        "kept": [item for item in proposed if item["title"] in previous_titles],
        "added": [item for item in proposed if item["title"] not in previous_titles],
        "removed": [item for item in previous if item["title"] not in proposed_titles],
        "before_month": before.get("current_plan_month"),
        "after_month": after.get("current_plan_month"),
    }


def _change(kind: str, job_id: str | None, before: Any, after: Any, *, summary: Dict[str, Any] | None = None) -> Dict[str, Any]:
    seed = json.dumps({"kind": kind, "job_id": job_id, "before": before, "after": after}, ensure_ascii=False, sort_keys=True)
    return {
        "id": f"chg_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}",
        "kind": kind,
        "job_id": job_id,
        "before": copy.deepcopy(before),
        "after": copy.deepcopy(after),
        "accepted": True,
        "summary": summary or {},
    }


def apply_plan_changes(report_obj: Dict[str, Any], changes: List[Dict[str, Any]], accepted_ids: set[str]) -> List[str]:
    applied: List[str] = []
    plans = report_obj.get("plans_by_target") or []
    for change in changes:
        change_id = str(change.get("id") or "")
        if change_id not in accepted_ids:
            continue
        kind = str(change.get("kind") or "")
        after = copy.deepcopy(change.get("after"))
        if kind == "replace_target_plan":
            target_id = str(change.get("job_id") or "")
            plan = next((item for item in plans if isinstance(item, dict) and str(item.get("job_id") or "") == target_id), None)
            if not plan or not isinstance(after, dict):
                continue
            plan["current_plan_month"] = after.get("current_plan_month")
            plan["next_month_plan"] = after.get("next_month_plan")
        elif kind == "replace_growth_plan":
            report_obj["growth_plan"] = after
        elif kind == "append_adjustments":
            development = report_obj.setdefault("development_lines", {})
            existing = development.setdefault("adjustments", [])
            existing_ids = {str(item.get("id") or "") for item in existing if isinstance(item, dict)}
            existing.extend(item for item in (after or []) if isinstance(item, dict) and str(item.get("id") or "") not in existing_ids)
        else:
            continue
        applied.append(change_id)
    return applied


def apply_change_overrides(
    changes: List[Dict[str, Any]],
    overrides: Iterable[Dict[str, Any]],
    accepted_ids: set[str],
) -> List[Dict[str, Any]]:
    """Apply user edits only to the editable `after` payload of accepted changes."""
    result = copy.deepcopy(changes)
    by_id = {str(item.get("id") or ""): item for item in result if isinstance(item, dict)}
    for override in overrides:
        if not isinstance(override, dict):
            continue
        change_id = str(override.get("id") or "")
        target = by_id.get(change_id)
        if not target or change_id not in accepted_ids or "after" not in override:
            continue
        after = override.get("after")
        expected_list = str(target.get("kind") or "") == "append_adjustments"
        if (expected_list and not isinstance(after, list)) or (not expected_list and not isinstance(after, dict)):
            raise ValueError(f"变更 {change_id} 的编辑内容格式无效")
        if len(json.dumps(after, ensure_ascii=False)) > 100_000:
            raise ValueError(f"变更 {change_id} 的编辑内容过大")
        target["after"] = copy.deepcopy(after)
    return result
