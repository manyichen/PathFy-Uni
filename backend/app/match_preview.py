"""
人岗匹配：八维加权缺口粗排（M1）；可选 DeepSeek 在候选池上精排 Top5 与文字分析（M2）。

Neo4j 使用 NEO4J_*；DeepSeek 使用 DEEPSEEK_API_KEY（可与 tools/job_eval/.env 保持一致后复制到 backend/.env）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from flask import Blueprint, current_app, jsonify, request

from .jobs import CONF_KEYS, DIM_KEYS, _driver, _neo4j_settings, _serialize_row
from .match_llm_refine import refine_top5_deepseek
from .mock_capability_profiles import _serialize_profile, get_mock_profile_raw

match_bp = Blueprint("match", __name__, url_prefix="/api/match")

_DIM_TO_CONF: Dict[str, str] = {d: c for d, c in zip(DIM_KEYS, CONF_KEYS)}


def _weighted_gap_match(
    student_scores: Dict[str, float],
    student_conf: Dict[str, float],
    job_scores: Dict[str, float],
    job_conf: Dict[str, float],
) -> Tuple[float, float, Dict[str, float]]:
    """按维 min(学生置信,岗位置信) 加权，惩罚 max(0, 岗位需求-学生供给)。返回 (match_score 0-100, weighted_gap, per_dim_gap)。"""
    weighted_sum = 0.0
    w_sum = 0.0
    gaps: Dict[str, float] = {}
    for dk in DIM_KEYS:
        ck = _DIM_TO_CONF[dk]
        s = float(student_scores.get(dk, 0.0))
        jv = float(job_scores.get(dk, 0.0))
        sc = float(student_conf.get(ck, 0.5))
        jc = float(job_conf.get(ck, 0.5))
        gap = max(0.0, jv - s)
        gaps[dk] = round(gap, 2)
        w = max(0.08, min(sc, jc))
        weighted_sum += w * gap
        w_sum += w
    weighted_gap = weighted_sum / w_sum if w_sum > 0 else 0.0
    weighted_gap = min(weighted_gap, 100.0)
    alpha = 1.0
    match_score = max(0.0, min(100.0, 100.0 - alpha * weighted_gap))
    return round(match_score, 2), round(weighted_gap, 2), gaps


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


def _resolve_student_profile(body: Dict[str, Any]) -> Tuple[Dict[str, Any] | None, str | None]:
    """返回 (serialized_profile, error_message)。"""
    profile_id = str(body.get("profile_id") or "").strip()
    if profile_id:
        raw = get_mock_profile_raw(profile_id)
        if not raw:
            return None, f"未知 profile_id: {profile_id}"
        return _serialize_profile(raw), None

    scores = body.get("scores")
    if isinstance(scores, dict) and scores:
        default_conf = {ck: 0.55 for ck in CONF_KEYS}
        conf_in = body.get("confidences")
        if isinstance(conf_in, dict):
            default_conf.update({k: float(v) for k, v in conf_in.items() if k in CONF_KEYS})
        inline = {
            "id": "inline",
            "display_name": str(body.get("display_name") or "内联测试画像"),
            "scores": scores,
            "confidences": default_conf,
        }
        return _serialize_profile(inline), None

    return None, "请提供 profile_id（虚构画像）或 scores 对象"


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _truthy_refine_llm(body: Dict[str, Any]) -> bool:
    v = body.get("refine_with_llm")
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
        return True
    return False


@match_bp.post("/preview")
def match_preview():
    uri, user, password, _database = _neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD，无法查询岗位"}), 500

    body = request.get_json(silent=True) or {}
    profile, err = _resolve_student_profile(body)
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

    try:
        rows = _fetch_jobs_for_match(q=q, location_q=location_q, cap=scan_cap)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "message": f"Neo4j 查询失败: {exc}"}), 500

    student_scores = profile["scores"]
    student_conf = profile["confidences"]

    ranked: List[Dict[str, Any]] = []
    for row in rows:
        card = _serialize_row(row)
        ms, wg, gaps = _weighted_gap_match(
            student_scores,
            student_conf,
            card["scores"],
            card["confidences"],
        )
        ranked.append(
            {
                **card,
                "match_preview": {
                    "match_score": ms,
                    "weighted_gap": wg,
                    "dimension_gaps": gaps,
                },
            }
        )

    ranked.sort(key=lambda x: float(x["match_preview"]["match_score"]), reverse=True)
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
        "filters": {"q": q, "location_q": location_q},
        "scoring": {
            "method": "weighted_negative_gap",
            "alpha": 1.0,
            "dim_weights": "min(student_conf, job_conf) per dimension, floor 0.08",
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
