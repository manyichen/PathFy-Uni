"""下月计划行动项完成状态（写回 report_json）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple


class PlanActionProgressError(ValueError):
    """业务校验失败（由 services 转为 ReportServiceError）。"""


def build_progress_key(
    job_id: str,
    plan_month: int,
    item_index: int,
    action_index: int,
) -> str:
    return f"{str(job_id or '').strip()}|{int(plan_month)}|{int(item_index)}|{int(action_index)}"


def _ensure_progress_map(report_obj: Dict[str, Any]) -> Dict[str, Any]:
    raw = report_obj.get("action_progress")
    if not isinstance(raw, dict):
        raw = {}
        report_obj["action_progress"] = raw
    return raw


def sync_action_progress_to_plans(report_obj: Dict[str, Any]) -> None:
    """将 action_progress 索引同步到 plans_by_target 内 custom_actions.done。"""
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
                key = build_progress_key(jid, plan_month, item_index, action_index)
                entry = progress.get(key)
                if not isinstance(entry, dict):
                    continue
                if entry.get("done"):
                    act["done"] = True
                    if entry.get("done_at"):
                        act["done_at"] = str(entry["done_at"])
                elif "done" in entry and not entry.get("done"):
                    act["done"] = False
                    act.pop("done_at", None)


def apply_plan_action_done(
    report_obj: Dict[str, Any],
    *,
    job_id: str,
    item_index: int,
    action_index: int,
    done: bool,
    stamp: str | None = None,
) -> Dict[str, Any]:
    """在 report_obj 内更新行动项 done 状态，返回 {done, done_at, progress_key}。"""
    jid = str(job_id or "").strip()
    if not jid:
        raise PlanActionProgressError("job_id 无效")

    plans = report_obj.get("plans_by_target")
    if not isinstance(plans, list):
        raise PlanActionProgressError("目标岗位计划不存在")

    plan = next(
        (p for p in plans if isinstance(p, dict) and str(p.get("job_id") or "").strip() == jid),
        None,
    )
    if not plan:
        raise PlanActionProgressError("目标岗位计划不存在")

    nmp = plan.get("next_month_plan")
    if not isinstance(nmp, dict):
        raise PlanActionProgressError("下月计划不存在")

    plan_month = int(nmp.get("plan_month") or plan.get("current_plan_month") or 1)

    items = nmp.get("items")
    if not isinstance(items, list) or item_index < 0 or item_index >= len(items):
        raise PlanActionProgressError("计划项不存在")

    item = items[item_index]
    if not isinstance(item, dict):
        raise PlanActionProgressError("计划项无效")

    actions = item.get("custom_actions")
    if not isinstance(actions, list) or action_index < 0 or action_index >= len(actions):
        raise PlanActionProgressError("行动项不存在")

    act = actions[action_index]
    if not isinstance(act, dict):
        raise PlanActionProgressError("行动项无效")

    act["done"] = bool(done)
    done_at: str | None
    if done:
        done_at = stamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        act["done_at"] = done_at
    else:
        done_at = None
        act.pop("done_at", None)

    progress_key = build_progress_key(jid, plan_month, item_index, action_index)
    progress_map = _ensure_progress_map(report_obj)
    if done:
        progress_map[progress_key] = {"done": True, "done_at": done_at}
    else:
        progress_map[progress_key] = {"done": False}

    return {"done": act["done"], "done_at": done_at, "progress_key": progress_key}


def find_plan_action(
    report_obj: Dict[str, Any],
    *,
    job_id: str,
    item_index: int,
    action_index: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """只读定位 plan 与 action，供测试与校验。"""
    jid = str(job_id or "").strip()
    plans = report_obj.get("plans_by_target") or []
    plan = next(
        (p for p in plans if isinstance(p, dict) and str(p.get("job_id") or "").strip() == jid),
        None,
    )
    if not plan:
        raise PlanActionProgressError("目标岗位计划不存在")
    items = (plan.get("next_month_plan") or {}).get("items") or []
    if item_index < 0 or item_index >= len(items):
        raise PlanActionProgressError("计划项不存在")
    actions = (items[item_index] or {}).get("custom_actions") or []
    if action_index < 0 or action_index >= len(actions):
        raise PlanActionProgressError("行动项不存在")
    act = actions[action_index]
    if not isinstance(act, dict):
        raise PlanActionProgressError("行动项无效")
    return plan, act
