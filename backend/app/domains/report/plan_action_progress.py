"""下月计划行动项完成状态（写回 report_json）。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple


class PlanActionProgressError(ValueError):
    """业务校验失败（由 services 转为 ReportServiceError）。"""


def build_progress_key(
    job_id: str,
    plan_month: int,
    item_index: int,
    action_index: int,
) -> str:
    return f"{str(job_id or '').strip()}|{int(plan_month)}|{int(item_index)}|{int(action_index)}"


def build_stable_action_ref(job_id: str, action: Dict[str, Any]) -> str:
    """Build an event identity that survives plan reordering and index changes."""
    semantic_parts = [
        str(job_id or "").strip(),
        str(action.get("action_id") or action.get("id") or "").strip(),
        str(action.get("kind") or "").strip().lower(),
        str(action.get("title") or action.get("text") or "").strip(),
        str(action.get("deliverable") or "").strip(),
    ]
    canonical = "\n".join(" ".join(part.split()) for part in semantic_parts)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"action:v1:{digest}"


def ensure_action_ids(report_obj: Dict[str, Any]) -> None:
    """Give every plan action a persisted identity that survives list reordering."""
    for plan in report_obj.get("plans_by_target") or []:
        if not isinstance(plan, dict):
            continue
        job_id = str(plan.get("job_id") or "").strip()
        items = ((plan.get("next_month_plan") or {}).get("items") or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            for action in item.get("custom_actions") or []:
                if not isinstance(action, dict):
                    continue
                action_uid = str(action.get("action_uid") or action.get("action_id") or "").strip()
                action["action_uid"] = action_uid or build_stable_action_ref(job_id, action)


def new_user_action_uid() -> str:
    return f"action:user:{uuid.uuid4().hex}"


def _ensure_progress_map(report_obj: Dict[str, Any]) -> Dict[str, Any]:
    raw = report_obj.get("action_progress")
    if not isinstance(raw, dict):
        raw = {}
        report_obj["action_progress"] = raw
    return raw


def sync_action_progress_to_plans(report_obj: Dict[str, Any]) -> None:
    """将 action_progress 索引同步到 plans_by_target 内 custom_actions.done。"""
    ensure_action_ids(report_obj)
    progress = report_obj.get("action_progress")
    if not isinstance(progress, dict) or not progress:
        return

    for plan in report_obj.get("plans_by_target") or []:
        if not isinstance(plan, dict):
            continue
        jid = str(plan.get("job_id") or "").strip()
        nmp = plan.get("next_month_plan")
        if not isinstance(nmp, dict):
            continue
        plan_month = int(nmp.get("plan_month") or plan.get("current_plan_month") or 1)
        items = nmp.get("items")
        if not isinstance(items, list):
            continue
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            actions = item.get("custom_actions")
            if not isinstance(actions, list):
                continue
            for action_index, act in enumerate(actions):
                if not isinstance(act, dict):
                    continue
                key = str(act.get("action_uid") or "")
                legacy_key = build_progress_key(jid, plan_month, item_index, action_index)
                entry = progress.get(key) or progress.get(legacy_key)
                if not isinstance(entry, dict):
                    continue
                if entry.get("done"):
                    act["done"] = True
                    if entry.get("done_at"):
                        act["done_at"] = str(entry["done_at"])
                elif "done" in entry and not entry.get("done"):
                    act["done"] = False
                    act.pop("done_at", None)


def summarize_plan_action_completion(
    report_obj: Dict[str, Any],
    *,
    target_job_ids: List[str] | None = None,
) -> Dict[str, Any]:
    """Snapshot the persisted checklist state for a review.

    This is deliberately based on plan actions after ``action_progress`` has been
    synchronized.  The snapshot is stored with the confirmed review so a later
    replan cannot rewrite the historical growth basis.
    """
    sync_action_progress_to_plans(report_obj)
    scoped_ids = {str(value).strip() for value in (target_job_ids or []) if str(value).strip()}
    total_count = 0
    done_count = 0
    plan_months: List[int] = []
    by_target: List[Dict[str, Any]] = []

    for plan in report_obj.get("plans_by_target") or []:
        if not isinstance(plan, dict):
            continue
        job_id = str(plan.get("job_id") or "").strip()
        if scoped_ids and job_id not in scoped_ids:
            continue
        next_month_plan = plan.get("next_month_plan")
        if not isinstance(next_month_plan, dict):
            continue
        try:
            plan_month = int(next_month_plan.get("plan_month") or plan.get("current_plan_month") or 1)
        except (TypeError, ValueError):
            plan_month = 1
        target_total = 0
        target_done = 0
        for item in next_month_plan.get("items") or []:
            if not isinstance(item, dict):
                continue
            for action in item.get("custom_actions") or []:
                if not isinstance(action, dict):
                    continue
                target_total += 1
                if bool(action.get("done")):
                    target_done += 1
        if target_total:
            plan_months.append(plan_month)
            total_count += target_total
            done_count += target_done
            by_target.append(
                {
                    "job_id": job_id,
                    "plan_month": plan_month,
                    "done_count": target_done,
                    "total_count": target_total,
                    "completion_rate": round(target_done / target_total, 4),
                }
            )

    return {
        "done_count": done_count,
        "total_count": total_count,
        "completion_rate": round(done_count / total_count, 4) if total_count else None,
        "has_completed_actions": done_count > 0,
        "plan_months": sorted(set(plan_months)),
        "by_target": by_target,
    }


def apply_plan_action_done(
    report_obj: Dict[str, Any],
    *,
    job_id: str,
    item_index: int | None = None,
    action_index: int | None = None,
    action_uid: str | None = None,
    done: bool,
    stamp: str | None = None,
) -> Dict[str, Any]:
    """在 report_obj 内更新行动项 done 状态，返回 {done, done_at, progress_key}。"""
    jid = str(job_id or "").strip()
    if not jid:
        raise PlanActionProgressError("job_id 无效")

    plan, _, act, resolved_item_index, resolved_action_index = locate_plan_action(
        report_obj,
        job_id=jid,
        item_index=item_index,
        action_index=action_index,
        action_uid=action_uid,
    )
    nmp = plan.get("next_month_plan") or {}
    plan_month = int(nmp.get("plan_month") or plan.get("current_plan_month") or 1)

    act["done"] = bool(done)
    done_at: str | None
    if done:
        done_at = stamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        act["done_at"] = done_at
    else:
        done_at = None
        act.pop("done_at", None)

    ensure_action_ids(report_obj)
    stable_key = str(act.get("action_uid") or "")
    progress_key = build_progress_key(jid, plan_month, resolved_item_index, resolved_action_index)
    progress_map = _ensure_progress_map(report_obj)
    entry = {"done": True, "done_at": done_at} if done else {"done": False}
    if stable_key:
        progress_map[stable_key] = entry
    if done:
        progress_map[progress_key] = entry
    else:
        progress_map[progress_key] = entry

    return {
        "done": act["done"],
        "done_at": done_at,
        "progress_key": progress_key,
        "action_uid": act.get("action_uid"),
        "item_index": resolved_item_index,
        "action_index": resolved_action_index,
    }


def locate_plan_action(
    report_obj: Dict[str, Any],
    *,
    job_id: str,
    item_index: int | None = None,
    action_index: int | None = None,
    action_uid: str | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], int, int]:
    ensure_action_ids(report_obj)
    jid = str(job_id or "").strip()
    plans = report_obj.get("plans_by_target") or []
    plan = next((p for p in plans if isinstance(p, dict) and str(p.get("job_id") or "").strip() == jid), None)
    if not plan:
        raise PlanActionProgressError("目标岗位计划不存在")
    items = ((plan.get("next_month_plan") or {}).get("items") or [])
    wanted_uid = str(action_uid or "").strip()
    if wanted_uid:
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for j, action in enumerate(item.get("custom_actions") or []):
                if isinstance(action, dict) and str(action.get("action_uid") or "") == wanted_uid:
                    return plan, item, action, i, j
        raise PlanActionProgressError("行动项不存在或已被删除")
    if item_index is None or action_index is None or item_index < 0 or item_index >= len(items):
        raise PlanActionProgressError("计划项不存在")
    item = items[item_index]
    actions = item.get("custom_actions") if isinstance(item, dict) else None
    if not isinstance(actions, list) or action_index < 0 or action_index >= len(actions):
        raise PlanActionProgressError("行动项不存在")
    action = actions[action_index]
    if not isinstance(action, dict):
        raise PlanActionProgressError("行动项无效")
    return plan, item, action, item_index, action_index


def find_plan_action(
    report_obj: Dict[str, Any],
    *,
    job_id: str,
    item_index: int,
    action_index: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """只读定位 plan 与 action，供测试与校验。"""
    plan, _, action, _, _ = locate_plan_action(
        report_obj, job_id=job_id, item_index=item_index, action_index=action_index
    )
    return plan, action
