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
from app.domains.report.constants import DIM_LABELS, SHORT_TERM_ACTIONS
from app.domains.report.growth import (
    _execution_hints_for_replan_action,
    _review_point_progress,
)
from app.domains.report.llm import _call_openai_compatible
from app.domains.report.recommendations import pick_replan_resource_hints
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


def _build_auto_adjustment(report_obj: Dict[str, Any], failed_codes: List[str]) -> Dict[str, Any]:
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

    # LLM 优先：根据失败指标生成更贴合当前报告的重规划动作；失败时回退规则动作
    llm_payload = _llm_auto_replan_payload(report_obj, failed_codes, top_dims, actions[:3])
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
        llm_meta = {
            "enabled": True,
            "used": True,
            "provider": llm_payload.get("provider"),
            "model": llm_payload.get("model"),
            "raw": llm_payload.get("raw"),
        }
    else:
        labels = [DIM_LABELS.get(x, x) for x in top_dims]
        actions = actions[:3]
        llm_meta = {
            "enabled": bool(current_app.config.get("CAREER_ENABLE_REPLAN_LLM", True)),
            "used": False,
            "error": llm_payload.get("error") or "llm_unavailable",
        }

    graph_hints = pick_replan_resource_hints(report_obj, top_dims)
    if graph_hints:
        actions = graph_hints[:1] + [a for a in actions if a not in graph_hints][:3]

    return {
        "triggered": True,
        "reason": "本月复盘量化完成后触发自动重规划",
        "failed_metric_codes": failed_codes,
        "focus_dimensions": top_dims,
        "focus_labels": labels,
        "extra_actions": actions[:3],
        "llm_meta": llm_meta,
    }


def _llm_auto_replan_payload(
    report_obj: Dict[str, Any],
    failed_codes: List[str],
    fallback_dims: List[str],
    fallback_actions: List[str],
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
        gaps = ((t.get("match_preview") or {}).get("dimension_gaps") or {})
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

    user_payload = {
        "task": "auto_replan",
        "failed_metrics": failed_metrics,
        "targets": target_top,
        "grounded_resources": grounded,
        "fallback": {
            "focus_dimensions": fallback_dims,
            "focus_labels": [DIM_LABELS.get(x, x) for x in fallback_dims],
            "extra_actions": fallback_actions,
        },
        "output_schema": {
            "focus_dimensions": ["cap_req_growth", "cap_req_practice"],
            "focus_labels": ["学习与发展潜力", "专业实践技能"],
            "extra_actions": ["每周完成1次针对性练习并记录复盘"],
        },
    }
    system_prompt = (
        "你是职业发展重规划助手。请基于失败指标与目标岗位缺口，输出最小可执行重规划方案。"
        "只输出 JSON 对象，不要输出 markdown。"
        "键必须仅包含 focus_dimensions(数组, 1-2个cap_req_*), focus_labels(数组), extra_actions(数组, 1-3条中文可执行动作)。"
        "extra_actions 应优先引用 grounded_resources 中的具体课程或竞赛名称，勿编造列表外资源。"
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
    if not dims or not actions:
        return {"ok": False, "error": "llm_missing_required_fields"}
    return {
        "ok": True,
        "provider": provider,
        "model": model,
        "data": {
            "focus_dimensions": dims[:2],
            "focus_labels": labels[:2],
            "extra_actions": actions[:3],
        },
        "raw": raw[:1200],
    }


def _apply_auto_adjustment_to_report(
    report_obj: Dict[str, Any],
    adjust_detail: Dict[str, Any],
    *,
    stamp: str,
    review_anchor_month: float | None = None,
) -> None:
    if not adjust_detail.get("triggered"):
        return
    actions = [str(x).strip() for x in (adjust_detail.get("extra_actions") or []) if str(x).strip()]
    focus_dims = [str(x).strip() for x in (adjust_detail.get("focus_dimensions") or []) if str(x).strip()]
    focus_labels = [str(x).strip() for x in (adjust_detail.get("focus_labels") or []) if str(x).strip()]
    if not actions:
        return

    eval_e = report_obj.get("evaluation") or {}
    lr = eval_e.get("latest_review") or {}
    submitted_adj = lr.get("submitted_metrics") or {}
    if not isinstance(submitted_adj, dict):
        submitted_adj = {}
    ev_lr = lr.get("evaluation") or {}
    if not isinstance(ev_lr, dict):
        ev_lr = {}
    pass_adj = float(ev_lr.get("pass_rate") or 0.0)
    targets_lookup = report_obj.get("targets") or []
    tgt_by_line = {str(t.get("id")): t for t in targets_lookup if isinstance(t, dict)}

    # 1) 把自动调整任务插入 growth_plan，便于阶段计划面板直接展示
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
    for idx, action in enumerate(actions):
        milestone = f"[自动重规划] {action}"
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

    # 2) 把自动调整节点写入 development_lines.adjustments，前端可直接绘制
    dev_lines = report_obj.get("development_lines")
    if not isinstance(dev_lines, dict):
        return
    lines = dev_lines.get("lines")
    if not isinstance(lines, list):
        return
    adjustments = dev_lines.get("adjustments")
    if not isinstance(adjustments, list):
        adjustments = []
        dev_lines["adjustments"] = adjustments
    existing_adjust_ids = {str(x.get("id") or "") for x in adjustments if isinstance(x, dict)}

    for li, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        line_id = str(line.get("line_id") or "").strip()
        if not line_id:
            continue
        tgt = tgt_by_line.get(str(line.get("target_job_id") or "")) or {}
        base_p = _review_point_progress(submitted_adj, pass_adj, li, tgt)
        for ai, action in enumerate(actions):
            aid = f"adj_{stamp}_{line_id}_{ai+1}"
            if aid in existing_adjust_ids:
                continue
            if review_anchor_month is not None:
                am_int = int(min(12, max(0, int(round(float(review_anchor_month))))))
                # 刚结束第 am_int 月复盘：重规划节点落在「下一执行月」，与折线横轴语义一致
                release_m = float(min(12.0, float(am_int + 1)))
                adj_month = round(min(12.0, release_m + float(ai) * 0.12 + float(li) * 0.03), 2)
                plan_m = int(min(12, am_int + 1))
                anchor_m = float(am_int)
            else:
                adj_month = round(min(12.0, 1.0 + float(ai) * 0.12 + float(li) * 0.03), 2)
                plan_m = 1
                anchor_m = 0.0
            # 与进步曲线同量级：在复盘进步度附近小幅抬升，避免菱形漂在曲线上方
            prog_marker = round(
                min(100.0, max(0.5, base_p + 2.0 + float(ai) * 1.4 + float(li) * 0.35)),
                2,
            )
            adjustments.append(
                {
                    "id": aid,
                    "line_id": line_id,
                    "stage": "short_term",
                    "label": action,
                    "focus_label": focus_labels[ai % len(focus_labels)] if focus_labels else "能力补齐",
                    "priority": li + 1,
                    "created_at": stamp,
                    "month": adj_month,
                    "progress": prog_marker,
                    "anchor_review_month": anchor_m,
                    "plan_month": plan_m,
                    "kind": "replan",
                    "execution_hints": _execution_hints_for_replan_action(action),
                }
            )


