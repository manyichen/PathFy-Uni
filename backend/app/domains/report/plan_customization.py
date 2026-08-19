"""分岗三阶段计划：DeepSeek batch 生成岗位定制行动。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from flask import current_app
from app.domains.settings.service import settings_view

from app.domains.report.constants import DIM_LABELS, sanitize_plan_item_user_text, sanitize_user_facing_text
from app.domains.report.llm import _call_openai_compatible
from app.domains.report.utils import truthy
from app.infrastructure.llm import strip_json_fence
from app.infrastructure.privacy import redact_payload

_PHASE_KEYS = ("early", "mid", "late")


def _brief_phase_items(items: List[Dict[str, Any]], *, job_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in (items or [])[:2]:
        if not isinstance(it, dict):
            continue
        refs = it.get("learning_path_refs") or []
        dimension = str(it.get("focus_dimension") or "")
        out.append(
            {
                "focus_dimension": dimension,
                "focus_label": it.get("focus_label"),
                "milestone": it.get("milestone"),
                "allowed_fact_refs": [
                    f"profile:{dimension}",
                    f"job:{job_id}:{dimension}",
                    f"gap:{job_id}:{dimension}",
                ] if dimension else [],
                "grounded_resource_ids": [
                    str(r.get("id") or "") for r in refs if isinstance(r, dict) and r.get("id")
                ],
                "grounded_resource_labels": [
                    str(r.get("label") or "") for r in refs if isinstance(r, dict) and r.get("label")
                ],
            }
        )
    return out


def _brief_plan_for_llm(plan: Dict[str, Any], insight: Dict[str, Any] | None) -> Dict[str, Any]:
    phases = plan.get("phases") or {}
    rec = plan.get("recommendations") or {}
    lr_names = [
        str(x.get("resource_name") or "")
        for x in (rec.get("learning_resources") or [])[:6]
        if x.get("resource_name")
    ]
    cp_names = [
        str(x.get("competition_name") or "")
        for x in (rec.get("competitions") or [])[:3]
        if x.get("competition_name")
    ]
    mp = (insight or {}).get("match_preview") or {}
    job_id = str(plan.get("job_id") or "")
    current_month = int(plan.get("current_plan_month") or 1)
    current_phase = "early" if current_month <= 3 else "mid" if current_month <= 6 else "late"
    return {
        "job_id": job_id,
        "display_title": plan.get("display_title"),
        "company": plan.get("company"),
        "location": plan.get("location"),
        "job_title_name": plan.get("job_title_name"),
        "match_score": plan.get("match_score"),
        "top_gap_labels": plan.get("top_gap_labels")
        or [DIM_LABELS.get(d, d) for d in (plan.get("top_gaps") or [])],
        "dimension_gaps": plan.get("dimension_gaps") or mp.get("dimension_gaps") or {},
        "grounded_resources": lr_names + cp_names,
        "current_phase": current_phase,
        "phases": {
            k: {
                "label": (phases.get(k) or {}).get("label"),
                "period": (phases.get(k) or {}).get("period"),
                "items": _brief_phase_items((phases.get(k) or {}).get("items") or [], job_id=job_id),
            }
            for k in (current_phase,)
        },
    }


def apply_custom_plan_batch(
    plans_by_target: List[Dict[str, Any]],
    parsed_items: List[Dict[str, Any]],
) -> int:
    """将 LLM 输出合并进 plans_by_target，返回成功更新的岗位数。"""
    if not plans_by_target or not parsed_items:
        return 0
    plan_index = {
        str(p.get("job_id") or "").strip(): p for p in plans_by_target if isinstance(p, dict)
    }
    updated = 0
    for raw in parsed_items:
        if not isinstance(raw, dict):
            continue
        jid = str(raw.get("job_id") or "").strip()
        plan = plan_index.get(jid)
        if not plan:
            continue
        phases_in = raw.get("phases") if isinstance(raw.get("phases"), dict) else {}
        plan_phases = plan.get("phases") if isinstance(plan.get("phases"), dict) else {}
        touched = False
        for ph_key in _PHASE_KEYS:
            ph_in = phases_in.get(ph_key) if isinstance(phases_in.get(ph_key), dict) else {}
            ph_out = plan_phases.get(ph_key) if isinstance(plan_phases.get(ph_key), dict) else {}
            if not ph_out:
                continue
            liner = str(ph_in.get("line_one_liner") or "").strip()
            if liner:
                ph_out["line_one_liner"] = liner[:160]
                touched = True
            items_in = ph_in.get("items") if isinstance(ph_in.get("items"), list) else []
            plan_items = ph_out.get("items") if isinstance(ph_out.get("items"), list) else []
            by_dim = {
                str(it.get("focus_dimension") or ""): it
                for it in plan_items
                if isinstance(it, dict) and it.get("focus_dimension")
            }
            allowed_ids = {
                str(r.get("id") or "")
                for it in plan_items
                if isinstance(it, dict)
                for r in (it.get("learning_path_refs") or [])
                if isinstance(r, dict) and r.get("id")
            }
            for it_in in items_in:
                if not isinstance(it_in, dict):
                    continue
                dim = str(it_in.get("focus_dimension") or "").strip()
                target = by_dim.get(dim)
                if not target:
                    continue
                ms = str(it_in.get("milestone") or "").strip()
                if ms:
                    target["milestone"] = sanitize_user_facing_text(ms)[:200]
                    touched = True
                actions: List[Dict[str, Any]] = []
                for act in it_in.get("custom_actions") or []:
                    if not isinstance(act, dict):
                        continue
                    text = str(act.get("text") or "").strip()
                    if not text:
                        continue
                    kind = str(act.get("kind") or "practice").strip().lower()
                    if kind not in ("learn", "practice", "deliverable"):
                        kind = "practice"
                    normalized: Dict[str, Any] = {
                        "kind": kind,
                        "text": sanitize_user_facing_text(text)[:150],
                    }
                    deliverable = sanitize_user_facing_text(str(act.get("deliverable") or "").strip())[:180]
                    deadline = str(act.get("deadline") or "").strip()[:10]
                    acceptance_rule = sanitize_user_facing_text(str(act.get("acceptance_rule") or "").strip())[:220]
                    try:
                        effort_hours = max(0.5, min(20.0, float(act.get("effort_hours"))))
                    except (TypeError, ValueError):
                        effort_hours = None
                    evidence_type = str(act.get("evidence_type") or "other").strip().lower()
                    if evidence_type not in ("project", "certificate", "feedback", "event", "other"):
                        evidence_type = "other"
                    allowed_fact_refs = {
                        f"profile:{dim}",
                        f"job:{jid}:{dim}",
                        f"gap:{jid}:{dim}",
                    }
                    fact_refs = [
                        str(value)
                        for value in act.get("fact_refs") or []
                        if str(value) in allowed_fact_refs
                    ]
                    resource_refs = [
                        str(value)
                        for value in act.get("resource_refs") or []
                        if str(value) in allowed_ids
                    ]
                    if deliverable:
                        normalized["deliverable"] = deliverable
                    if len(deadline) == 10 and deadline[4:5] == "-" and deadline[7:8] == "-":
                        normalized["deadline"] = deadline
                    if effort_hours is not None:
                        normalized["effort_hours"] = effort_hours
                    if acceptance_rule:
                        normalized["acceptance_rule"] = acceptance_rule
                    normalized["evidence_type"] = evidence_type
                    normalized["linked_dimensions"] = [dim] if dim else []
                    normalized["fact_refs"] = fact_refs
                    normalized["resource_refs"] = resource_refs
                    actions.append(normalized)
                if actions:
                    target["custom_actions"] = actions[:4]
                    sanitize_plan_item_user_text(target)
                    touched = True
                use_ids = [
                    str(x).strip()
                    for x in (it_in.get("use_resource_ids") or [])
                    if str(x).strip()
                ]
                if use_ids and allowed_ids:
                    keep = set(use_ids).intersection(allowed_ids)
                    refs = target.get("learning_path_refs") or []
                    if keep and isinstance(refs, list):
                        target["learning_path_refs"] = [
                            r for r in refs if isinstance(r, dict) and str(r.get("id") or "") in keep
                        ]
                        touched = True
        if touched:
            updated += 1
    return updated


def build_custom_plan_actions_batch(
    plans_by_target: List[Dict[str, Any]],
    target_insights: List[Dict[str, Any]],
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    一次 DeepSeek 为各目标岗位生成定制行动，并写入 plans_by_target（原地修改）。
    """
    meta: Dict[str, Any] = {"ok": False, "reason": "skipped", "mode": "batch", "updated": 0}
    if not plans_by_target:
        meta["reason"] = "empty_plans"
        return meta
    if not use_llm:
        meta["reason"] = "use_llm_false"
        return meta

    cfg = settings_view(base=current_app.config)
    if not truthy(cfg.get("CAREER_ENABLE_PLAN_CUSTOMIZATION", True)):
        meta["reason"] = "CAREER_ENABLE_PLAN_CUSTOMIZATION disabled"
        return meta
    if not truthy(cfg.get("CAREER_ENABLE_RECOMMENDATION_LLM", True)):
        meta["reason"] = "CAREER_ENABLE_RECOMMENDATION_LLM disabled"
        return meta

    api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        meta["reason"] = "missing DEEPSEEK_API_KEY"
        return meta

    insight_by_id = {
        str(t.get("id") or "").strip(): t for t in target_insights if isinstance(t, dict)
    }
    brief_plans = [
        _brief_plan_for_llm(p, insight_by_id.get(str(p.get("job_id") or "").strip()))
        for p in plans_by_target[:5]
        if isinstance(p, dict)
    ]
    payload = {
        "task": "customize_career_plan_actions_batch",
        "plans": brief_plans,
        "rules": [
            "每个 job_id 必须输出一条",
            "每个岗位只输出 current_phase 对应阶段，不要扩写其他阶段",
            "custom_actions 必须结合该公司/岗位/缺口，与同 title 其他公司区分",
            "禁止编造 grounded_resources 以外的课程或竞赛名称",
            "milestone 可验收、含时间或产出物与验收标准",
            "每条 custom_actions 含 learn/practice/deliverable 三类至少各1条（共3-4条），text<=80字",
            "行动须写清「做完后如何提升匹配度/成果/短板收敛」",
            "禁止英文 code、匹配分数、「拉动完成率/贴合度」等开发术语，用自然中文",
            "use_resource_ids 只能从该维 grounded_resource_ids 中选，可不选",
            "每条行动必须填写 deliverable、deadline、effort_hours、acceptance_rule、evidence_type",
            "fact_refs 只能从该维 allowed_fact_refs 中选，resource_refs 只能从 grounded_resource_ids 中选",
            "全部行动总投入应与一个月内可完成的学习量一致，不得承诺就业结果",
            "只输出 JSON 对象，禁止 markdown",
        ],
        "today": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "output_schema": {
            "items": [
                {
                    "job_id": "string",
                    "phases": {
                        "early|mid|late（仅 current_phase）": {
                            "line_one_liner": "string 30-50字",
                            "items": [
                                {
                                    "focus_dimension": "string",
                                    "milestone": "string",
                                    "custom_actions": [{
                                        "kind": "learn|practice|deliverable",
                                        "text": "string",
                                        "deliverable": "string",
                                        "deadline": "YYYY-MM-DD",
                                        "effort_hours": 4,
                                        "acceptance_rule": "string",
                                        "evidence_type": "project|certificate|feedback|event|other",
                                        "linked_dimensions": ["cap_req_practice"],
                                        "fact_refs": ["string from allowed_fact_refs"],
                                        "resource_refs": ["string from grounded_resource_ids"],
                                    }],
                                    "use_resource_ids": ["string"],
                                }
                            ],
                        },
                    },
                }
            ]
        },
    }
    model = str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-v4-pro")
    timeout = min(45.0, float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 45.0))
    try:
        text = _call_openai_compatible(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model=model,
            timeout=timeout,
            system_prompt="你是职业规划教练。仅输出 JSON 对象。",
            user_prompt=json.dumps(redact_payload(payload), ensure_ascii=False),
            temperature=0.4,
        )
        parsed = json.loads(strip_json_fence(text))
        items = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(items, list):
            return {**meta, "ok": False, "reason": "llm_items_missing", "model": model}

        updated = apply_custom_plan_batch(plans_by_target, items)
        for p in plans_by_target:
            if isinstance(p, dict) and updated:
                p["customization"] = {
                    "provider": "deepseek",
                    "model": model,
                    "mode": "batch",
                    "ok": True,
                }
        return {
            "ok": updated > 0,
            "updated": updated,
            "provider": "deepseek",
            "model": model,
            "mode": "batch",
            "job_count": len(brief_plans),
        }
    except Exception as exc:  # noqa: BLE001
        return {**meta, "ok": False, "reason": str(exc), "model": model, "fallback": "skeleton"}
