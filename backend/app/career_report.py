"""
生涯报告（M1）：
- 导入人岗匹配智能推荐 Top5
- 手动选择目标职业（最多 5 个）
- 生成并保存报告快照（短期/中期成长计划 + 评估指标）
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from statistics import pstdev
from typing import Any, Dict, List, Tuple

import requests
from flask import Blueprint, current_app, jsonify, request
from openai import OpenAI

from .auth import get_bearer_user_id
from .db import db_cursor
from .jobs import _driver, _neo4j_settings, _serialize_row
from .match_llm_refine import refine_top5_deepseek
from .match_preview import (
    _coarse_morphology_match,
    _fetch_jobs_for_match,
    _resolve_student_profile,
    _sort_ranked_for_goal,
)

career_report_bp = Blueprint("career_report", __name__, url_prefix="/api/report")

# 进步曲线（0–100）：沿横轴每经过 1 个月，相对上一节点进步度最多上涨多少
TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH = 15.0

DIM_LABELS: Dict[str, str] = {
    "cap_req_theory": "专业理论知识",
    "cap_req_cross": "交叉学科广度",
    "cap_req_practice": "专业实践技能",
    "cap_req_digital": "数字素养技能",
    "cap_req_innovation": "创新创业能力",
    "cap_req_teamwork": "团队协作能力",
    "cap_req_social": "社会实践网络",
    "cap_req_growth": "学习与发展潜力",
}

SHORT_TERM_ACTIONS: Dict[str, List[str]] = {
    "cap_req_theory": ["完成 1 门岗位核心课程并输出笔记", "每周整理 1 份知识图谱并复盘"],
    "cap_req_cross": ["选修 1 门跨学科课程", "每月完成 1 次跨领域案例拆解"],
    "cap_req_practice": ["完成 1 个可展示的实战小项目", "参与 1 次真实需求协作（校内/开源）"],
    "cap_req_digital": ["掌握目标岗位常用数字工具链", "完成 2 份数据分析或自动化练习"],
    "cap_req_innovation": ["每两周输出 1 个问题-方案提案", "参与 1 次创新/挑战赛"],
    "cap_req_teamwork": ["在团队项目中承担明确角色并记录产出", "每周进行一次协作复盘"],
    "cap_req_social": ["每月参加 1 次行业交流活动", "建立并维护 10 位职业联系人清单"],
    "cap_req_growth": ["建立双周学习节奏并固化复盘模板", "每月更新一次成长仪表板"],
}

MID_TERM_ACTIONS: Dict[str, List[str]] = {
    "cap_req_theory": ["完成岗位进阶知识体系并形成专题文章", "准备并通过 1 项专业认证"],
    "cap_req_cross": ["完成 1 个跨学科综合项目", "将主专业能力迁移到新场景并沉淀方法"],
    "cap_req_practice": ["完成 1 段岗位相关实习/长期项目", "建立可面试展示的项目作品集"],
    "cap_req_digital": ["完成 1 个数据/自动化中型项目", "形成可复用工具脚本与文档"],
    "cap_req_innovation": ["主导 1 个从方案到落地的创新实践", "形成个人创新案例库"],
    "cap_req_teamwork": ["承担小团队协调职责", "将协作流程标准化并沉淀模板"],
    "cap_req_social": ["建立稳定行业导师/前辈反馈机制", "完成 3 次目标岗位深度访谈"],
    "cap_req_growth": ["形成年度成长路线图并季度修订", "将学习成果固化为公开作品或分享"],
}


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(v, (int, float)):
        return bool(v)
    return False


def _clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        x = int(v)
    except (TypeError, ValueError):
        x = default
    return max(lo, min(hi, x))


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


_TARGET_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_metric_target(target_text: str) -> float:
    text = str(target_text or "").strip()
    m = _TARGET_NUM_RE.search(text)
    if not m:
        return 0.0
    return _to_float(m.group(0), 0.0)


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
        target = _parse_metric_target(str(m.get("target") or "0"))
        actual = _to_float(submitted.get(code), float("nan"))
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
        pcts.append(_to_float(m.group(1), 0.0))
    points: List[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*分", text):
        points.append(_to_float(m.group(1), 0.0))
    for m in re.finditer(r"(?:提高|提升|增加|上涨|多了|少|降低|减少)\s*(\d+(?:\.\d+)?)\s*分", text):
        points.append(_to_float(m.group(1), 0.0))
    item_counts: List[int] = []
    for m in re.finditer(r"(\d+)\s*(?:项|个|条|件)(?:成果|作品|产出|项目)?", text):
        item_counts.append(int(_to_float(m.group(1), 0.0)))
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
                return _to_float(m.group(1), default)
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
    prompt_obj = {
        "task": "extract_review_metrics_from_natural_language",
        "review_cycle": review_cycle,
        "review_text": review_text,
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
        f"{json.dumps(prompt_obj, ensure_ascii=False)}"
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
        parsed = json.loads(_strip_json_fence(text))
        if not isinstance(parsed, dict):
            raise RuntimeError("llm_root_not_object")
        metrics = {
            "dim_gap_reduction": _to_float(parsed.get("dim_gap_reduction"), 0.0),
            "project_completion": _to_float(parsed.get("project_completion"), 0.0),
            "match_score_change": _to_float(parsed.get("match_score_change"), 0.0),
            "delivery_output": _to_float(parsed.get("delivery_output"), 0.0),
        }
        metrics["delivery_output"] = max(0.0, round(metrics.get("delivery_output", 0.0)))
        for k in ("dim_gap_reduction", "project_completion", "match_score_change"):
            metrics[k] = round(_to_float(metrics.get(k), 0.0), 2)
        summary = str(parsed.get("summary") or "").strip()[:120]
        return {
            "ok": True,
            "metrics": metrics,
            "summary": summary,
            "model": model,
            "source": "deepseek",
            "raw": _strip_json_fence(text)[:1200],
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
            gap_counter[str(k)] += _to_float(v, 0.0)
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
    provider = str(cfg.get("CAREER_PRIMARY_PROVIDER") or "deepseek").strip().lower()
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    secondary = str(cfg.get("CAREER_SECONDARY_PROVIDER") or "").strip().lower()

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

    user_payload = {
        "task": "auto_replan",
        "failed_metrics": failed_metrics,
        "targets": target_top,
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
    )
    user_prompt = json.dumps(user_payload, ensure_ascii=False)

    def _try_provider(p: str) -> Dict[str, Any]:
        if p == "deepseek":
            api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
            if not api_key:
                return {"ok": False, "error": "missing DEEPSEEK_API_KEY"}
            text = _call_openai_compatible(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                model=str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat"),
                timeout=timeout,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return _parse_replan_json(text, provider="deepseek", model=str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat"))
        if p == "qwen":
            api_key = str(cfg.get("DASHSCOPE_API_KEY") or "").strip()
            if not api_key:
                return {"ok": False, "error": "missing DASHSCOPE_API_KEY"}
            text = _call_qwen_text(
                api_key=api_key,
                model=str(cfg.get("CAREER_QWEN_MODEL") or "qwen-plus"),
                user_prompt=user_prompt,
                timeout=timeout,
            )
            return _parse_replan_json(text, provider="qwen", model=str(cfg.get("CAREER_QWEN_MODEL") or "qwen-plus"))
        # 豆包
        api_key = str(cfg.get("ARK_API_KEY") or "").strip()
        if not api_key:
            return {"ok": False, "error": "missing ARK_API_KEY"}
        text = _call_openai_compatible(
            api_key=api_key,
            base_url=str(cfg.get("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"),
            model=str(cfg.get("CAREER_ARK_MODEL") or cfg.get("ARK_MODEL") or "doubao-seed-2-0-lite-260215"),
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return _parse_replan_json(
            text,
            provider="doubao",
            model=str(cfg.get("CAREER_ARK_MODEL") or cfg.get("ARK_MODEL") or "doubao-seed-2-0-lite-260215"),
        )

    try:
        first = _try_provider(provider)
        if first.get("ok"):
            return first
        if secondary and secondary != provider:
            second = _try_provider(secondary)
            if second.get("ok"):
                second["error"] = first.get("error")
                return second
            return {"ok": False, "error": f"primary:{first.get('error')};secondary:{second.get('error')}"}
        return first
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


def _ensure_report_tables() -> None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS career_reports (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              user_id BIGINT UNSIGNED NOT NULL,
              resume_id BIGINT UNSIGNED NOT NULL,
              title VARCHAR(160) NOT NULL,
              primary_job_id VARCHAR(191) NULL,
              target_job_ids_json JSON NOT NULL,
              report_json LONGTEXT NOT NULL,
              meta_json JSON NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_career_reports_user_id_created_at (user_id, created_at DESC),
              CONSTRAINT fk_career_reports_user_id
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS career_report_targets (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              report_id BIGINT UNSIGNED NOT NULL,
              job_id VARCHAR(191) NOT NULL,
              title VARCHAR(191) NULL,
              is_primary TINYINT(1) NOT NULL DEFAULT 0,
              target_order INT NOT NULL DEFAULT 0,
              source VARCHAR(32) NOT NULL DEFAULT 'manual',
              meta_json JSON NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              UNIQUE KEY uk_report_job (report_id, job_id),
              KEY idx_career_report_targets_report_id_order (report_id, target_order),
              CONSTRAINT fk_career_report_targets_report_id
                FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS career_report_reviews (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              report_id BIGINT UNSIGNED NOT NULL,
              review_cycle VARCHAR(32) NOT NULL DEFAULT 'biweekly',
              metrics_json JSON NOT NULL,
              adjustment_json JSON NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_career_report_reviews_report_id_created_at (report_id, created_at DESC),
              CONSTRAINT fk_career_report_reviews_report_id
                FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def _query_jobs_by_ids(job_ids: List[str]) -> List[Dict[str, Any]]:
    ids = [str(x).strip() for x in job_ids if str(x).strip()]
    if not ids:
        return []
    uri, user, password, database = _neo4j_settings()
    if not password:
        return []
    query = """
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) IN $ids
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.salary, '薪资面议') AS salary,
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
      coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
      coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
      coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
      coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
      coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
      coalesce(j.cap_req_social, 0.0) AS cap_req_social,
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
      coalesce(j.cap_conf_theory, 0.0) AS cap_conf_theory,
      coalesce(j.cap_conf_cross, 0.0) AS cap_conf_cross,
      coalesce(j.cap_conf_practice, 0.0) AS cap_conf_practice,
      coalesce(j.cap_conf_digital, 0.0) AS cap_conf_digital,
      coalesce(j.cap_conf_innovation, 0.0) AS cap_conf_innovation,
      coalesce(j.cap_conf_teamwork, 0.0) AS cap_conf_teamwork,
      coalesce(j.cap_conf_social, 0.0) AS cap_conf_social,
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth
    """
    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"ids": ids})]
    cards = [_serialize_row(r) for r in rows]
    order = {jid: idx for idx, jid in enumerate(ids)}
    cards.sort(key=lambda x: order.get(x["id"], 999999))
    return cards


def _query_job_relations(job_ids: List[str], max_per_job: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    ids = [str(x).strip() for x in job_ids if str(x).strip()]
    if not ids:
        return {}
    uri, user, password, database = _neo4j_settings()
    if not password:
        return {}
    query = """
    UNWIND $ids AS jid
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = jid
    OPTIONAL MATCH (j)-[r:PROMOTE_TO|TRANSFER_TO]->(n:Job)
    WITH jid, j, r, n
    ORDER BY type(r) ASC, coalesce(n.title, n.name, '') ASC
    RETURN
      jid AS source_id,
      type(r) AS relation_type,
      coalesce(n.job_key, n.job_code, n.name, n.title, elementId(n)) AS target_id,
      coalesce(n.title, n.name, '未命名岗位') AS target_title,
      coalesce(n.company, '未知公司') AS target_company,
      coalesce(n.location, '未知地点') AS target_location
    """
    driver = _driver(uri, user, password)
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    with driver.session(database=database) as session:
        for row in session.run(query, {"ids": ids}):
            rec = dict(row)
            source_id = str(rec.get("source_id") or "").strip()
            relation_type = str(rec.get("relation_type") or "").strip()
            target_id = str(rec.get("target_id") or "").strip()
            if not source_id or not relation_type or not target_id:
                continue
            if len(out[source_id]) >= max_per_job:
                continue
            out[source_id].append(
                {
                    "relation_type": relation_type,
                    "target_id": target_id,
                    "target_title": rec.get("target_title"),
                    "target_company": rec.get("target_company"),
                    "target_location": rec.get("target_location"),
                }
            )
    return out


def _top_gap_dimensions(gaps: Dict[str, float], top_n: int = 3) -> List[str]:
    ordered = sorted(
        [(k, float(v or 0)) for k, v in (gaps or {}).items() if k in DIM_LABELS],
        key=lambda x: x[1],
        reverse=True,
    )
    return [k for k, v in ordered if v > 0][:top_n]


def _build_growth_plan(
    target_insights: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    top_gap_counter: Dict[str, int] = defaultdict(int)
    for insight in target_insights:
        for dim in _top_gap_dimensions((insight.get("match_preview") or {}).get("dimension_gaps") or {}):
            top_gap_counter[dim] += 1
    if not top_gap_counter:
        top_gap_dims = ["cap_req_growth", "cap_req_practice", "cap_req_teamwork"]
    else:
        top_gap_dims = sorted(top_gap_counter.keys(), key=lambda x: top_gap_counter[x], reverse=True)[:3]

    short_term: List[Dict[str, Any]] = []
    mid_term: List[Dict[str, Any]] = []
    for idx, dim in enumerate(top_gap_dims):
        short_term.append(
            {
                "phase": "short_term",
                "order": idx + 1,
                "focus_dimension": dim,
                "focus_label": DIM_LABELS.get(dim, dim),
                "period": "0-3个月",
                "learning_path": SHORT_TERM_ACTIONS.get(dim, [])[:2],
                "practice_plan": SHORT_TERM_ACTIONS.get(dim, [])[1:2] or [],
                "milestone": f"{DIM_LABELS.get(dim, dim)}完成基础补齐并有可展示产出",
            }
        )
        mid_term.append(
            {
                "phase": "mid_term",
                "order": idx + 1,
                "focus_dimension": dim,
                "focus_label": DIM_LABELS.get(dim, dim),
                "period": "3-12个月",
                "learning_path": MID_TERM_ACTIONS.get(dim, [])[:2],
                "practice_plan": MID_TERM_ACTIONS.get(dim, [])[1:2] or [],
                "milestone": f"{DIM_LABELS.get(dim, dim)}达到目标岗位可投递水平",
            }
        )

    metrics = [
        {"code": "dim_gap_reduction", "label": "关键能力缺口收敛率", "cycle": "月度", "target": ">=10%"},
        {"code": "project_completion", "label": "项目/实践任务完成率", "cycle": "月度", "target": ">=80%"},
        {"code": "match_score_change", "label": "目标岗位匹配度变化", "cycle": "月度", "target": "月增>=3分"},
        {"code": "delivery_output", "label": "可展示成果数量", "cycle": "月度", "target": "每月>=1项"},
    ]
    return short_term, mid_term, metrics


def _review_point_progress(
    submitted: Dict[str, Any],
    pass_rate: float,
    line_idx: int,
    target: Dict[str, Any],
) -> float:
    """单次复盘在曲线上的进步度（0–100），各岗位线略错开。"""
    ms_t = float(((target or {}).get("match_preview") or {}).get("match_score") or 0)
    dg = float((submitted or {}).get("dim_gap_reduction") or 0)
    pc = float((submitted or {}).get("project_completion") or 0)
    msc = float((submitted or {}).get("match_score_change") or 0)
    dl = float((submitted or {}).get("delivery_output") or 0)
    msc_c = max(-6.0, min(10.0, msc))
    evidence = min(
        100.0,
        max(10.0, 0.26 * dg + 0.36 * pc + 3.2 * msc_c + 8.5 * min(dl, 5.0)),
    )
    pr = max(0.0, min(1.0, float(pass_rate or 0.0)))
    blended = pr * 100.0 * 0.5 + evidence * 0.5
    blended += (line_idx * 1.25) + (ms_t - 55.0) * 0.08
    return max(7.0, min(100.0, blended))


def _execution_hints_for_replan_action(action: str) -> List[str]:
    a = str(action or "").strip()
    if not a:
        return []
    return [
        f"下一执行月优先事项：{a}",
        "拆解落地：把上面这一条拆成 2–4 个可勾选子任务，按周排进日程；每条任务写清「产出物」与「截止时间」。",
        "与评估对齐：对照本月四项量化指标（缺口收敛、项目完成、匹配变化、成果），复盘时逐条打勾并估算完成度。",
    ]


def _execution_hints_for_initial_item(item: Dict[str, Any]) -> List[str]:
    ms = str(item.get("milestone") or "").strip()
    lp = item.get("learning_path") or []
    pp = item.get("practice_plan") or []
    lines: List[str] = []
    if ms:
        lines.append(f"从第 1 个月起优先推进：{ms}")
    if isinstance(lp, list) and lp:
        chunk = "；".join(str(x).strip() for x in lp[:4] if str(x).strip())
        if chunk:
            lines.append(f"学习侧：{chunk}")
    if isinstance(pp, list) and pp:
        chunk2 = "；".join(str(x).strip() for x in pp[:3] if str(x).strip())
        if chunk2:
            lines.append(f"实践侧：{chunk2}")
    lines.append(
        "节奏说明：第 0 月在画布上固定本方向起点；进入第 1 月提交复盘后，系统会把量化结果写回曲线并刷新下一月安排。"
    )
    return lines


def _seed_month_zero_adjustments(report_obj: Dict[str, Any], *, stamp: str) -> None:
    """报告刚生成时，为每条发展线写入第 0 月可见的「起步执行」菱形节点。"""
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
    growth = report_obj.get("growth_plan") or {}
    short_term = growth.get("short_term") if isinstance(growth.get("short_term"), list) else []
    items = [x for x in short_term if isinstance(x, dict)][:3]
    if not items:
        return
    existing_ids = {str(x.get("id") or "") for x in adjustments if isinstance(x, dict)}
    for li, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        line_id = str(line.get("line_id") or "").strip()
        if not line_id:
            continue
        for ai, item in enumerate(items):
            milestone = str(item.get("milestone") or "").strip()
            focus_label = str(item.get("focus_label") or "短期补齐").strip()
            learning = item.get("learning_path") or []
            lp0 = str(learning[0]).strip() if isinstance(learning, list) and learning else ""
            label_text = (lp0 or milestone or focus_label)[:200]
            aid = f"adj_init0_{stamp}_{line_id}_{ai + 1}"
            if aid in existing_ids:
                continue
            existing_ids.add(aid)
            hints = _execution_hints_for_initial_item(item)
            adjustments.append(
                {
                    "id": aid,
                    "line_id": line_id,
                    "stage": "short_term",
                    "label": label_text,
                    "focus_label": focus_label,
                    "priority": ai + 1,
                    "created_at": stamp,
                    "month": round(0.0 + float(ai) * 0.07 + float(li) * 0.02, 2),
                    "progress": round(2.5 + float(ai) * 2.2 + float(li) * 0.5, 2),
                    "anchor_review_month": 0.0,
                    "plan_month": 1,
                    "kind": "initial_plan",
                    "execution_hints": hints,
                }
            )


def _build_development_lines(
    student_name: str,
    target_insights: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stage_labels = {
        "current": f"{student_name} 当前画像",
        "short_term": "短期能力补齐",
        "mid_term": "中期岗位化实践",
        "target": "目标岗位就绪",
    }
    lines: List[Dict[str, Any]] = []
    for idx, target in enumerate(target_insights):
        line_name = str(target.get("display_title") or target.get("title") or f"目标职业{idx + 1}")
        tid = str(target.get("id") or "").strip()
        nodes: List[Dict[str, Any]] = []
        for stage in ("current", "short_term", "mid_term", "target"):
            sid = f"{stage}_{idx + 1}"
            label = stage_labels[stage] if stage != "target" else line_name
            nodes.append({"id": sid, "label": label, "stage": stage})
        # 未提交动态复盘前不画进步曲线：仅保留时间轴起点 (0,0)
        timeline: List[Dict[str, Any]] = [
            {"month": 0.0, "progress": 0.0, "label": "起点", "kind": "origin"},
        ]
        lines.append(
            {
                "line_id": f"line_{idx + 1}",
                "line_name": line_name,
                "target_job_id": tid,
                "overlay_group": "shared" if idx < 2 else f"custom_{idx + 1}",
                "nodes": nodes,
                "timeline": timeline,
            }
        )
    return {
        "display_mode": "single",
        "axis": {
            "x_unit": "month",
            "x_min": 0.0,
            "x_max": 12.0,
            "x_label": "时间（月）",
            "y_min": 0.0,
            "y_max": 100.0,
            "y_label": "进步度",
        },
        "lines": lines,
        "adjustments": [],
    }


def _rebuild_development_timelines(report_obj: Dict[str, Any], reviews_asc: List[Dict[str, Any]]) -> None:
    """时间线从 (0,0) 起点开始；仅在有复盘记录后追加折线段，时间逐步向右。"""
    dev = report_obj.get("development_lines")
    if not isinstance(dev, dict):
        return
    lines = dev.get("lines")
    targets = report_obj.get("targets") or []
    if not isinstance(lines, list):
        return
    tgt_by_id = {str(t.get("id")): t for t in targets if isinstance(t, dict)}

    for idx, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        tid = str(line.get("target_job_id") or "")
        target = tgt_by_id.get(tid) or {}
        pts: List[Dict[str, Any]] = [
            {"month": 0.0, "progress": 0.0, "label": "起点", "kind": "origin"},
        ]
        prev_month = 0.0
        prev_progress = 0.0
        for i, rev in enumerate(reviews_asc):
            met = rev.get("metrics") or {}
            if not isinstance(met, dict):
                met = {}
            submitted = met.get("submitted") or {}
            if not isinstance(submitted, dict):
                submitted = {}
            ev = met.get("evaluation") or {}
            if not isinstance(ev, dict):
                ev = {}
            pr = float(ev.get("pass_rate") or 0.0)
            rid = int(rev.get("review_id") or 0)
            # 横轴按自然月：第 1 次复盘在第 1 月，第 2 次在第 2 月…（上限 12）
            month = float(min(12, i + 1))
            raw_prog = _review_point_progress(submitted, pr, idx, target)
            month_span = max(0.0, month - prev_month)
            ceiling = prev_progress + TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH * month_span
            prog = min(raw_prog, ceiling)
            prog = max(0.0, min(100.0, prog))
            llm_ex = met.get("llm_extract") or {}
            if not isinstance(llm_ex, dict):
                llm_ex = {}
            detail: Dict[str, Any] = {
                "review_text": str(met.get("review_text") or "")[:4000],
                "submitted": submitted,
                "llm_summary": str(llm_ex.get("summary") or "")[:800],
                "pass_rate": round(pr, 4),
                "all_passed": bool(ev.get("all_passed")),
            }
            pts.append(
                {
                    "month": month,
                    "progress": round(prog, 2),
                    "label": f"第{int(month)}月",
                    "kind": "review",
                    "review_id": rid,
                    "detail": detail,
                }
            )
            prev_month, prev_progress = month, prog
        pts.sort(key=lambda x: float(x.get("month") or 0.0))
        line["timeline"] = pts

    if "axis" not in dev or not isinstance(dev.get("axis"), dict):
        dev["axis"] = {
            "x_unit": "month",
            "x_min": 0.0,
            "x_max": 12.0,
            "x_label": "时间（月）",
            "y_min": 0.0,
            "y_max": 100.0,
            "y_label": "进步度",
        }
    dev["display_mode"] = "single"


def _build_trend_for_job(job: Dict[str, Any]) -> Dict[str, Any]:
    score_avg = float(job.get("score_avg") or 0)
    risk_flags = job.get("risk_flags") or []
    demand_index = max(35.0, min(98.0, 42.0 + score_avg * 0.62 - len(risk_flags) * 2.5))
    growth_signal = max(20.0, min(95.0, 35.0 + float(job.get("scores", {}).get("cap_req_growth", 0)) * 0.7))
    volatility = max(5.0, min(90.0, 18.0 + len(risk_flags) * 14.0))
    return {
        "demand_index_0_100": round(demand_index, 1),
        "growth_signal_0_100": round(growth_signal, 1),
        "volatility_0_100": round(volatility, 1),
        "analysis_text": "需求与增长信号较好，建议持续关注波动并准备备选路径。",
        "evidence": "基于岗位能力门槛、风险标记与历史岗位结构推断（M1启发式）",
        "source": "heuristic",
    }


def _fetch_category_peer_jobs(title: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    """
    以岗位类别（title）为锚点，在 Neo4j 拉取同类岗位样本（约 50 条）用于全局趋势计算。
    """
    category = str(title or "").strip()
    if not category:
        return []
    uri, user, password, database = _neo4j_settings()
    if not password:
        return []
    query = """
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        toLower(coalesce(j.title, j.name, '')) = toLower($category) OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($category)
      )
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.salary, '薪资面议') AS salary,
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
      coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
      coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
      coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
      coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
      coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
      coalesce(j.cap_req_social, 0.0) AS cap_req_social,
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
      coalesce(j.cap_conf_theory, 0.0) AS cap_conf_theory,
      coalesce(j.cap_conf_cross, 0.0) AS cap_conf_cross,
      coalesce(j.cap_conf_practice, 0.0) AS cap_conf_practice,
      coalesce(j.cap_conf_digital, 0.0) AS cap_conf_digital,
      coalesce(j.cap_conf_innovation, 0.0) AS cap_conf_innovation,
      coalesce(j.cap_conf_teamwork, 0.0) AS cap_conf_teamwork,
      coalesce(j.cap_conf_social, 0.0) AS cap_conf_social,
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth
    LIMIT $limit
    """
    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"category": category, "limit": int(max(10, min(limit, 200)))})]
    return [_serialize_row(r) for r in rows]


def _build_global_trend_for_target(job: Dict[str, Any], peer_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    以同类别岗位样本（约 50 条）计算全局需求/增长/波动，再叠加目标岗位信息给 LLM 做校准。
    """
    peers = [x for x in peer_jobs if isinstance(x, dict)]
    if not peers:
        # 无样本时回退单岗位启发式
        out = _build_trend_for_job(job)
        out["evidence"] = "同类别样本不足，回退到单岗位启发式估计"
        out["source"] = "heuristic_fallback_single"
        return out

    score_vals = [float(p.get("score_avg") or 0.0) for p in peers]
    growth_vals = [float((p.get("scores") or {}).get("cap_req_growth") or 0.0) for p in peers]
    risk_vals = [float(len((p.get("risk_flags") or []))) for p in peers]

    score_avg_global = sum(score_vals) / len(score_vals) if score_vals else 0.0
    growth_avg_global = sum(growth_vals) / len(growth_vals) if growth_vals else 0.0
    risk_avg_global = sum(risk_vals) / len(risk_vals) if risk_vals else 0.0

    # 需求、增长使用“同类别均值”口径
    demand_index = max(35.0, min(98.0, 42.0 + score_avg_global * 0.62 - risk_avg_global * 2.5))
    growth_signal = max(20.0, min(95.0, 35.0 + growth_avg_global * 0.7))

    # 波动：用样本离散度（std）映射到 0~100，波动越大风险越高
    score_std = pstdev(score_vals) if len(score_vals) > 1 else 0.0
    growth_std = pstdev(growth_vals) if len(growth_vals) > 1 else 0.0
    risk_std = pstdev(risk_vals) if len(risk_vals) > 1 else 0.0
    volatility_raw = 12.0 + score_std * 0.9 + growth_std * 0.6 + risk_std * 12.0
    volatility = max(5.0, min(90.0, volatility_raw))

    target_title = str(job.get("title") or "目标岗位")
    sample_n = len(peers)
    text = (
        f"基于同类别样本{sample_n}条计算：需求与增长由类别均值驱动，"
        f"波动由样本离散度决定；当前{target_title}建议按该趋势配置主线与备选线。"
    )
    return {
        "demand_index_0_100": round(demand_index, 1),
        "growth_signal_0_100": round(growth_signal, 1),
        "volatility_0_100": round(volatility, 1),
        "analysis_text": text[:80],
        "evidence": f"同类别岗位样本聚合计算（n={sample_n}）",
        "source": "heuristic_global_aggregated",
        "peer_sample_size": sample_n,
        "peer_stats": {
            "score_avg_global": round(score_avg_global, 2),
            "growth_avg_global": round(growth_avg_global, 2),
            "risk_avg_global": round(risk_avg_global, 2),
            "score_std": round(score_std, 2),
            "growth_std": round(growth_std, 2),
            "risk_std": round(risk_std, 2),
        },
    }


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.replace("```json", "").replace("```", "").strip()
    return t


def _clamp_0_100(v: Any, default: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = default
    return round(max(0.0, min(100.0, x)), 1)


def _augment_trends_with_deepseek(target_insights: List[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = current_app.config
    if not _truthy(cfg.get("CAREER_ENABLE_TREND_AUGMENT", True)):
        return {"ok": False, "reason": "CAREER_ENABLE_TREND_AUGMENT disabled"}
    api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "reason": "missing DEEPSEEK_API_KEY"}
    if not target_insights:
        return {"ok": False, "reason": "empty_targets"}

    payload = []
    for t in target_insights:
        payload.append(
            {
                "job_id": t.get("id"),
                "title": t.get("title"),
                "company": t.get("company"),
                "location": t.get("location"),
                "score_avg": t.get("score_avg"),
                "risk_flags": t.get("risk_flags") or [],
                "heuristic_trend": t.get("trend") or {},
            }
        )
    user_prompt = (
        "请基于每个岗位的启发式趋势与岗位信息，输出职业趋势强度修正结果。"
        "仅输出 JSON 对象，格式：{\"items\":[{\"job_id\":\"...\",\"demand_index_0_100\":0-100,"
        "\"growth_signal_0_100\":0-100,\"volatility_0_100\":0-100,\"analysis_text\":\"一句中文解释<=40字\"}]}"
        "。禁止输出 Markdown。\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    system_prompt = "你是职业趋势分析顾问，擅长根据岗位信息给出需求、增长、波动的相对判断。"
    model = str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat")
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    try:
        text = _call_openai_compatible(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model=model,
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        parsed = json.loads(_strip_json_fence(text))
        items = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(items, list):
            return {"ok": False, "reason": "llm_items_missing"}

        by_id = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            jid = str(it.get("job_id") or "").strip()
            if not jid:
                continue
            by_id[jid] = {
                "demand_index_0_100": _clamp_0_100(it.get("demand_index_0_100"), 60.0),
                "growth_signal_0_100": _clamp_0_100(it.get("growth_signal_0_100"), 60.0),
                "volatility_0_100": _clamp_0_100(it.get("volatility_0_100"), 50.0),
                "analysis_text": str(it.get("analysis_text") or "").strip()[:80],
                "evidence": "DeepSeek 趋势解释（基于岗位信息与启发式信号）",
                "source": "deepseek",
                "model": model,
            }
        if not by_id:
            return {"ok": False, "reason": "llm_empty_result"}
        updated = 0
        for t in target_insights:
            jid = str(t.get("id") or "").strip()
            if jid in by_id:
                t["trend"] = by_id[jid]
                updated += 1
        return {"ok": True, "updated": updated, "model": model}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc)}


def _call_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    client = OpenAI(api_key=api_key.strip(), base_url=base_url.strip(), timeout=timeout)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=max(0.0, min(2.0, float(temperature))),
    )
    return (resp.choices[0].message.content or "").strip()


def _call_qwen_text(*, api_key: str, model: str, user_prompt: str, timeout: float) -> str:
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": user_prompt}]},
        "parameters": {"temperature": 0.3, "result_format": "text"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    data = resp.json()
    return str((data.get("output") or {}).get("text") or "").strip()


def _build_llm_summary(
    *,
    profile: Dict[str, Any],
    target_insights: List[Dict[str, Any]],
    short_term: List[Dict[str, Any]],
    mid_term: List[Dict[str, Any]],
) -> Dict[str, Any]:
    cfg = current_app.config
    provider = str(cfg.get("CAREER_COPYWRITER_PROVIDER") or "doubao").strip().lower()
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)

    student_name = str(profile.get("display_name") or "候选人")
    brief_targets = [
        {
            "title": t.get("title"),
            "match_score": (t.get("match_preview") or {}).get("match_score"),
            "top_gaps": _top_gap_dimensions((t.get("match_preview") or {}).get("dimension_gaps") or {}, 2),
        }
        for t in target_insights[:5]
    ]
    payload = {
        "student_name": student_name,
        "targets": brief_targets,
        "short_term_focus": [x.get("focus_label") for x in short_term[:3]],
        "mid_term_focus": [x.get("focus_label") for x in mid_term[:3]],
    }
    user_prompt = (
        "请输出 2 段中文总结：\n"
        "1) 职业路径建议（80-120字）\n"
        "2) 执行提醒（80-120字）\n"
        "不要使用 markdown。信息依据如下：\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    system_prompt = "你是职业规划顾问，输出简洁、可执行、具体的中文建议。"

    try:
        if provider == "deepseek":
            api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
            if not api_key:
                raise RuntimeError("missing DEEPSEEK_API_KEY")
            text = _call_openai_compatible(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                model=str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat"),
                timeout=timeout,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return {"provider": "deepseek", "text": text}
        if provider == "qwen":
            api_key = str(cfg.get("DASHSCOPE_API_KEY") or "").strip()
            if not api_key:
                raise RuntimeError("missing DASHSCOPE_API_KEY")
            text = _call_qwen_text(
                api_key=api_key,
                model=str(cfg.get("CAREER_QWEN_MODEL") or "qwen-plus"),
                user_prompt=user_prompt,
                timeout=timeout,
            )
            return {"provider": "qwen", "text": text}

        # 默认豆包（Ark OpenAI 兼容）
        api_key = str(cfg.get("ARK_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("missing ARK_API_KEY")
        text = _call_openai_compatible(
            api_key=api_key,
            base_url=str(cfg.get("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"),
            model=str(cfg.get("CAREER_ARK_MODEL") or cfg.get("ARK_MODEL") or "doubao-seed-2-0-lite-260215"),
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return {"provider": "doubao", "text": text}
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": provider,
            "text": (
                "你当前最优策略是先完成短期关键能力补齐，再把中期任务聚焦到可证明的项目与岗位化实践。"
                "每两周检查能力缺口和任务完成率，确保成长路径持续贴近目标岗位。"
            ),
            "error": str(exc),
        }


def _build_match_ranked(profile: Dict[str, Any], q: str, location_q: str, match_goal: str) -> List[Dict[str, Any]]:
    rows = _fetch_jobs_for_match(
        q=q,
        location_q=location_q,
        cap=max(120, int(current_app.config.get("MATCH_LLM_POOL_K", 40)) * 4),
    )
    shape_w = float(current_app.config.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    margin_fit = float(current_app.config.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
    margin_stretch = float(current_app.config.get("MATCH_GAP_SOFT_MARGIN_STRETCH", 10.0))
    soft_margin = margin_stretch if match_goal == "stretch" else margin_fit
    ranked: List[Dict[str, Any]] = []
    for row in rows:
        card = _serialize_row(row)
        ms, wg, gaps, shape_r = _coarse_morphology_match(
            profile["scores"],
            profile["confidences"],
            card["scores"],
            card["confidences"],
            soft_margin=soft_margin,
            shape_weight=shape_w,
        )
        ranked.append(
            {
                **card,
                "match_preview": {
                    "match_score": ms,
                    "weighted_gap": wg,
                    "dimension_gaps": gaps,
                    "shape_correlation": shape_r,
                },
            }
        )
    _sort_ranked_for_goal(ranked, match_goal)
    return ranked


def _ensure_match_snapshot_tables() -> None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS match_runs (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              user_id BIGINT UNSIGNED NOT NULL,
              resume_id BIGINT UNSIGNED NOT NULL,
              match_goal VARCHAR(16) NOT NULL DEFAULT 'fit',
              q VARCHAR(191) NULL,
              location_q VARCHAR(191) NULL,
              refine_with_llm TINYINT(1) NOT NULL DEFAULT 0,
              student_json LONGTEXT NULL,
              stats_json JSON NULL,
              llm_json LONGTEXT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_match_runs_user_resume_created (user_id, resume_id, created_at DESC),
              KEY idx_match_runs_user_goal_created (user_id, match_goal, created_at DESC),
              CONSTRAINT fk_match_runs_user_id
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS match_run_items (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              run_id BIGINT UNSIGNED NOT NULL,
              rank_index INT NOT NULL DEFAULT 0,
              job_id VARCHAR(191) NOT NULL,
              is_llm_top5 TINYINT(1) NOT NULL DEFAULT 0,
              job_json LONGTEXT NOT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              UNIQUE KEY uk_match_run_items_run_rank (run_id, rank_index),
              KEY idx_match_run_items_run_id (run_id),
              KEY idx_match_run_items_job_id (job_id),
              CONSTRAINT fk_match_run_items_run_id
                FOREIGN KEY (run_id) REFERENCES match_runs(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def _load_recent_match_snapshot(
    *,
    user_id: int,
    resume_id: int,
    match_goal: str,
    limit: int,
) -> Tuple[List[Dict[str, Any]], str]:
    _ensure_match_snapshot_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, llm_json
            FROM match_runs
            WHERE user_id = %s
              AND resume_id = %s
              AND match_goal = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, resume_id, match_goal),
        )
        run = cur.fetchone()
        if not run:
            return [], "none"
        run_id = int(run["id"])
        llm_json = run.get("llm_json")
        if isinstance(llm_json, str):
            try:
                llm_json = json.loads(llm_json)
            except Exception:  # noqa: BLE001
                llm_json = {}
        if not isinstance(llm_json, dict):
            llm_json = {}

        # 优先使用快照中的 llm top5
        if llm_json.get("ok") and isinstance(llm_json.get("top5"), list):
            llm_targets: List[Dict[str, Any]] = []
            for item in (llm_json.get("top5") or [])[:limit]:
                if not isinstance(item, dict):
                    continue
                llm_targets.append(
                    {
                        "job_id": item.get("job_id"),
                        "title": item.get("title"),
                        "company": item.get("company"),
                        "location": item.get("location"),
                        "salary": item.get("salary"),
                        "score_avg": item.get("coarse_match_score"),
                        "reason": item.get("one_line") or "",
                        "source": "match_snapshot_llm",
                    }
                )
            if llm_targets:
                return llm_targets, "match_snapshot_llm"

        cur.execute(
            """
            SELECT rank_index, job_json
            FROM match_run_items
            WHERE run_id = %s
            ORDER BY rank_index ASC
            LIMIT %s
            """,
            (run_id, limit),
        )
        rows = cur.fetchall()
    coarse_targets: List[Dict[str, Any]] = []
    for row in rows:
        job_json = row.get("job_json")
        if isinstance(job_json, str):
            try:
                job_json = json.loads(job_json)
            except Exception:  # noqa: BLE001
                job_json = {}
        if not isinstance(job_json, dict):
            continue
        coarse_targets.append(
            {
                "job_id": job_json.get("id"),
                "title": job_json.get("title"),
                "company": job_json.get("company"),
                "location": job_json.get("location"),
                "salary": job_json.get("salary"),
                "score_avg": (job_json.get("match_preview") or {}).get("match_score"),
                "reason": "来自最近一次匹配快照",
                "source": "match_snapshot_coarse",
            }
        )
    return coarse_targets, ("match_snapshot_coarse" if coarse_targets else "none")


@career_report_bp.post("/targets/import-from-match")
def import_targets_from_match():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录后导入目标职业"}), 401

    body = request.get_json(silent=True) or {}
    resume_id = body.get("resume_id")
    try:
        rid = int(resume_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "resume_id 无效"}), 400

    profile, err = _resolve_student_profile({"resume_id": rid}, uid)
    if err or not profile:
        return jsonify({"ok": False, "message": err or "画像读取失败"}), 400

    q = str(body.get("q") or "").strip()
    location_q = str(body.get("location_q") or "").strip()
    match_goal = str(body.get("match_goal") or "fit").strip().lower()
    if match_goal not in {"fit", "stretch"}:
        match_goal = "fit"
    limit = _clamp_int(body.get("limit"), 1, 5, 5)
    refine_with_llm = _truthy(body.get("refine_with_llm", True))

    selected: List[Dict[str, Any]]
    source = "match_coarse"

    # 优先读取最近一次匹配快照（与岗位匹配页结果保持一致）
    selected, source = _load_recent_match_snapshot(
        user_id=uid,
        resume_id=rid,
        match_goal=match_goal,
        limit=limit,
    )

    if not selected:
        ranked = _build_match_ranked(profile, q, location_q, match_goal)
        pool = ranked[: max(limit, _clamp_int(current_app.config.get("MATCH_LLM_POOL_K", 40), 5, 100, 40))]
        if refine_with_llm:
            api_key = str(current_app.config.get("DEEPSEEK_API_KEY") or "").strip()
            if api_key:
                llm_payload, llm_err = refine_top5_deepseek(
                    profile,
                    pool,
                    api_key=api_key,
                    model=str(current_app.config.get("MATCH_DEEPSEEK_MODEL") or "deepseek-chat"),
                    timeout=float(current_app.config.get("MATCH_LLM_TIMEOUT_SECONDS") or 120.0),
                    match_goal=match_goal,
                )
                if not llm_err and llm_payload:
                    selected = []
                    for item in (llm_payload.get("top5") or [])[:limit]:
                        selected.append(
                            {
                                "job_id": item.get("job_id"),
                                "title": item.get("title"),
                                "company": item.get("company"),
                                "location": item.get("location"),
                                "salary": item.get("salary"),
                                "score_avg": item.get("coarse_match_score"),
                                "reason": item.get("one_line") or "",
                                "source": "match_llm",
                            }
                        )
                    source = "match_llm_recompute"
                else:
                    selected = []
            else:
                selected = []
        else:
            selected = []

    if not selected:
        ranked = _build_match_ranked(profile, q, location_q, match_goal)
        selected = [
            {
                "job_id": row.get("id"),
                "title": row.get("title"),
                "company": row.get("company"),
                "location": row.get("location"),
                "salary": row.get("salary"),
                "score_avg": (row.get("match_preview") or {}).get("match_score"),
                "reason": "基于画像与岗位八维需求匹配排序",
                "source": "match_coarse",
            }
            for row in ranked[:limit]
        ]
        source = "match_coarse_recompute"

    return jsonify(
        {
            "ok": True,
            "data": {
                "resume_id": rid,
                "match_goal": match_goal,
                "source": source,
                "targets": selected,
            },
        }
    )


@career_report_bp.post("/targets/manual-search")
def manual_search_targets():
    body = request.get_json(silent=True) or {}
    q = str(body.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "message": "请提供岗位关键词"}), 400
    location_q = str(body.get("location_q") or "").strip()
    limit = _clamp_int(body.get("limit"), 1, 30, 20)
    rows = _fetch_jobs_for_match(q=q, location_q=location_q, cap=max(limit, 60))
    cards = [_serialize_row(r) for r in rows][:limit]
    targets = [
        {
            "job_id": c.get("id"),
            "title": c.get("title"),
            "company": c.get("company"),
            "location": c.get("location"),
            "salary": c.get("salary"),
            "score_avg": c.get("score_avg"),
            "scores": c.get("scores"),
            "source": "manual_search",
        }
        for c in cards
    ]
    return jsonify({"ok": True, "data": {"targets": targets, "count": len(targets)}})


@career_report_bp.post("/generate")
def generate_report():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录后生成报告"}), 401
    body = request.get_json(silent=True) or {}

    resume_id = body.get("resume_id")
    try:
        rid = int(resume_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "resume_id 无效"}), 400

    profile, err = _resolve_student_profile({"resume_id": rid}, uid)
    if err or not profile:
        return jsonify({"ok": False, "message": err or "画像读取失败"}), 400

    raw_ids = body.get("target_job_ids")
    if not isinstance(raw_ids, list):
        return jsonify({"ok": False, "message": "target_job_ids 必须为数组"}), 400
    target_job_ids = [str(x).strip() for x in raw_ids if str(x).strip()]
    target_job_ids = list(dict.fromkeys(target_job_ids))
    if not target_job_ids:
        return jsonify({"ok": False, "message": "请至少选择 1 个目标职业"}), 400
    if len(target_job_ids) > 5:
        return jsonify({"ok": False, "message": "最多选择 5 个目标职业"}), 400

    target_cards = _query_jobs_by_ids(target_job_ids)
    found_ids = {str(x.get("id")) for x in target_cards}
    missing = [jid for jid in target_job_ids if jid not in found_ids]
    if missing:
        return jsonify({"ok": False, "message": f"存在无效 job_id: {', '.join(missing[:3])}"}), 400

    margin = float(current_app.config.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
    shape_w = float(current_app.config.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    target_insights: List[Dict[str, Any]] = []
    for card in target_cards:
        peers = _fetch_category_peer_jobs(str(card.get("title") or ""), limit=50)
        ms, wg, gaps, shape_r = _coarse_morphology_match(
            profile["scores"],
            profile["confidences"],
            card["scores"],
            card["confidences"],
            soft_margin=margin,
            shape_weight=shape_w,
        )
        target_insights.append(
            {
                **card,
                "display_title": (
                    f"{str(card.get('title') or '目标岗位')} · {str(card.get('company') or '未知公司')}"
                ),
                "trend": _build_global_trend_for_target(card, peers),
                "match_preview": {
                    "match_score": ms,
                    "weighted_gap": wg,
                    "dimension_gaps": gaps,
                    "shape_correlation": shape_r,
                },
            }
        )

    trend_meta = _augment_trends_with_deepseek(target_insights)

    relations = _query_job_relations(target_job_ids)
    short_term, mid_term, metrics = _build_growth_plan(target_insights)
    lines = _build_development_lines(str(profile.get("display_name") or "候选人"), target_insights)
    llm_summary = _build_llm_summary(
        profile=profile,
        target_insights=target_insights,
        short_term=short_term,
        mid_term=mid_term,
    ) if _truthy(current_app.config.get("CAREER_ENABLE_COPYWRITER", True)) else {
        "provider": "disabled",
        "text": "",
    }

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    stamp_compact = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    report_obj = {
        "generated_at": now,
        "student": {
            "id": profile.get("id"),
            "display_name": profile.get("display_name"),
            "scores": profile.get("scores"),
            "confidences": profile.get("confidences"),
            "score_avg": profile.get("score_avg"),
            "education": profile.get("education"),
        },
        "targets": target_insights,
        "path_relations": relations,
        "development_lines": lines,
        "growth_plan": {
            "short_term": short_term,
            "mid_term": mid_term,
        },
        "evaluation": {
            "cycle": {"default": "monthly", "recommended": ["monthly"]},
            "metrics": metrics,
            "adjust_rule": "连续2个评估周期未达标时触发自动重规划",
        },
        "narrative": llm_summary,
        "trend_meta": trend_meta,
    }
    _seed_month_zero_adjustments(report_obj, stamp=stamp_compact)

    _ensure_report_tables()
    title = str(body.get("title") or "").strip() or f"生涯报告-{now[:10]}"
    primary_job_id = str(body.get("primary_job_id") or target_job_ids[0]).strip()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO career_reports (
              user_id, resume_id, title, primary_job_id, target_job_ids_json, report_json, meta_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uid,
                rid,
                title[:160],
                primary_job_id or None,
                _json_dumps(target_job_ids),
                _json_dumps(report_obj),
                _json_dumps(
                    {
                        "providers": {
                            "primary": current_app.config.get("CAREER_PRIMARY_PROVIDER"),
                            "secondary": current_app.config.get("CAREER_SECONDARY_PROVIDER"),
                            "copywriter": current_app.config.get("CAREER_COPYWRITER_PROVIDER"),
                        }
                    }
                ),
            ),
        )
        report_id = int(cur.lastrowid)
        for idx, target in enumerate(target_insights):
            job_id = str(target.get("id") or "").strip()
            if not job_id:
                continue
            cur.execute(
                """
                INSERT INTO career_report_targets (
                  report_id, job_id, title, is_primary, target_order, source, meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    report_id,
                    job_id,
                    str(target.get("title") or "")[:191] or None,
                    1 if job_id == primary_job_id else 0,
                    idx + 1,
                    "mixed",
                    _json_dumps(
                        {
                            "match_score": (target.get("match_preview") or {}).get("match_score"),
                            "trend": target.get("trend"),
                        }
                    ),
                ),
            )

    return jsonify(
        {
            "ok": True,
            "data": {
                "report_id": report_id,
                "title": title,
                "primary_job_id": primary_job_id,
                "target_job_ids": target_job_ids,
                "report": report_obj,
            },
        }
    )


@career_report_bp.get("/<int:report_id>")
def get_report_detail(report_id: int):
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, user_id, resume_id, title, primary_job_id, target_job_ids_json, report_json, created_at, updated_at
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, uid),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404
    try:
        target_ids = row.get("target_job_ids_json")
        if isinstance(target_ids, str):
            target_ids = json.loads(target_ids)
        report_obj = row.get("report_json")
        if isinstance(report_obj, str):
            report_obj = json.loads(report_obj)
    except Exception:  # noqa: BLE001
        target_ids = []
        report_obj = {}
    if isinstance(report_obj, dict):
        with db_cursor() as (_, cur2):
            cur2.execute(
                """
                SELECT id, metrics_json
                FROM career_report_reviews
                WHERE report_id = %s
                ORDER BY id ASC
                """,
                (report_id,),
            )
            rr_all = cur2.fetchall() or []
        rev_parse: List[Dict[str, Any]] = []
        for rr in rr_all:
            mj = rr.get("metrics_json")
            if isinstance(mj, str):
                try:
                    mj = json.loads(mj)
                except Exception:  # noqa: BLE001
                    mj = {}
            if not isinstance(mj, dict):
                mj = {}
            rev_parse.append({"review_id": int(rr["id"]), "metrics": mj})
        _rebuild_development_timelines(report_obj, rev_parse)
    return jsonify(
        {
            "ok": True,
            "data": {
                "report_id": int(row["id"]),
                "title": row.get("title"),
                "resume_id": row.get("resume_id"),
                "primary_job_id": row.get("primary_job_id"),
                "target_job_ids": target_ids or [],
                "report": report_obj or {},
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            },
        }
    )


@career_report_bp.get("/my/list")
def list_my_reports():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    _ensure_report_tables()
    limit = _clamp_int(request.args.get("limit"), 1, 50, 20)
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, title, resume_id, primary_job_id, target_job_ids_json, created_at, updated_at
            FROM career_reports
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (uid, limit),
        )
        rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        target_ids = row.get("target_job_ids_json")
        if isinstance(target_ids, str):
            try:
                target_ids = json.loads(target_ids)
            except Exception:  # noqa: BLE001
                target_ids = []
        out.append(
            {
                "report_id": int(row["id"]),
                "title": row.get("title"),
                "resume_id": row.get("resume_id"),
                "primary_job_id": row.get("primary_job_id"),
                "target_job_ids": target_ids or [],
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            }
        )
    return jsonify({"ok": True, "data": {"items": out}})


@career_report_bp.get("/<int:report_id>/reviews")
def list_report_reviews(report_id: int):
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, uid),
        )
        if not cur.fetchone():
            return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404
        cur.execute(
            """
            SELECT id, review_cycle, metrics_json, adjustment_json, created_at
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id DESC
            LIMIT 80
            """,
            (report_id,),
        )
        rows = cur.fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        metrics = row.get("metrics_json")
        adjust = row.get("adjustment_json")
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except Exception:  # noqa: BLE001
                metrics = {}
        if isinstance(adjust, str):
            try:
                adjust = json.loads(adjust)
            except Exception:  # noqa: BLE001
                adjust = {}
        items.append(
            {
                "review_id": int(row["id"]),
                "review_cycle": row.get("review_cycle"),
                "metrics": metrics or {},
                "adjustment": adjust or {},
                "created_at": str(row.get("created_at") or ""),
            }
        )
    return jsonify({"ok": True, "data": {"items": items}})


@career_report_bp.post("/review-cycle")
def submit_review_cycle():
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"ok": False, "message": "请先登录"}), 401
    body = request.get_json(silent=True) or {}
    report_id = body.get("report_id")
    try:
        rid = int(report_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "report_id 无效"}), 400
    # 固定按月复盘（与进步曲线横轴「第 n 月」一致）
    review_cycle = "monthly"
    submitted_metrics = body.get("metrics")
    review_text = str(body.get("review_text") or "").strip()
    if not isinstance(submitted_metrics, dict):
        submitted_metrics = None
    if not submitted_metrics and not review_text:
        return jsonify({"ok": False, "message": "请提供 metrics 或 review_text"}), 400

    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, report_json
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (rid, uid),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"ok": False, "message": "报告不存在或无权访问"}), 404

        report_obj = row.get("report_json")
        if isinstance(report_obj, str):
            try:
                report_obj = json.loads(report_obj)
            except Exception:  # noqa: BLE001
                report_obj = {}
        if not isinstance(report_obj, dict):
            report_obj = {}

        expected_metrics = (((report_obj.get("evaluation") or {}).get("metrics")) or [])
        if not isinstance(expected_metrics, list):
            expected_metrics = []

        llm_extract_meta: Dict[str, Any] = {}
        if not submitted_metrics:
            llm_extract = _llm_extract_metrics_from_text(
                report_obj=report_obj,
                review_text=review_text,
                review_cycle=review_cycle,
            )
            submitted_metrics = llm_extract.get("metrics") or {}
            llm_extract_meta = {
                "ok": bool(llm_extract.get("ok")),
                "source": llm_extract.get("source"),
                "model": llm_extract.get("model"),
                "summary": llm_extract.get("summary"),
                "error": llm_extract.get("error"),
            }
        metric_eval = _evaluate_review_metrics(expected_metrics, submitted_metrics or {})

        cur.execute(
            "SELECT COUNT(*) AS c FROM career_report_reviews WHERE report_id = %s",
            (rid,),
        )
        cnt_row = cur.fetchone() or {}
        # 与折线上「第 n 月」复盘点对齐：本次提交为第 (已有条数+1) 月
        review_anchor_month = float(min(12, int(cnt_row.get("c") or 0) + 1))

        # 每次提交评估都生成重规划方案，并在发展线画布追加菱形节点
        adjust_detail = _build_auto_adjustment(report_obj, metric_eval.get("failed_codes") or [])
        adjustment_payload = {
            "all_passed": bool(metric_eval.get("all_passed")),
            "pass_rate": metric_eval.get("pass_rate"),
            "failed_codes": metric_eval.get("failed_codes") or [],
            "auto_adjustment": adjust_detail,
        }

        cur.execute(
            """
            INSERT INTO career_report_reviews (report_id, review_cycle, metrics_json, adjustment_json)
            VALUES (%s, %s, %s, %s)
            """,
            (
                rid,
                review_cycle,
                _json_dumps(
                    {
                        "submitted": submitted_metrics,
                        "review_text": review_text,
                        "llm_extract": llm_extract_meta,
                        "evaluation": metric_eval,
                    }
                ),
                _json_dumps(adjustment_payload),
            ),
        )
        review_id = int(cur.lastrowid)

        # 将评估摘要写回 report_json，便于前端直接读取
        now_stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        eval_block = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
        eval_block["latest_review"] = {
            "review_id": review_id,
            "review_cycle": review_cycle,
            "submitted_metrics": submitted_metrics or {},
            "review_text": review_text,
            "llm_extract": llm_extract_meta,
            "evaluation": metric_eval,
            "adjustment": adjustment_payload,
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
        report_obj["evaluation"] = eval_block
        eval_block["adjust_rule_effective"] = True
        eval_block["latest_adjustment_actions"] = (adjust_detail.get("extra_actions") or [])[:3]
        _apply_auto_adjustment_to_report(
            report_obj,
            adjust_detail,
            stamp=now_stamp,
            review_anchor_month=review_anchor_month,
        )

        cur.execute(
            """
            SELECT id, metrics_json
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id ASC
            """,
            (rid,),
        )
        rev_rows_all = cur.fetchall() or []
        reviews_asc: List[Dict[str, Any]] = []
        for rr in rev_rows_all:
            mj = rr.get("metrics_json")
            if isinstance(mj, str):
                try:
                    mj = json.loads(mj)
                except Exception:  # noqa: BLE001
                    mj = {}
            if not isinstance(mj, dict):
                mj = {}
            reviews_asc.append({"review_id": int(rr["id"]), "metrics": mj})
        _rebuild_development_timelines(report_obj, reviews_asc)

        cur.execute(
            """
            UPDATE career_reports
            SET report_json = %s
            WHERE id = %s
            """,
            (_json_dumps(report_obj), rid),
        )

    return jsonify(
        {
            "ok": True,
            "data": {
                "review_id": review_id,
                "report_id": rid,
                "review_cycle": review_cycle,
                "evaluation": metric_eval,
                "adjustment": adjustment_payload,
                "submitted_metrics": submitted_metrics or {},
                "review_text": review_text,
                "llm_extract": llm_extract_meta,
            },
        }
    )
