"""复盘与自动重规划。"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple

from flask import current_app
from openai import OpenAI

from app.infrastructure.llm import strip_json_fence
from app.infrastructure.privacy import redact_payload, redact_text
from app.domains.report.constants import DIM_LABELS, SHORT_TERM_ACTIONS, sanitize_plan_item_user_text, sanitize_user_facing_text
from app.domains.report.growth import (
    _execution_hints_for_replan_action,
    _review_point_progress,
)
from app.domains.report.llm import _call_openai_compatible
from app.domains.report.recommendations import pick_replan_resource_hints
from app.domains.report.replan_by_target import (
    apply_replan_after_review,
    phase_key_for_plan_month,
)
from app.domains.report.utils import parse_metric_target, to_float


def _evaluate_review_metrics(
    expected_metrics: List[Dict[str, Any]],
    submitted_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    failed_codes: List[str] = []
    submitted = submitted_metrics or {}
    for m in expected_metrics:
        code = str(m.get("code") or "").strip()
        if not code:
            continue
        target = parse_metric_target(str(m.get("target") or "0"))
        actual = to_float(submitted.get(code), float("nan"))
        if actual != actual:  # nan
            passed = False
            actual = 0.0
            missing = True
        else:
            passed = actual >= target
            missing = False
        if not passed:
            failed_codes.append(code)
        rows.append(
            {
                "code": code,
                "label": m.get("label") or code,
                "cycle": m.get("cycle") or "",
                "target_raw": m.get("target") or "",
                "target_value": round(target, 4),
                "actual_value": round(actual, 4),
                "passed": passed,
                "missing": missing,
            }
        )
    pass_rate = (len(rows) - len(failed_codes)) / len(rows) if rows else 0.0
    return {
        "rows": rows,
        "failed_codes": failed_codes,
        "pass_rate": round(pass_rate, 4),
        "all_passed": len(failed_codes) == 0 and len(rows) > 0,
    }


def _uniq_floats_keep_order(values: List[float]) -> List[float]:
    seen = set()
    out: List[float] = []
    for x in values:
        key = round(float(x), 4)
        if key in seen:
            continue
        seen.add(key)
        out.append(float(x))
    return out


def _numeric_hints_from_review_text(review_text: str) -> Dict[str, Any]:
    """从复盘原文里抓数字线索，供 LLM 对齐，减少凭空凑整。"""
    text = str(review_text or "")
    pcts: List[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text):
        pcts.append(to_float(m.group(1), 0.0))
    points: List[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*分", text):
        points.append(to_float(m.group(1), 0.0))
    for m in re.finditer(r"(?:提高|提升|增加|上涨|多了|少|降低|减少)\s*(\d+(?:\.\d+)?)\s*分", text):
        points.append(to_float(m.group(1), 0.0))
    item_counts: List[int] = []
    for m in re.finditer(r"(\d+)\s*(?:项|个|条|件)(?:成果|作品|产出|项目)?", text):
        item_counts.append(int(to_float(m.group(1), 0.0)))
    # 「八成」「七成五」等口语
    cn_frac = {
        "十成": 100.0,
        "九成": 90.0,
        "八成": 80.0,
        "七成": 70.0,
        "六成": 60.0,
        "五成": 50.0,
        "四成": 40.0,
        "三成": 30.0,
        "两成": 20.0,
        "一成": 10.0,
    }
    for k, v in cn_frac.items():
        if k in text:
            pcts.append(v)
    return {
        "percentages_found": _uniq_floats_keep_order(pcts)[:12],
        "match_points_found": _uniq_floats_keep_order(points)[:8],
        "quantity_phrases_found": list(dict.fromkeys(item_counts))[:8],
    }


def _heuristic_extract_metrics_from_text(review_text: str) -> Dict[str, float]:
    text = str(review_text or "").strip()

    def pick(patterns: List[str], default: float = 0.0) -> float:
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return to_float(m.group(1), default)
        return default

    return {
        "dim_gap_reduction": pick([r"(?:缺口收敛率|能力缺口).*?(-?\d+(?:\.\d+)?)\s*%?"], 0.0),
        "project_completion": pick([r"(?:项目完成率|任务完成率|完成率).*?(-?\d+(?:\.\d+)?)\s*%?"], 0.0),
        "match_score_change": pick([r"(?:匹配度(?:变化)?|匹配分(?:变化)?).*?(-?\d+(?:\.\d+)?)\s*分?"], 0.0),
        "delivery_output": pick([r"(?:成果数量|可展示成果).*?(-?\d+(?:\.\d+)?)\s*(?:项|个)?"], 0.0),
    }


def _llm_extract_metrics_from_text(
    *,
    report_obj: Dict[str, Any],
    review_text: str,
    review_cycle: str,
) -> Dict[str, Any]:
    cfg = current_app.config
    api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        return {
            "ok": False,
            "error": "missing DEEPSEEK_API_KEY",
            "metrics": _heuristic_extract_metrics_from_text(review_text),
            "source": "heuristic_fallback",
        }

    eval_metrics = (((report_obj.get("evaluation") or {}).get("metrics")) or [])
    if not isinstance(eval_metrics, list):
        eval_metrics = []
    metrics_brief = []
    for item in eval_metrics:
        if isinstance(item, dict):
            metrics_brief.append(
                {
                    "code": item.get("code"),
                    "label": item.get("label"),
                    "target": item.get("target"),
                    "cycle": item.get("cycle"),
                }
            )

    numeric_hints = _numeric_hints_from_review_text(review_text)
    safe_review_text = redact_text(
        review_text,
        max_chars=int(cfg.get("LLM_MAX_TEXT_CHARS") or 4000),
    )
    prompt_obj = {
        "task": "extract_review_metrics_from_natural_language",
        "review_cycle": review_cycle,
        "review_text": safe_review_text,
        "numeric_hints_from_text": numeric_hints,
        "metrics_schema": metrics_brief,
        "rules": [
            "四个数字必须尽量贴合正文与 numeric_hints；正文没有写到的不要拍脑袋凑成 5/10/15/20 这种整齐数。",
            "dim_gap_reduction、project_completion 用百分比，尽量保留 1 位小数（如 11.4、76.8）；只有正文明确整数时才用整数。",
            "match_score_change 表示相对上一周期的匹配分变化，可为负；尽量 1 位小数。",
            "delivery_output 为成果个数，非负整数；可参考 quantity_phrases_found；能数出几条写几条，数不出则写 0。",
            "若信息严重不足，宁可给偏低的小数也不要默认 80、50、10 这类常见凑数。",
        ],
        "required_output": {
            "dim_gap_reduction": "number 百分比",
            "project_completion": "number 百分比",
            "match_score_change": "number 分值变化, 可为负数",
            "delivery_output": "number 本周期新增成果项数",
            "summary": "string 一句话总结<=60字",
        },
    }
    user_prompt = (
        "你是职业发展评估助手。请从自然语言复盘中提取关键指标并量化。"
        "仅输出 JSON 对象，禁止 markdown。\n"
        f"{json.dumps(redact_payload(prompt_obj), ensure_ascii=False)}"
    )
    model = str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat")
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    extract_temp = float(cfg.get("CAREER_REVIEW_EXTRACT_TEMPERATURE") or 0.55)
    try:
        text = _call_openai_compatible(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model=model,
            timeout=timeout,
            system_prompt=(
                "你将复盘文本映射为可评估指标，只输出 JSON。"
                "禁止为省事输出全是 5 的倍数；估计要依据正文，可用一位小数；"
                "若正文出现百分比或分数，必须与之一致或能解释的差异。"
            ),
            user_prompt=user_prompt,
            temperature=extract_temp,
        )
        parsed = json.loads(strip_json_fence(text))
        if not isinstance(parsed, dict):
            raise RuntimeError("llm_root_not_object")
        metrics = {
            "dim_gap_reduction": to_float(parsed.get("dim_gap_reduction"), 0.0),
            "project_completion": to_float(parsed.get("project_completion"), 0.0),
            "match_score_change": to_float(parsed.get("match_score_change"), 0.0),
            "delivery_output": to_float(parsed.get("delivery_output"), 0.0),
        }
        metrics["delivery_output"] = max(0.0, round(metrics.get("delivery_output", 0.0)))
        for k in ("dim_gap_reduction", "project_completion", "match_score_change"):
            metrics[k] = round(to_float(metrics.get(k), 0.0), 2)
        summary = str(parsed.get("summary") or "").strip()[:120]
        return {
            "ok": True,
            "metrics": metrics,
            "summary": summary,
            "model": model,
            "source": "deepseek",
            "raw": strip_json_fence(text)[:1200],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "metrics": _heuristic_extract_metrics_from_text(review_text),
            "source": "heuristic_fallback",
        }


def _build_auto_adjustment(
    report_obj: Dict[str, Any],
    failed_codes: List[str],
    *,
    replan_mode: str = "light",
) -> Dict[str, Any]:
    targets = report_obj.get("targets") or []
    gap_counter: Dict[str, float] = defaultdict(float)
    for t in targets:
        gaps = ((t or {}).get("match_preview") or {}).get("dimension_gaps") or {}
        for k, v in gaps.items():
            gap_counter[str(k)] += to_float(v, 0.0)
    top_dims = sorted(gap_counter.keys(), key=lambda x: gap_counter[x], reverse=True)[:2]
    if not top_dims:
        top_dims = ["cap_req_growth", "cap_req_practice"]

    actions: List[str] = []
    for dim in top_dims:
        actions.extend(SHORT_TERM_ACTIONS.get(dim, [])[:1])
    if not actions:
        actions = ["增加每周一次针对薄弱能力的专项练习并记录结果"]

    labels = [DIM_LABELS.get(x, x) for x in top_dims]
    llm_by_job: List[Dict[str, Any]] = []
    llm_meta: Dict[str, Any] = {
        "enabled": bool(current_app.config.get("CAREER_ENABLE_REPLAN_LLM", True)),
        "used": False,
        "error": None,
    }

    if replan_mode in ("strong", "light"):
        llm_payload = _llm_auto_replan_payload(
            report_obj,
            failed_codes,
            top_dims,
            actions[:3],
            replan_mode=replan_mode,
        )
        if llm_payload.get("ok"):
            llm_data = llm_payload.get("data") or {}
            llm_dims = [str(x).strip() for x in (llm_data.get("focus_dimensions") or []) if str(x).strip()]
            llm_labels = [str(x).strip() for x in (llm_data.get("focus_labels") or []) if str(x).strip()]
            llm_actions = [str(x).strip() for x in (llm_data.get("extra_actions") or []) if str(x).strip()]
            if llm_dims:
                top_dims = llm_dims[:2]
            if llm_labels:
                labels = llm_labels[:2]
            else:
                labels = [DIM_LABELS.get(x, x) for x in top_dims]
            if llm_actions:
                actions = llm_actions[:3]
            else:
                actions = actions[:3]
            llm_by_job = llm_data.get("by_job") if isinstance(llm_data.get("by_job"), list) else []
            llm_meta = {
                "enabled": True,
                "used": True,
                "provider": llm_payload.get("provider"),
                "model": llm_payload.get("model"),
                "raw": llm_payload.get("raw"),
            }
        else:
            actions = actions[:3]
            llm_meta["error"] = llm_payload.get("error") or "llm_unavailable"
    else:
        actions = actions[:1]

    graph_hints = pick_replan_resource_hints(report_obj, top_dims)
    if graph_hints and replan_mode != "continue":
        actions = graph_hints[:1] + [a for a in actions if a not in graph_hints][:3]

    reason_map = {
        "continue": "本月评估达标，按分岗阶段计划延续下月任务",
        "light": "本月部分指标未达标，已微调下月任务",
        "strong": "连续未达标，已加强下月任务安排",
    }
    return {
        "triggered": True,
        "reason": reason_map.get(replan_mode, "本月复盘后更新下月安排"),
        "replan_mode": replan_mode,
        "failed_metric_codes": failed_codes,
        "focus_dimensions": top_dims,
        "focus_labels": labels,
        "extra_actions": actions[:3],
        "by_job": llm_by_job,
        "llm_meta": llm_meta,
    }


def _llm_auto_replan_payload(
    report_obj: Dict[str, Any],
    failed_codes: List[str],
    fallback_dims: List[str],
    fallback_actions: List[str],
    *,
    replan_mode: str = "light",
) -> Dict[str, Any]:
    if not bool(current_app.config.get("CAREER_ENABLE_REPLAN_LLM", True)):
        return {"ok": False, "error": "CAREER_ENABLE_REPLAN_LLM disabled"}

    cfg = current_app.config
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    model = str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat")

    eval_block = (report_obj.get("evaluation") or {})
    metric_defs = eval_block.get("metrics") if isinstance(eval_block, dict) else []
    if not isinstance(metric_defs, list):
        metric_defs = []
    metric_map = {str(m.get("code") or ""): m for m in metric_defs if isinstance(m, dict)}
    failed_metrics = []
    for code in failed_codes:
        m = metric_map.get(code) or {}
        failed_metrics.append(
            {
                "code": code,
                "label": m.get("label") or code,
                "target": m.get("target") or "",
            }
        )

    target_top = []
    for t in (report_obj.get("targets") or [])[:5]:
        if not isinstance(t, dict):
            continue
        gaps = (t.get("match_preview") or {}).get("dimension_gaps") or {}
        gap_items = sorted(
            [(k, float(v or 0)) for k, v in gaps.items() if k in DIM_LABELS],
            key=lambda x: x[1],
            reverse=True,
        )[:3]
        target_top.append(
            {
                "title": t.get("title"),
                "match_score": (t.get("match_preview") or {}).get("match_score"),
                "top_gaps": [{"dim": k, "label": DIM_LABELS.get(k, k), "value": v} for k, v in gap_items],
            }
        )

    grounded: List[Dict[str, str]] = []
    rec = report_obj.get("recommendations") or {}
    if rec.get("enabled"):
        for block in (rec.get("by_target") or [])[:2]:
            if not isinstance(block, dict):
                continue
            for lr in (block.get("learning_resources") or [])[:3]:
                grounded.append(
                    {
                        "resource_id": str(lr.get("resource_id") or ""),
                        "name": str(lr.get("resource_name") or ""),
                    }
                )
            for cp in (block.get("competitions") or [])[:2]:
                grounded.append(
                    {
                        "competition_id": str(cp.get("competition_id") or ""),
                        "name": str(cp.get("competition_name") or ""),
                    }
                )

    plan_brief = []
    for p in (report_obj.get("plans_by_target") or [])[:5]:
        if not isinstance(p, dict):
            continue
        pm = int(p.get("current_plan_month") or 1) + 1
        pk = phase_key_for_plan_month(pm)
        items = ((p.get("phases") or {}).get(pk) or {}).get("items") or []
        plan_brief.append(
            {
                "job_id": p.get("job_id"),
                "display_title": p.get("display_title"),
                "next_plan_month": pm,
                "phase_key": pk,
                "phase_items": [
                    {
                        "focus_dimension": it.get("focus_dimension"),
                        "focus_label": it.get("focus_label"),
                        "milestone": it.get("milestone"),
                    }
                    for it in items[:3]
                    if isinstance(it, dict)
                ],
            }
        )

    lr = eval_block.get("latest_review") if isinstance(eval_block, dict) else {}
    submitted_snapshot = (lr.get("submitted_metrics") or {}) if isinstance(lr, dict) else {}

    user_payload = {
        "task": "auto_replan_by_target",
        "replan_mode": replan_mode,
        "failed_metrics": failed_metrics,
        "submitted_metrics_snapshot": submitted_snapshot,
        "targets": target_top,
        "plans": plan_brief,
        "grounded_resources": grounded,
        "rules": [
            "每个 job_id 的 items 含 1-2 个 focus_dimension",
            "每项 milestone 可验收（含时间/产出物/验收标准）",
            "每项 custom_actions 3-4 条，kind 分别为 learn/practice/deliverable，text<=80字",
            "动作须具体可执行，写清「做完后有什么可展示成果」",
            "禁止出现英文指标 code、匹配分数、「拉动完成率/贴合度」等开发术语",
            "优先引用 grounded_resources 名称，禁止编造课程/竞赛",
            "只输出 JSON",
        ],
        "fallback": {
            "focus_dimensions": fallback_dims,
            "focus_labels": [DIM_LABELS.get(x, x) for x in fallback_dims],
            "extra_actions": fallback_actions,
        },
        "output_schema": {
            "focus_dimensions": ["cap_req_*"],
            "focus_labels": ["中文"],
            "extra_actions": ["全局兜底动作"],
            "by_job": [
                {
                    "job_id": "string",
                    "items": [
                        {
                            "focus_dimension": "cap_req_*",
                            "milestone": "可验收里程碑（含产出物）",
                            "custom_actions": [{"kind": "learn|practice|deliverable", "text": "具体动作"}],
                        }
                    ],
                }
            ],
        },
    }
    system_prompt = (
        "你是职业发展重规划教练。按 job_id 为每个目标岗位输出下月可执行任务，"
        "必须与 plans 中对应阶段的 phase_key 一致（early=1-3月,mid=4-9月,late=10-12月）。"
        "只输出 JSON。extra_actions 为全局兜底；by_job 每项 1-2 个 focus 任务，"
        "custom_actions 须具体、可勾选，用教练口吻描述「做什么、产出什么」；"
        "禁止英文指标 code、匹配分数、「拉动完成率」等术语；"
        "优先引用 grounded_resources 名称，禁止编造课程/竞赛。"
    )
    user_prompt = json.dumps(redact_payload(user_payload), ensure_ascii=False)

    try:
        api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
        if not api_key:
            return {"ok": False, "error": "missing DEEPSEEK_API_KEY"}
        text = _call_openai_compatible(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model=model,
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return _parse_replan_json(text, provider="deepseek", model=model)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _parse_replan_json(text: str, *, provider: str, model: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        obj = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"json_parse_error:{exc}"}
    if not isinstance(obj, dict):
        return {"ok": False, "error": "llm_root_not_object"}
    dims = [str(x).strip() for x in (obj.get("focus_dimensions") or []) if str(x).strip()]
    labels = [str(x).strip() for x in (obj.get("focus_labels") or []) if str(x).strip()]
    actions = [str(x).strip() for x in (obj.get("extra_actions") or []) if str(x).strip()]
    by_job_raw = obj.get("by_job") if isinstance(obj.get("by_job"), list) else []
    by_job: List[Dict[str, Any]] = []
    for block in by_job_raw:
        if not isinstance(block, dict):
            continue
        jid = str(block.get("job_id") or "").strip()
        if not jid:
            continue
        items_in = block.get("items") if isinstance(block.get("items"), list) else []
        items_out: List[Dict[str, Any]] = []
        for it in items_in:
            if not isinstance(it, dict):
                continue
            dim = str(it.get("focus_dimension") or "").strip()
            if not dim:
                continue
            row_item: Dict[str, Any] = {
                "focus_dimension": dim,
                "milestone": sanitize_user_facing_text(str(it.get("milestone") or ""))[:200],
                "custom_actions": [
                    {
                        "kind": str(a.get("kind") or "practice"),
                        "text": sanitize_user_facing_text(str(a.get("text") or ""))[:150],
                    }
                    for a in (it.get("custom_actions") or [])
                    if isinstance(a, dict) and str(a.get("text") or "").strip()
                ][:4],
            }
            sanitize_plan_item_user_text(row_item)
            items_out.append(row_item)
        if items_out:
            by_job.append({"job_id": jid, "items": items_out})
    if not dims and not by_job:
        return {"ok": False, "error": "llm_missing_required_fields"}
    if not actions and not by_job:
        return {"ok": False, "error": "llm_missing_actions"}
    return {
        "ok": True,
        "provider": provider,
        "model": model,
        "data": {
            "focus_dimensions": dims[:2] if dims else [],
            "focus_labels": labels[:2] if labels else [],
            "extra_actions": actions[:3],
            "by_job": by_job,
        },
        "raw": raw[:1200],
    }


def _apply_auto_adjustment_to_report(
    report_obj: Dict[str, Any],
    adjust_detail: Dict[str, Any],
    *,
    stamp: str,
    review_anchor_month: float | None = None,
    replan_mode: str = "light",
    metric_eval: Dict[str, Any] | None = None,
) -> None:
    if not adjust_detail.get("triggered"):
        return
    actions = [str(x).strip() for x in (adjust_detail.get("extra_actions") or []) if str(x).strip()]
    focus_dims = [str(x).strip() for x in (adjust_detail.get("focus_dimensions") or []) if str(x).strip()]
    focus_labels = [str(x).strip() for x in (adjust_detail.get("focus_labels") or []) if str(x).strip()]

    anchor = float(review_anchor_month if review_anchor_month is not None else 1.0)
    apply_replan_after_review(
        report_obj,
        adjust_detail,
        stamp=stamp,
        review_anchor_month=anchor,
        replan_mode=str(adjust_detail.get("replan_mode") or replan_mode),
        metric_eval=metric_eval or {},
    )

    if not actions:
        return

    growth_plan = report_obj.get("growth_plan")
    if not isinstance(growth_plan, dict):
        growth_plan = {"short_term": [], "mid_term": []}
        report_obj["growth_plan"] = growth_plan
    short_term = growth_plan.get("short_term")
    if not isinstance(short_term, list):
        short_term = []
        growth_plan["short_term"] = short_term
    existing_milestones = {str(item.get("milestone") or "") for item in short_term if isinstance(item, dict)}
    next_order = len(short_term) + 1
    for idx, action in enumerate(actions[:1]):
        milestone = f"[下月重点] {action}"
        if milestone in existing_milestones:
            continue
        short_term.append(
            {
                "phase": "short_term",
                "order": next_order + idx,
                "focus_dimension": focus_dims[idx % len(focus_dims)] if focus_dims else "cap_req_growth",
                "focus_label": focus_labels[idx % len(focus_labels)] if focus_labels else "学习与发展潜力",
                "period": "0-3个月",
                "learning_path": [action],
                "practice_plan": [],
                "milestone": milestone,
                "from_auto_adjustment": True,
                "adjusted_at": stamp,
            }
        )


