"""
人岗匹配：八维轮廓 Pearson + 软 surplus 加权粗排（M1）；可选 DeepSeek 在候选池上精排 Top5 与文字分析（M2）。

Neo4j 使用 NEO4J_*；DeepSeek 使用 backend/.env 中的 DEEPSEEK_API_KEY。
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Tuple

from flask import current_app
from app.db import db_cursor
from app.infrastructure.neo4j import CONF_KEYS, DIM_KEYS, neo4j_driver, neo4j_settings, serialize_job_row
from app.domains.match.capability_profile import serialize_capability_profile
from app.domains.match.llm_refine import refine_top5_deepseek
from app.domains.match.preference_fit import (
    PREFERENCE_FIT_ALGORITHM_VERSION,
    build_preference_fit,
)
from app.domains.match.preference_ranking import (
    PREFERENCE_EXPERIMENT_KEY,
    PREFERENCE_RANKING_VERSION,
    apply_preference_tie_break,
    experiment_variant,
)
from app.domains.match.snapshots import persist_match_snapshot
from app.domains.jobs.workstyle import WORKSTYLE_PROPERTY_KEYS, WORKSTYLE_SNAPSHOT_VERSION, build_job_workstyle
from app.domains.personality.preference_profile import preference_context_summary, resolve_preference_profile
from app.domains.settings.service import setting, settings_view

_DIM_TO_CONF: Dict[str, str] = {d: c for d, c in zip(DIM_KEYS, CONF_KEYS)}
_INTERACTIVE_LLM_POOL_CAP = 20
_INTERACTIVE_LLM_TIMEOUT_CAP_SECONDS = 90.0
_PRIMARY_LLM_TIMEOUT_CAP_SECONDS = 55.0
_FALLBACK_LLM_POOL_CAP = 10
_FALLBACK_LLM_TIMEOUT_CAP_SECONDS = 30.0
_RETRYABLE_LLM_ERROR_CODES = {"timeout", "network", "rate_limit", "invalid_response"}

_DIM_LABELS = {
    "cap_req_theory": "专业理论",
    "cap_req_cross": "交叉学科",
    "cap_req_practice": "实践技能",
    "cap_req_digital": "数字素养",
    "cap_req_innovation": "创新创业",
    "cap_req_teamwork": "团队协作",
    "cap_req_social": "社会网络",
    "cap_req_growth": "学习成长",
}


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _safe_int_or_none(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _pearson_across_dims(
    student_scores: Dict[str, float],
    job_scores: Dict[str, float],
) -> float:
    """八维得分在维度上的 Pearson 相关：雷达轮廓是否同涨同落（越接近 1 形状越像）。"""
    s_vals = [float(student_scores.get(dk, 0.0)) for dk in DIM_KEYS]
    j_vals = [float(job_scores.get(dk, 0.0)) for dk in DIM_KEYS]
    n = len(DIM_KEYS)
    mean_s = sum(s_vals) / n
    mean_j = sum(j_vals) / n
    var_s = sum((x - mean_s) ** 2 for x in s_vals)
    var_j = sum((x - mean_j) ** 2 for x in j_vals)
    if var_s < 1e-12 or var_j < 1e-12:
        return 1.0
    cov = sum((s_vals[i] - mean_s) * (j_vals[i] - mean_j) for i in range(n))
    r = cov / (math.sqrt(var_s) * math.sqrt(var_j) + 1e-12)
    return max(-1.0, min(1.0, r))


def _coarse_morphology_match(
    student_scores: Dict[str, float],
    student_conf: Dict[str, float],
    job_scores: Dict[str, float],
    job_conf: Dict[str, float],
    *,
    soft_margin: float,
    shape_weight: float,
) -> Tuple[float, float, Dict[str, float], float]:
    """
    粗排匹配分：八维轮廓 Pearson（形状）与 min(置信) 加权的软 surplus（岗位每维可高于学生 soft_margin 内不罚）。
    返回 (match_score 0-100, weighted_soft_gap, per_dim_soft_gap, pearson_r)。
    """
    gamma = max(0.0, min(1.0, float(shape_weight)))
    margin = max(0.0, float(soft_margin))

    weighted_sum = 0.0
    w_sum = 0.0
    gaps: Dict[str, float] = {}
    for dk in DIM_KEYS:
        ck = _DIM_TO_CONF[dk]
        s = float(student_scores.get(dk, 0.0))
        jv = float(job_scores.get(dk, 0.0))
        sc = float(student_conf.get(ck, 0.5))
        jc = float(job_conf.get(ck, 0.5))
        soft_gap = max(0.0, jv - s - margin)
        gaps[dk] = round(soft_gap, 2)
        w = max(0.08, min(sc, jc))
        weighted_sum += w * soft_gap
        w_sum += w
    weighted_soft_gap = weighted_sum / w_sum if w_sum > 0 else 0.0
    weighted_soft_gap = min(weighted_soft_gap, 100.0)

    r = _pearson_across_dims(student_scores, job_scores)
    shape_term = (r + 1.0) / 2.0
    level_term = 1.0 - min(1.0, weighted_soft_gap / 100.0)
    combined = gamma * shape_term + (1.0 - gamma) * level_term
    match_score = max(0.0, min(100.0, 100.0 * combined))

    return (
        round(match_score, 2),
        round(weighted_soft_gap, 2),
        gaps,
        round(r, 4),
    )


def _fetch_jobs_for_match(
    q: str,
    location_q: str,
    cap: int,
) -> List[Dict[str, Any]]:
    uri, user, password, database = neo4j_settings()
    # Keep the Cypher projection deliberately small. The production Neo4j
    # instance resets its Bolt connection when the text predicates and 23
    # individual capability projections are compiled in the same query.
    # Returning the property map is equivalent for this read path; Python does
    # the inexpensive fallback/alias normalization below.
    query = """
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
      AND (
        $loc = '' OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($loc)
      )
    OPTIONAL MATCH (j)-[:HAS_TITLE]->(jt:JobTitle)
    WITH j, head(collect(jt)) AS jt
    RETURN properties(j) AS job, properties(jt) AS job_title, elementId(j) AS element_id
    LIMIT $cap
    """
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        records = session.run(query, {"q": q, "loc": location_q, "cap": int(cap)})
        return [_job_properties_to_match_row(r["job"], r["element_id"], r.get("job_title")) for r in records]


def _job_properties_to_match_row(properties: Any, element_id: Any, job_title_properties: Any = None) -> Dict[str, Any]:
    """Normalize a Neo4j Job property map to the existing match row contract."""
    props = dict(properties or {})
    fallback_id = str(element_id or "")
    row: Dict[str, Any] = {
        "id": props.get("job_key") or props.get("job_code") or props.get("name") or props.get("title") or fallback_id,
        "title": props.get("title") or props.get("name") or "未命名岗位",
        "salary": props.get("salary_norm") or props.get("salary") or "薪资面议",
        "salary_raw": props.get("salary") or "",
        "company": props.get("company") or "未知公司",
        "location": props.get("location") or "未知地点",
        "risk_flags": props.get("cap_risk_flags") or [],
    }
    for key in (*DIM_KEYS, *CONF_KEYS):
        row[key] = props.get(key) or 0.0
    for key in WORKSTYLE_PROPERTY_KEYS:
        row[key] = props.get(key)
    row["workstyle"] = build_job_workstyle(props, dict(job_title_properties or {}))
    return row


def _student_row_to_serialized_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    """将 student_resume 行转为已序列化学生画像（含 cap_conf_*）。"""
    scores = {k: float(row[k]) for k in DIM_KEYS}
    confidences: Dict[str, float] = {}
    for ck in CONF_KEYS:
        v = row.get(ck)
        confidences[ck] = float(v) if v is not None else 0.55
    major = (row.get("major") or "").strip()
    raw: Dict[str, Any] = {
        "id": str(row["id"]),
        "display_name": (row.get("name") or "能力画像").strip() or "能力画像",
        "education": major or None,
        "city_pref": None,
        "skills_hint": [],
        "scores": scores,
        "confidences": confidences,
    }
    return serialize_capability_profile(raw)


def _resolve_student_profile(
    body: Dict[str, Any], jwt_user_id: int | None
) -> Tuple[Dict[str, Any] | None, str | None]:
    """返回 (serialized_profile, error_message)。优先 resume_id，其次请求体内联 scores。"""
    resume_raw = body.get("resume_id")
    if resume_raw is not None and str(resume_raw).strip() != "":
        if jwt_user_id is None:
            return (
                None,
                "使用数据库能力画像请登录，并在请求头携带 Authorization: Bearer",
            )
        try:
            rid = int(resume_raw)
        except (TypeError, ValueError):
            return None, "resume_id 无效"
        try:
            with db_cursor() as (_, cur):
                cur.execute(
                    """
                    SELECT id, user_id, name, major,
                      cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
                      cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
                      cap_conf_theory, cap_conf_cross, cap_conf_practice, cap_conf_digital,
                      cap_conf_innovation, cap_conf_teamwork, cap_conf_social, cap_conf_growth
                    FROM student_resume
                    WHERE id = %s AND user_id = %s
                    LIMIT 1
                    """,
                    (rid, jwt_user_id),
                )
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            return None, f"读取能力画像失败: {exc}"
        if not row:
            return None, "未找到该简历画像或无权使用（请确认 resume_id 属于当前用户）"
        return _student_row_to_serialized_profile(row), None

    profile_id = str(body.get("profile_id") or "").strip()
    if profile_id:
        return None, "示例画像已下线，请使用 resume_id 或在请求体提供 scores"

    scores = body.get("scores")
    if isinstance(scores, dict) and scores:
        default_conf = {ck: 0.55 for ck in CONF_KEYS}
        conf_in = body.get("confidences")
        if isinstance(conf_in, dict):
            default_conf.update(
                {k: float(v) for k, v in conf_in.items() if k in CONF_KEYS}
            )
        inline = {
            "id": "inline",
            "display_name": str(body.get("display_name") or "内联测试画像"),
            "scores": scores,
            "confidences": default_conf,
        }
        return serialize_capability_profile(inline), None

    return None, "请提供 resume_id（我的能力画像）或 scores 对象"


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _effective_llm_pool_k(configured: int) -> int:
    return min(_INTERACTIVE_LLM_POOL_CAP, _clamp_int(configured, 5, 100))


def _effective_llm_timeout(configured: float) -> float:
    return min(_INTERACTIVE_LLM_TIMEOUT_CAP_SECONDS, max(10.0, float(configured)))


def _llm_error_code(error: str | None) -> str:
    text = str(error or "").lower()
    if any(token in text for token in ("apitimeouterror", "timed out", "timeout")):
        return "timeout"
    if any(token in text for token in ("ratelimiterror", "rate limit", "status_code=429", " 429")):
        return "rate_limit"
    if any(token in text for token in ("authenticationerror", "invalid api key", "status_code=401", " 401")):
        return "authentication"
    if any(token in text for token in ("insufficient balance", "insufficient_balance", "余额不足", "quota")):
        return "quota"
    if any(token in text for token in ("apiconnectionerror", "connecterror", "connection refused", "network")):
        return "network"
    if any(token in text for token in ("json_decode_error", "missing_top5", "parse_failed", "empty_response")):
        return "invalid_response"
    if "badrequesterror" in text or "status_code=400" in text:
        return "bad_request"
    return "unknown"


def _llm_public_error(code: str) -> str:
    messages = {
        "timeout": "AI 精排两次响应均超时，可能是服务繁忙；完整粗排结果不受影响。",
        "rate_limit": "AI 精排请求触发服务限流，请稍后再试；完整粗排结果不受影响。",
        "authentication": "AI 精排服务鉴权失败，请检查 DeepSeek 密钥；完整粗排结果不受影响。",
        "quota": "AI 精排服务额度不足，请检查账户余额；完整粗排结果不受影响。",
        "network": "服务器暂时无法连接 AI 精排服务；完整粗排结果不受影响。",
        "invalid_response": "AI 返回内容格式异常，请重试；完整粗排结果不受影响。",
        "bad_request": "AI 精排请求未被模型接受，请检查模型配置；完整粗排结果不受影响。",
        "unknown": "AI 精排服务暂时不可用；完整粗排结果不受影响。",
    }
    return messages.get(code, messages["unknown"])


def _refine_with_timeout_fallback(
    profile: Dict[str, Any],
    pool: List[Dict[str, Any]],
    *,
    api_key: str,
    model: str,
    configured_timeout: float,
    match_goal: str,
) -> Tuple[Dict[str, Any] | None, Dict[str, Any]]:
    """Run a bounded refinement and retry transient failures with a smaller prompt."""
    effective_timeout = _effective_llm_timeout(configured_timeout)
    primary_timeout = min(_PRIMARY_LLM_TIMEOUT_CAP_SECONDS, effective_timeout)
    payload, error = refine_top5_deepseek(
        profile,
        pool,
        api_key=api_key,
        model=model,
        timeout=primary_timeout,
        match_goal=match_goal,
    )
    if payload:
        return payload, {
            "retry_attempted": False,
            "degraded": False,
            "initial_pool_size": len(pool),
        }

    primary_code = _llm_error_code(error)
    if primary_code not in _RETRYABLE_LLM_ERROR_CODES or len(pool) <= _FALLBACK_LLM_POOL_CAP:
        return None, {
            "error_code": primary_code,
            "error": _llm_public_error(primary_code),
            "diagnostic": error,
            "retry_attempted": False,
            "degraded": False,
            "initial_pool_size": len(pool),
        }

    fallback_pool = pool[:_FALLBACK_LLM_POOL_CAP]
    fallback_timeout = min(_FALLBACK_LLM_TIMEOUT_CAP_SECONDS, effective_timeout)
    fallback_payload, fallback_error = refine_top5_deepseek(
        profile,
        fallback_pool,
        api_key=api_key,
        model=model,
        timeout=fallback_timeout,
        match_goal=match_goal,
    )
    if fallback_payload:
        return fallback_payload, {
            "retry_attempted": True,
            "degraded": True,
            "fallback_reason": primary_code,
            "initial_pool_size": len(pool),
            "fallback_pool_size": len(fallback_pool),
        }

    fallback_code = _llm_error_code(fallback_error)
    return None, {
        "error_code": fallback_code,
        "error": _llm_public_error(fallback_code),
        "diagnostic": fallback_error,
        "retry_attempted": True,
        "degraded": True,
        "fallback_reason": primary_code,
        "initial_pool_size": len(pool),
        "fallback_pool_size": len(fallback_pool),
    }


def _dimension_comparison_lines(
    student_scores: Dict[str, Any],
    job_scores: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    """Build concise, evidence-based strengths and gaps for local refinement."""
    comparisons: List[Tuple[str, float, float, float]] = []
    for key in DIM_KEYS:
        student = float(student_scores.get(key) or 0.0)
        required = float(job_scores.get(key) or 0.0)
        comparisons.append((key, student - required, student, required))

    strengths: List[str] = []
    for key, delta, student, required in sorted(comparisons, key=lambda row: row[1], reverse=True):
        if delta < -2 and strengths:
            break
        label = _DIM_LABELS.get(key, key)
        if delta >= 3:
            strengths.append(f"{label}高于岗位要求 {delta:.0f} 分（{student:.0f} / {required:.0f}）")
        elif delta >= -2:
            strengths.append(f"{label}与岗位要求基本持平（{student:.0f} / {required:.0f}）")
        if len(strengths) >= 3:
            break

    gaps: List[str] = []
    for key, delta, student, required in sorted(comparisons, key=lambda row: row[1]):
        if delta >= -3:
            break
        label = _DIM_LABELS.get(key, key)
        gaps.append(f"{label}尚差 {abs(delta):.0f} 分（{student:.0f} / {required:.0f}），建议优先补强")
        if len(gaps) >= 3:
            break

    if not strengths:
        strengths.append("能力轮廓与岗位方向接近，可从现有优势维度切入准备")
    if not gaps:
        gaps.append("暂无显著能力短板，下一步重点补充项目证据与岗位案例")
    return strengths, gaps


def _local_refine_top5(
    profile: Dict[str, Any],
    pool: List[Dict[str, Any]],
    *,
    match_goal: str,
) -> Dict[str, Any]:
    """Deterministic local fallback so external LLM failures never empty Top 5."""
    student_scores = profile.get("scores") or {}
    rows: List[Dict[str, Any]] = []
    for rank, job in enumerate(pool[:5], start=1):
        preview = job.get("match_preview") or {}
        score = round(float(preview.get("match_score") or 0.0), 1)
        strengths, gaps = _dimension_comparison_lines(student_scores, job.get("scores") or {})
        conf_avg = float(job.get("conf_avg") or 0.0)
        risks: List[str] = []
        if conf_avg < 45:
            risks.append(f"岗位能力要求证据置信度仅 {conf_avg:.0f}%，建议结合岗位详情复核")
        if match_goal == "stretch":
            one_line = f"冲刺价值排序第 {rank}；当前八维匹配度 {score:.0f}，优先验证关键能力缺口。"
        else:
            one_line = f"综合八维轮廓与能力缺口，本地增强匹配度为 {score:.0f}。"
        rows.append(
            {
                "job_id": str(job.get("id") or ""),
                "rank": rank,
                "overall_fit_0_100": score,
                "one_line": one_line,
                "strengths": strengths,
                "gaps": gaps,
                "risks": risks,
                "llm_fallback": True,
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "salary": job.get("salary"),
                "scores": job.get("scores") or {},
                "coarse_match_score": score,
            }
        )
    return {
        "top5": rows,
        "model": "local-capability-ranker-v1",
        "pool_size": len(pool),
    }


def _truthy_refine_llm(body: Dict[str, Any]) -> bool:
    v = body.get("refine_with_llm")
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
        return True
    return False


def _parse_match_goal(body: Dict[str, Any]) -> str:
    """fit=匹配适合岗位（默认）；stretch=冲刺高质岗位（偏好需求门槛更高的挑战岗）。"""
    v = str(body.get("match_goal") or body.get("matchGoal") or "").strip().lower()
    if v in ("stretch", "high", "premium", "challenge", "冲刺"):
        return "stretch"
    return "fit"


def _resolve_preference_mode(body: Dict[str, Any]) -> tuple[str, str | None]:
    mode = str(body.get("preference_mode") or "off").strip().lower()
    if mode not in {"off", "explain", "tie_break"}:
        return "off", "preference_mode 仅支持 off、explain 或 tie_break"
    return mode, None


def _preference_fit_unavailable(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return an explicit state when a preference calculation cannot run."""
    mode = str(context.get("mode") or "off")
    status = str(context.get("status") or "missing")
    if mode == "off":
        fit_status = "not_enabled"
    elif status == "measured":
        fit_status = "insufficient_job_evidence"
    elif status == "disabled":
        fit_status = "personalization_disabled"
    elif status == "legacy":
        fit_status = "legacy_user_profile"
    else:
        fit_status = "missing_user_profile"
    return {
        "status": fit_status,
        "score": None,
        "confidence": None,
        "axes": [],
        "influenced_ranking": False,
        "algorithm_version": PREFERENCE_FIT_ALGORITHM_VERSION,
    }


def _sort_ranked_for_goal(ranked: List[Dict[str, Any]], match_goal: str) -> None:
    """粗排结果排序：fit 按匹配分；stretch 在可达前提下抬高岗位八维均分（需求强度）。"""
    if not ranked:
        return
    if match_goal != "stretch":
        ranked.sort(key=lambda x: float(x["match_preview"]["match_score"]), reverse=True)
        return

    floor = float(setting("MATCH_STRETCH_MATCH_SCORE_FLOOR", 38))
    w_ms = float(setting("MATCH_STRETCH_SORT_W_MATCH", 0.32))
    w_jq = float(setting("MATCH_STRETCH_SORT_W_JOB_AVG", 0.68))

    def sort_key(card: Dict[str, Any]) -> Tuple[int, float, float]:
        ms = float((card.get("match_preview") or {}).get("match_score") or 0.0)
        jq = float(card.get("score_avg") or 0.0)
        if ms < floor:
            return (1, -ms, -jq)
        comp = w_ms * ms + w_jq * jq
        return (0, -comp, -ms)

    ranked.sort(key=sort_key)


def run_match_preview(body: Dict[str, Any], jwt_user_id: int | None) -> Tuple[Dict[str, Any] | None, str | None, int]:
    uri, user, password, _database = neo4j_settings()
    if not password:
        return None, "缺少 NEO4J_PASSWORD，无法查询岗位", 500

    profile, err = _resolve_student_profile(body, jwt_user_id)
    if err or not profile:
        return None, err or "画像解析失败", 400

    preference_mode, preference_mode_error = _resolve_preference_mode(body)
    if preference_mode_error:
        return None, preference_mode_error, 400
    requested_personality_id = _safe_int_or_none(body.get("personality_profile_id"))
    if preference_mode in {"explain", "tie_break"}:
        resolved_preference = resolve_preference_profile(
            int(jwt_user_id or 0),
            profile_id=requested_personality_id,
            require_personalization_enabled=True,
        )
        if requested_personality_id is not None and resolved_preference.get("status") == "missing":
            return None, "人格偏好画像不存在或无权使用", 403
    else:
        resolved_preference = {"status": "off", "snapshot": None}
    preference_context = preference_context_summary(
        resolved_preference,
        mode=preference_mode,
    )

    top_k = _clamp_int(int(setting("MATCH_TOP_K_RETURN", 30)), 1, 100)
    llm_pool_k_cfg = _clamp_int(int(setting("MATCH_LLM_POOL_K", 20)), 5, 100)
    # 精排池独立于粗排返回数。粗排可以返回 30～100 条，但送给模型的候选
    # 固定封顶 20 条，避免大提示导致交互请求频繁超时。
    llm_pool_k = _effective_llm_pool_k(llm_pool_k_cfg)

    scan_cap = max(
        llm_pool_k,
        min(
            int(setting("MATCH_PREVIEW_MAX_SCAN", 2000)),
            int(current_app.config.get("MATCH_PREVIEW_MAX_SCAN_HARD", 8000)),
        ),
    )

    q = str(body.get("q") or "").strip()
    location_q = str(body.get("location_q") or "").strip()
    match_goal = _parse_match_goal(body)

    try:
        rows = _fetch_jobs_for_match(q=q, location_q=location_q, cap=scan_cap)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("match_preview_neo4j_query_failed")
        return None, "岗位数据服务暂时不可用，请稍后重试", 503

    student_scores = profile["scores"]
    student_conf = profile["confidences"]

    cfg = settings_view()
    shape_w = float(cfg.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    margin_fit = float(cfg.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
    margin_stretch = float(cfg.get("MATCH_GAP_SOFT_MARGIN_STRETCH", 10.0))
    soft_margin = margin_stretch if match_goal == "stretch" else margin_fit

    ranked: List[Dict[str, Any]] = []
    for row in rows:
        card = serialize_job_row(row)
        ms, wg, gaps, shape_r = _coarse_morphology_match(
            student_scores,
            student_conf,
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
    min_axes = int(setting("MATCH_PREFERENCE_MIN_AXES", 2))
    min_confidence = float(setting("MATCH_PREFERENCE_MIN_CONFIDENCE", 0.4))
    preference_available_count = 0
    workstyle_evidence_count = 0
    for card in ranked:
        preview = card.get("match_preview")
        if isinstance(preview, dict):
            workstyle = card.get("workstyle") if isinstance(card.get("workstyle"), dict) else None
            if workstyle and int(workstyle.get("evidenced_axis_count") or 0) > 0:
                workstyle_evidence_count += 1
            if preference_mode in {"explain", "tie_break"} and resolved_preference.get("status") == "measured":
                preference_fit = build_preference_fit(
                    resolved_preference.get("snapshot"),
                    workstyle,
                    min_axes=min_axes,
                    min_confidence=min_confidence,
                )
            else:
                preference_fit = _preference_fit_unavailable(preference_context)
            preview["preference_fit"] = preference_fit
            if preference_fit.get("status") == "available":
                preference_available_count += 1
    coverage = preference_available_count / len(ranked) if ranked else 0.0
    ranking_enabled = bool(setting("MATCH_PREFERENCE_TIE_BREAK_ENABLED", False))
    coverage_threshold = float(setting("MATCH_PREFERENCE_TIE_BREAK_MIN_COVERAGE", 0.6))
    max_ability_gap = float(setting("MATCH_PREFERENCE_TIE_BREAK_MAX_ABILITY_GAP", 3.0))
    experiment_percent = int(setting("MATCH_PREFERENCE_TIE_BREAK_EXPERIMENT_PERCENT", 50))
    variant, bucket = experiment_variant(int(jwt_user_id or 0), experiment_percent)
    ranking_diff: Dict[str, Any] = {
        "version": PREFERENCE_RANKING_VERSION,
        "original_ability_order": [str(card.get("id") or "") for card in ranked],
        "preference_order": [str(card.get("id") or "") for card in ranked],
        "changes": [],
        "changed_jobs": 0,
        "max_ability_gap": max_ability_gap,
    }
    ranking_reason = "not_requested"
    ranking_eligible = False
    if preference_mode == "tie_break":
        if not ranking_enabled:
            ranking_reason = "system_disabled"
        elif resolved_preference.get("status") != "measured":
            ranking_reason = "missing_user_profile"
        elif coverage < coverage_threshold:
            ranking_reason = "insufficient_workstyle_coverage"
        elif variant != "tie_break":
            ranking_reason = "experiment_control"
            ranking_eligible = True
        else:
            ranking_eligible = True
            ranking_reason = "applied"
            ranking_diff = apply_preference_tie_break(ranked, max_ability_gap=max_ability_gap)
    else:
        for index, card in enumerate(ranked, start=1):
            preview = card.get("match_preview") or {}
            preview["ability_rank"] = index
            preview["preference_rank"] = index

    top = ranked[:top_k]

    llm_pool = ranked[: min(llm_pool_k, len(ranked))]

    data_out: Dict[str, Any] = {
        "student": {
            "id": profile.get("id"),
            "display_name": profile.get("display_name"),
            "vector_kind": profile.get("vector_kind"),
            "scores": profile["scores"],
            "confidences": profile["confidences"],
            "score_avg": profile.get("score_avg"),
            "conf_avg": profile.get("conf_avg"),
            "education": profile.get("education"),
            "city_pref": profile.get("city_pref"),
            "skills_hint": profile.get("skills_hint"),
        },
        "filters": {"q": q, "location_q": location_q, "match_goal": match_goal},
        "scoring": {
            "method": "morphology_soft_gap",
            "shape_weight": shape_w,
            "soft_margin": soft_margin,
            "pearson_across_dims": "radar profile similarity (trend across 8 dimensions)",
            "soft_surplus": "per-dim max(0, job - student - soft_margin), weighted like dim_weights",
            "dim_weights": "min(student_conf, job_conf) per dimension, floor 0.08",
            "match_goal": match_goal,
            "coarse_order": (
                "match_score_desc"
                if match_goal == "fit"
                else "stretch: tier by match_score floor then w_match*match_score+w_job*job_score_avg desc"
            ),
        },
        "stats": {
            "scanned": len(rows),
            "scan_cap": scan_cap,
            "returned": len(top),
            "match_top_k_return": top_k,
            "match_llm_pool_k": llm_pool_k,
            "llm_pool_size": len(llm_pool),
        },
        "jobs": top,
        "preference_context": {
            **preference_context,
            "algorithm_version": PREFERENCE_FIT_ALGORITHM_VERSION,
            "workstyle_snapshot_version": WORKSTYLE_SNAPSHOT_VERSION,
            "minimum_evidenced_axes": min_axes,
            "minimum_fit_confidence": min_confidence,
            "jobs_with_workstyle_evidence": workstyle_evidence_count,
            "jobs_with_preference_fit": preference_available_count,
            "workstyle_coverage": round(coverage, 4),
            "tie_break": {
                "requested": preference_mode == "tie_break",
                "eligible": ranking_eligible,
                "applied": ranking_reason == "applied",
                "reason": ranking_reason,
                "system_enabled": ranking_enabled,
                "minimum_coverage": coverage_threshold,
                "max_ability_gap": max_ability_gap,
                "experiment_key": PREFERENCE_EXPERIMENT_KEY,
                "experiment_variant": variant,
                "experiment_bucket": bucket,
                "ranking_version": PREFERENCE_RANKING_VERSION,
                **ranking_diff,
            },
            "influenced_ranking": ranking_reason == "applied" and bool(ranking_diff.get("changes")),
        },
    }

    refine_with_llm = _truthy_refine_llm(body)
    if refine_with_llm:
        api_key = str(setting("DEEPSEEK_API_KEY", "") or "").strip()
        if not api_key:
            local_payload = _local_refine_top5(profile, llm_pool, match_goal=match_goal)
            data_out["llm"] = {
                "ok": bool(local_payload["top5"]),
                "error_code": "not_configured",
                "error": "云端 AI 精排尚未配置，已自动切换为本地八维增强排序。",
                "notice": "云端 AI 精排尚未配置；当前 Top 5 由本地八维差距算法生成，可正常比较岗位。",
                "fallback_mode": "local",
                "model": local_payload["model"],
                "pool_size": local_payload["pool_size"],
                "top5": local_payload["top5"],
                "retry_attempted": False,
                "degraded": True,
                "fallback_reason": "not_configured",
            }
        else:
            model = str(setting("MATCH_DEEPSEEK_MODEL", "deepseek-v4-flash"))
            llm_payload, llm_meta = _refine_with_timeout_fallback(
                profile,
                llm_pool,
                api_key=api_key,
                model=model,
                configured_timeout=float(setting("MATCH_LLM_TIMEOUT_SECONDS", 90.0)),
                match_goal=match_goal,
            )
            if not llm_payload:
                current_app.logger.warning(
                    "match_llm_refine_failed code=%s retry=%s diagnostic=%s",
                    llm_meta.get("error_code"),
                    llm_meta.get("retry_attempted"),
                    llm_meta.get("diagnostic"),
                )
                local_payload = _local_refine_top5(profile, llm_pool, match_goal=match_goal)
                data_out["llm"] = {
                    "ok": bool(local_payload["top5"]),
                    **{key: value for key, value in llm_meta.items() if key != "diagnostic"},
                    "notice": (
                        f"{llm_meta.get('error')}系统已自动切换为本地八维增强排序；"
                        "推荐仍可使用，稍后可重试云端 AI 文案。"
                    ),
                    "fallback_mode": "local",
                    "fallback_reason": llm_meta.get("error_code") or "unknown",
                    "model": local_payload["model"],
                    "pool_size": local_payload["pool_size"],
                    "top5": local_payload["top5"],
                    "degraded": True,
                }
            else:
                data_out["llm"] = {
                    "ok": True,
                    "model": llm_payload.get("model"),
                    "pool_size": llm_payload.get("pool_size"),
                    "top5": llm_payload.get("top5") or [],
                    "raw_snippet": llm_payload.get("raw_snippet"),
                    **llm_meta,
                }

    # 两阶段前端会先请求一次不落库的粗排，避免同一次匹配产生两条历史记录。
    if body.get("persist_snapshot", True) is not False:
        try:
            persist_match_snapshot(
                jwt_user_id=jwt_user_id,
                resume_id=_safe_int_or_none(body.get("resume_id")),
                data_out=data_out,
                refine_with_llm=refine_with_llm,
                settings_revision=body.get("_settings_revision"),
                config_snapshot=body.get("_config_snapshot") or {},
                preference_snapshot=resolved_preference.get("snapshot"),
                preference_context=data_out.get("preference_context") or preference_context,
            )
        except Exception as exc:  # noqa: BLE001
            # 不影响主流程返回，错误仅透出到 llm block 旁注
            data_out["snapshot_warning"] = f"match_snapshot_persist_failed:{exc}"

    return data_out, None, 200
