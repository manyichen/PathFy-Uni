"""趋势分析。"""
from __future__ import annotations

import json
from statistics import pstdev
from typing import Any, Dict, List

import requests
from flask import current_app

from app.infrastructure.llm import strip_json_fence
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings, serialize_job_row
from app.domains.report.constants import DIM_LABELS
from app.domains.report.helpers import _truthy

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
    uri, user, password, database = neo4j_settings()
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
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"category": category, "limit": int(max(10, min(limit, 200)))})]
    return [serialize_job_row(r) for r in rows]


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
        parsed = json.loads(strip_json_fence(text))
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


