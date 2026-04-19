"""
人岗匹配：八维轮廓 Pearson + 软 surplus 加权粗排（M1）；可选 DeepSeek 在候选池上精排 Top5 与文字分析（M2）。

Neo4j 使用 NEO4J_*；DeepSeek 使用 DEEPSEEK_API_KEY（可与 tools/job_eval/.env 保持一致后复制到 backend/.env）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from flask import Blueprint, current_app, jsonify, request

from .auth import get_bearer_user_id
from .db import db_cursor
from .jobs import CONF_KEYS, DIM_KEYS, _driver, _neo4j_settings, _serialize_row
from .match_llm_refine import refine_top5_deepseek
from .capability_profile_serialize import serialize_capability_profile

match_bp = Blueprint("match", __name__, url_prefix="/api/match")

_DIM_TO_CONF: Dict[str, str] = {d: c for d, c in zip(DIM_KEYS, CONF_KEYS)}


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
    uri, user, password, database = _neo4j_settings()
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
    LIMIT $cap
    """
    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        return [dict(r) for r in session.run(query, {"q": q, "loc": location_q, "cap": int(cap)})]


def _student_row_to_serialized_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    """将 student_resume 行转为已序列化学生画像（含 cap_conf_*）。"""
    scores = {k: float(row[k]) for k in DIM_KEYS}
    confidences: Dict[str, float] = {}
    for ck in CONF_KEYS:
        v = row.get(ck)
        confidences[ck] = float(v) if v is not None else 0.55
    excerpt = (row.get("resume_text") or "")[:1200]
    major = (row.get("major") or "").strip()
    raw: Dict[str, Any] = {
        "id": str(row["id"]),
        "display_name": (row.get("name") or "能力画像").strip() or "能力画像",
        "education": major or None,
        "city_pref": None,
        "skills_hint": [],
        "resume_excerpt": excerpt,
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
                    SELECT id, user_id, name, major, resume_text,
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


def _sort_ranked_for_goal(ranked: List[Dict[str, Any]], match_goal: str) -> None:
    """粗排结果排序：fit 按匹配分；stretch 在可达前提下抬高岗位八维均分（需求强度）。"""
    if not ranked:
        return
    if match_goal != "stretch":
        ranked.sort(key=lambda x: float(x["match_preview"]["match_score"]), reverse=True)
        return

    floor = float(current_app.config.get("MATCH_STRETCH_MATCH_SCORE_FLOOR", 38))
    w_ms = float(current_app.config.get("MATCH_STRETCH_SORT_W_MATCH", 0.32))
    w_jq = float(current_app.config.get("MATCH_STRETCH_SORT_W_JOB_AVG", 0.68))

    def sort_key(card: Dict[str, Any]) -> Tuple[int, float, float]:
        ms = float((card.get("match_preview") or {}).get("match_score") or 0.0)
        jq = float(card.get("score_avg") or 0.0)
        if ms < floor:
            return (1, -ms, -jq)
        comp = w_ms * ms + w_jq * jq
        return (0, -comp, -ms)

    ranked.sort(key=sort_key)


@match_bp.post("/preview")
def match_preview():
    uri, user, password, _database = _neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD，无法查询岗位"}), 500

    body = request.get_json(silent=True) or {}
    profile, err = _resolve_student_profile(body, get_bearer_user_id())
    if err or not profile:
        return jsonify({"ok": False, "message": err or "画像解析失败"}), 400

    top_k = _clamp_int(int(current_app.config.get("MATCH_TOP_K_RETURN", 30)), 1, 100)
    llm_pool_k_cfg = _clamp_int(int(current_app.config.get("MATCH_LLM_POOL_K", 40)), 5, 100)
    llm_pool_k = max(llm_pool_k_cfg, top_k)

    scan_cap = max(
        llm_pool_k,
        min(
            int(current_app.config.get("MATCH_PREVIEW_MAX_SCAN", 2000)),
            int(current_app.config.get("MATCH_PREVIEW_MAX_SCAN_HARD", 8000)),
        ),
    )

    q = str(body.get("q") or "").strip()
    location_q = str(body.get("location_q") or "").strip()
    match_goal = _parse_match_goal(body)

    try:
        rows = _fetch_jobs_for_match(q=q, location_q=location_q, cap=scan_cap)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "message": f"Neo4j 查询失败: {exc}"}), 500

    student_scores = profile["scores"]
    student_conf = profile["confidences"]

    cfg = current_app.config
    shape_w = float(cfg.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    margin_fit = float(cfg.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
    margin_stretch = float(cfg.get("MATCH_GAP_SOFT_MARGIN_STRETCH", 10.0))
    soft_margin = margin_stretch if match_goal == "stretch" else margin_fit

    ranked: List[Dict[str, Any]] = []
    for row in rows:
        card = _serialize_row(row)
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
            "resume_excerpt": profile.get("resume_excerpt"),
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
    }

    if _truthy_refine_llm(body):
        api_key = str(current_app.config.get("DEEPSEEK_API_KEY") or "").strip()
        if not api_key:
            data_out["llm"] = {
                "ok": False,
                "error": "未配置 DEEPSEEK_API_KEY，无法精排。请将 tools/job_eval/.env 中的密钥同步到 backend/.env。",
            }
        else:
            model = str(current_app.config.get("MATCH_DEEPSEEK_MODEL") or "deepseek-chat")
            timeout = float(current_app.config.get("MATCH_LLM_TIMEOUT_SECONDS") or 120.0)
            llm_payload, llm_err = refine_top5_deepseek(
                profile,
                llm_pool,
                api_key=api_key,
                model=model,
                timeout=timeout,
                match_goal=match_goal,
            )
            if llm_err or not llm_payload:
                data_out["llm"] = {
                    "ok": False,
                    "error": llm_err or "unknown_llm_error",
                }
            else:
                data_out["llm"] = {
                    "ok": True,
                    "model": llm_payload.get("model"),
                    "pool_size": llm_payload.get("pool_size"),
                    "top5": llm_payload.get("top5") or [],
                    "raw_snippet": llm_payload.get("raw_snippet"),
                }

    return jsonify({"ok": True, "data": data_out})
