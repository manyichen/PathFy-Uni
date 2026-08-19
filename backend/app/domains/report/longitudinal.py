"""Deterministic longitudinal insights built only from confirmed user history."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if len(text) == 14 and text.isdigit():
            try:
                parsed = datetime.strptime(text, "%Y%m%d%H%M%S")
            except ValueError:
                return None
        else:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                try:
                    parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _freshness_item(
    *,
    as_of: Any,
    now: datetime,
    aging_days: int,
    stale_days: int,
    source_label: str,
    refresh_action: str,
    forced_outdated: bool = False,
) -> Dict[str, Any]:
    stamp = _dt(as_of)
    if stamp is None:
        return {
            "status": "unknown",
            "as_of": None,
            "age_days": None,
            "source_label": source_label,
            "reason": "缺少可核验更新时间",
            "refresh_action": refresh_action,
        }
    age_days = max(0, (now - stamp).days)
    if forced_outdated:
        status, reason = "outdated", "源数据在报告快照之后发生变化"
    elif age_days > stale_days:
        status, reason = "stale", f"已超过 {stale_days} 天有效期"
    elif age_days > aging_days:
        status, reason = "aging", f"已使用 {age_days} 天，建议近期刷新"
    else:
        status, reason = "fresh", "仍在当前口径的有效期内"
    return {
        "status": status,
        "as_of": stamp.isoformat().replace("+00:00", "Z"),
        "age_days": age_days,
        "source_label": source_label,
        "reason": reason,
        "refresh_action": refresh_action,
    }


def build_layered_freshness(
    report_obj: Dict[str, Any],
    *,
    report_created_at: Any,
    report_updated_at: Any,
    profile_updated_at: Any,
    latest_review_at: Any,
    latest_plan_at: Any,
    now: datetime | None = None,
) -> Dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    snapshot_at = ((report_obj.get("input_snapshot") or {}).get("captured_at")) or report_created_at
    snapshot_dt = _dt(snapshot_at)
    profile_dt = _dt(profile_updated_at)
    profile_changed = bool(profile_dt and snapshot_dt and profile_dt > snapshot_dt + timedelta(seconds=1))
    enrichment_at = ((report_obj.get("enrichment") or {}).get("completed_at")) or report_updated_at
    domains = {
        "profile": _freshness_item(
            as_of=profile_updated_at, now=current, aging_days=14, stale_days=30,
            source_label="当前能力画像", refresh_action="重新分析简历并刷新报告", forced_outdated=profile_changed,
        ),
        "job_market": _freshness_item(
            as_of=snapshot_at, now=current, aging_days=14, stale_days=30,
            source_label="岗位与匹配输入快照", refresh_action="刷新岗位公开信息或重新生成报告",
        ),
        "resources": _freshness_item(
            as_of=enrichment_at, now=current, aging_days=21, stale_days=45,
            source_label="资源与增强结果", refresh_action="仅刷新资源",
        ),
        "plan": _freshness_item(
            as_of=latest_plan_at or report_updated_at, now=current, aging_days=14, stale_days=35,
            source_label="当前已接受计划", refresh_action="完成复盘并核对计划提案",
        ),
        "review": _freshness_item(
            as_of=latest_review_at, now=current, aging_days=10, stale_days=40,
            source_label="最近确认复盘", refresh_action="完成周复盘或月复盘",
        ),
    }
    stale_domains = [key for key, item in domains.items() if item["status"] in {"stale", "outdated", "unknown"}]
    aging_domains = [key for key, item in domains.items() if item["status"] == "aging"]
    return {
        "overall_status": "stale" if stale_domains else "aging" if aging_domains else "fresh",
        "stale_domains": stale_domains,
        "aging_domains": aging_domains,
        "domains": domains,
    }


def _json(value: Any, default: Any) -> Any:
    import json
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return value if value is not None else default


def _current_actions(report_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for plan in report_obj.get("plans_by_target") or []:
        if not isinstance(plan, dict):
            continue
        for item in ((plan.get("next_month_plan") or {}).get("items")) or []:
            if not isinstance(item, dict):
                continue
            actions.extend(action for action in item.get("custom_actions") or [] if isinstance(action, dict))
    return actions


def build_execution_profile(
    report_obj: Dict[str, Any],
    review_rows: Iterable[Dict[str, Any]],
    action_event_rows: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    reviews: List[Dict[str, Any]] = []
    for row in review_rows:
        metrics = _json(row.get("metrics_json"), {})
        adjustment = _json(row.get("adjustment_json"), {})
        if not isinstance(metrics, dict):
            metrics = {}
        status = str(metrics.get("review_status") or (adjustment or {}).get("review_status") or "data_insufficient")
        reviews.append({"id": row.get("id"), "status": status, "metrics": metrics, "created_at": row.get("created_at")})

    events: List[Dict[str, Any]] = []
    for row in action_event_rows:
        payload = _json(row.get("payload_json"), {})
        events.append({**row, "payload": payload if isinstance(payload, dict) else {}})
    completed_events = [row for row in events if row.get("event_type") == "action_completed"]
    reopened_events = [row for row in events if row.get("event_type") == "action_reopened"]
    current_actions = _current_actions(report_obj)
    current_done = sum(1 for action in current_actions if action.get("done"))
    current_total = len(current_actions)
    completion_rate = round(current_done / current_total, 4) if current_total else None
    statuses = Counter(row["status"] for row in reviews)

    if not reviews and not events:
        diagnosis, label = "data_insufficient", "历史样本不足"
    elif statuses["goal_changed"]:
        diagnosis, label = "goal_changed", "目标发生变化"
    elif statuses["overloaded"] >= max(1, len(reviews) // 3):
        diagnosis, label = "time_capacity", "可用时间不足或任务过载"
    elif statuses["evidence_missing"]:
        diagnosis, label = "evidence_habit", "执行有发生，但证据沉淀不足"
    elif statuses["stalled"] >= 2 or (completion_rate is not None and completion_rate < 0.34):
        diagnosis, label = "execution_stalled", "当前计划推进阻力较大"
    elif reopened_events and len(reopened_events) >= len(completed_events):
        diagnosis, label = "plan_friction", "行动反复打开，任务颗粒度可能过大"
    else:
        diagnosis, label = "stable", "执行节奏基本稳定"

    evidence_points = len(reviews) + len(completed_events) + len(reopened_events)
    confidence = "high" if evidence_points >= 10 else "medium" if evidence_points >= 4 else "low"
    return {
        "diagnosis": diagnosis,
        "diagnosis_label": label,
        "confidence": confidence,
        "evidence_points": evidence_points,
        "confirmed_review_count": len(reviews),
        "review_status_distribution": dict(statuses),
        "action_event_count": len(completed_events) + len(reopened_events),
        "completion_events": len(completed_events),
        "reopen_events": len(reopened_events),
        "current_action_count": current_total,
        "current_done_count": current_done,
        "current_completion_rate": completion_rate,
    }


def build_longitudinal_trends(
    review_rows: Iterable[Dict[str, Any]],
    plan_version_rows: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    series: List[Dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for row in reversed(list(review_rows)):
        metrics = _json(row.get("metrics_json"), {})
        adjustment = _json(row.get("adjustment_json"), {})
        evaluation = metrics.get("evaluation") if isinstance(metrics, dict) else {}
        status = str((metrics or {}).get("review_status") or (adjustment or {}).get("review_status") or "data_insufficient")
        status_counts[status] += 1
        series.append(
            {
                "review_id": int(row.get("id") or 0),
                "cycle": row.get("review_cycle"),
                "status": status,
                "pass_rate": evaluation.get("pass_rate") if isinstance(evaluation, dict) else None,
                "confirmed_metric_count": len((metrics or {}).get("submitted") or {}),
                "created_at": str(row.get("created_at") or ""),
            }
        )
    versions = list(plan_version_rows)
    decided = [row for row in versions if str(row.get("status") or "") in {"accepted", "rejected"}]
    accepted = [row for row in decided if str(row.get("status") or "") == "accepted"]
    accepted_ratio = round(len(accepted) / len(decided), 4) if decided else None
    change_counts: List[int] = []
    partial_count = 0
    for row in accepted:
        changes = _json(row.get("diff_json"), [])
        decision = _json(row.get("decision_json"), {})
        selected = decision.get("accepted_change_ids") if isinstance(decision, dict) else []
        change_counts.append(len(selected or []))
        if isinstance(changes, list) and len(selected or []) < len(changes):
            partial_count += 1
    average_changes = round(sum(change_counts) / len(change_counts), 2) if change_counts else 0.0
    plan_stability = max(0.0, round(1.0 - min(1.0, average_changes / 5.0), 4))
    return {
        "review_series": series[-12:],
        "review_status_distribution": dict(status_counts),
        "goal_change_count": status_counts["goal_changed"],
        "proposal_count": len(versions),
        "decided_proposal_count": len(decided),
        "proposal_acceptance_rate": accepted_ratio,
        "partial_accept_count": partial_count,
        "average_accepted_changes": average_changes,
        "plan_stability": plan_stability,
    }


def build_personalization(
    execution: Dict[str, Any],
    trends: Dict[str, Any],
    *,
    enabled: bool,
    variant: str,
    weekly_hours_hint: Any = None,
) -> Dict[str, Any]:
    completion = execution.get("current_completion_rate")
    diagnosis = execution.get("diagnosis")
    try:
        configured_hours = max(1.0, min(40.0, float(weekly_hours_hint)))
    except (TypeError, ValueError):
        configured_hours = 6.0
    if diagnosis in {"time_capacity", "execution_stalled", "plan_friction"} or (completion is not None and completion < 0.4):
        action_limit = 2
        hours = max(2.0, round(configured_hours * 0.7, 1))
        focus = "缩小任务颗粒度，优先完成一个可验收产物"
    elif completion is not None and completion >= 0.8 and execution.get("evidence_points", 0) >= 4:
        action_limit = 4
        hours = min(20.0, round(configured_hours * 1.1, 1))
        focus = "保持节奏，并增加一项面向真实岗位的交付"
    else:
        action_limit = 3
        hours = configured_hours
        focus = "维持保守节奏，继续积累确认样本"
    sample_count = int(execution.get("evidence_points") or 0)
    recommendation_active = enabled and variant == "personalized_v1" and sample_count >= 2
    return {
        "enabled": enabled,
        "experiment": {"key": "career_pacing_v1", "variant": variant},
        "recommendation_active": recommendation_active,
        "suggested_weekly_action_limit": action_limit,
        "suggested_weekly_hours": hours,
        "focus": focus,
        "confidence": execution.get("confidence"),
        "learned_from": {
            "confirmed_reviews": execution.get("confirmed_review_count", 0),
            "action_events": execution.get("action_event_count", 0),
            "decided_proposals": trends.get("decided_proposal_count", 0),
            "excluded": ["未确认候选指标", "复盘草稿", "已过期计划提案"],
        },
        "explanation": "建议仅使用已确认复盘、行动事件和计划决定生成；样本不足时不自动改计划。",
    }


def build_reminders(report_obj: Dict[str, Any], latest_review_at: Any, *, now: datetime | None = None) -> List[Dict[str, Any]]:
    current = now or datetime.now(timezone.utc)
    reminders: List[Dict[str, Any]] = []
    for action in _current_actions(report_obj):
        if action.get("done"):
            continue
        due = _dt(action.get("deadline"))
        if not due:
            continue
        days = (due - current).days
        if days < 0:
            reminders.append({"kind": "action_overdue", "severity": "warning", "label": str(action.get("title") or action.get("text") or "行动已逾期"), "due_at": due.isoformat().replace("+00:00", "Z"), "days": days})
        elif days <= 3:
            reminders.append({"kind": "action_due", "severity": "info", "label": str(action.get("title") or action.get("text") or "行动即将到期"), "due_at": due.isoformat().replace("+00:00", "Z"), "days": days})
    latest = _dt(latest_review_at)
    if latest is None or (current - latest).days >= 10:
        reminders.append({"kind": "review_due", "severity": "info", "label": "建议完成一次周复盘，确认当前执行状态", "due_at": None, "days": None})
    return reminders[:6]


def build_longitudinal_insights(
    report_obj: Dict[str, Any],
    *,
    report_created_at: Any,
    report_updated_at: Any,
    profile_updated_at: Any,
    review_rows: List[Dict[str, Any]],
    plan_version_rows: List[Dict[str, Any]],
    action_event_rows: List[Dict[str, Any]],
    personalization_enabled: bool,
    experiment_variant: str,
    now: datetime | None = None,
) -> Dict[str, Any]:
    latest_review_at = review_rows[0].get("created_at") if review_rows else None
    decided_versions = [row for row in plan_version_rows if row.get("decided_at")]
    latest_plan_at = decided_versions[0].get("decided_at") if decided_versions else report_updated_at
    freshness = build_layered_freshness(
        report_obj,
        report_created_at=report_created_at,
        report_updated_at=report_updated_at,
        profile_updated_at=profile_updated_at,
        latest_review_at=latest_review_at,
        latest_plan_at=latest_plan_at,
        now=now,
    )
    execution = build_execution_profile(report_obj, review_rows, action_event_rows)
    trends = build_longitudinal_trends(review_rows, plan_version_rows)
    weekly_hours = ((report_obj.get("input_snapshot") or {}).get("constraints") or {}).get("weekly_hours")
    return {
        "schema_version": 1,
        "generated_at": (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "freshness": freshness,
        "execution_profile": execution,
        "trends": trends,
        "personalization": build_personalization(execution, trends, enabled=personalization_enabled, variant=experiment_variant, weekly_hours_hint=weekly_hours),
        "reminders": build_reminders(report_obj, latest_review_at, now=now),
        "privacy": {
            "learning_boundary": "仅使用已确认复盘、行动事件和计划决定",
            "unconfirmed_draft_retention_days": 90,
            "confirmed_history_retention": "保留至用户删除报告",
            "exportable": True,
            "deletable": True,
        },
    }
