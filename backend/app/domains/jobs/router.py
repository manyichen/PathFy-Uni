import hashlib
import json
from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, request

from app.infrastructure.neo4j import (
    CONF_KEYS,
    DIM_KEYS,
    neo4j_driver,
    neo4j_settings,
    serialize_job_row,
)
from app.infrastructure.llm import call_ark_json
from app.infrastructure.salary import (
    cypher_job_salary_display,
    cypher_job_salary_raw,
    parse_salary_range,
)

_SALARY_DISP = cypher_job_salary_display()
_SALARY_RAW = cypher_job_salary_raw()

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")

_JOBS_FILTER_WHERE = """
    (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
"""

_JOBS_RETURN_FIELDS = f"""
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      {_SALARY_DISP},
      {_SALARY_RAW},
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

_JOBS_SHUFFLE_CACHE: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
_JOBS_SHUFFLE_CACHE_ORDER: List[Tuple[str, str]] = []
_MAX_JOBS_SHUFFLE_CACHES = 32


def _normalize_jobs_sort(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if value in {"random", "score_asc", "score_desc"}:
        return value
    return "default"


def _jobs_order_clause(sort_mode: str) -> str:
    if sort_mode == "score_asc":
        return "ORDER BY total_score ASC, title ASC"
    return "ORDER BY total_score DESC, title ASC"


def _jobs_shuffle_key(job_id: str, seed: str) -> str:
    return hashlib.md5(f"{seed}:{job_id}".encode("utf-8")).hexdigest()


def _shuffled_job_rows(keyword: str, seed: str) -> List[Dict[str, Any]]:
    cache_key = (keyword, seed)
    cached = _JOBS_SHUFFLE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    uri, user, password, database = neo4j_settings()
    query = f"""
    MATCH (j:Job)
    WHERE {_JOBS_FILTER_WHERE}
    WITH j,
      (coalesce(j.cap_req_theory, 0.0) +
       coalesce(j.cap_req_cross, 0.0) +
       coalesce(j.cap_req_practice, 0.0) +
       coalesce(j.cap_req_digital, 0.0) +
       coalesce(j.cap_req_innovation, 0.0) +
       coalesce(j.cap_req_teamwork, 0.0) +
       coalesce(j.cap_req_social, 0.0) +
       coalesce(j.cap_req_growth, 0.0)) AS total_score
    RETURN
      {_JOBS_RETURN_FIELDS},
      total_score
    """
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"q": keyword})]
    rows.sort(key=lambda row: _jobs_shuffle_key(str(row.get("id") or ""), seed))
    _JOBS_SHUFFLE_CACHE[cache_key] = rows
    _JOBS_SHUFFLE_CACHE_ORDER.append(cache_key)
    while len(_JOBS_SHUFFLE_CACHE_ORDER) > _MAX_JOBS_SHUFFLE_CACHES:
        old_key = _JOBS_SHUFFLE_CACHE_ORDER.pop(0)
        _JOBS_SHUFFLE_CACHE.pop(old_key, None)
    return rows


def _jobs_page_payload(
    rows: List[Dict[str, Any]],
    *,
    page: int,
    page_size: int,
    sort_mode: str,
    seed: str = "",
) -> Dict[str, Any]:
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page_num = min(max(1, page), total_pages)
    start = (page_num - 1) * page_size
    page_rows = rows[start : start + page_size]
    data = [serialize_job_row(r) for r in page_rows]
    payload: Dict[str, Any] = {
        "jobs": data,
        "total": total,
        "page": page_num,
        "page_size": page_size,
        "total_pages": total_pages,
        "sort": sort_mode,
    }
    if sort_mode == "random" and seed:
        payload["seed"] = seed
    return payload


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fetch_job_for_analysis(session, job_id):
    row = session.run(
        f"""
        MATCH (j:Job)
        WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
        OPTIONAL MATCH (j)-[:REQUIRES]->(req)
        RETURN
          coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
          coalesce(j.title, j.name, '未命名岗位') AS title,
          {_SALARY_DISP},
          {_SALARY_RAW},
          coalesce(j.company, '未知公司') AS company,
          coalesce(j.location, '未知地点') AS location,
          coalesce(j.demand, '') AS demand,
          coalesce(j.experience_text, '') AS experience_text,
          coalesce(j.experience_years, 0.0) AS experience_years,
          coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
          coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
          coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
          coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
          coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
          coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
          coalesce(j.cap_req_social, 0.0) AS cap_req_social,
          coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
          collect(DISTINCT coalesce(req.name, '')) AS requirement_names
        LIMIT 1
        """,
        {"job_id": job_id},
    ).single()
    return dict(row) if row else None


def _build_transition_analysis(from_row, to_row):
    from_reqs = {str(x).strip() for x in (from_row.get("requirement_names") or []) if str(x).strip()}
    to_reqs = {str(x).strip() for x in (to_row.get("requirement_names") or []) if str(x).strip()}

    overlap = sorted(from_reqs & to_reqs)
    missing = sorted(to_reqs - from_reqs)
    transferable = sorted(from_reqs - to_reqs)

    cap_gaps = []
    for key in DIM_KEYS:
        from_val = round(_safe_float(from_row.get(key)), 2)
        to_val = round(_safe_float(to_row.get(key)), 2)
        cap_gaps.append(
            {
                "dimension": key,
                "from": from_val,
                "to": to_val,
                "gap": round(to_val - from_val, 2),
            }
        )
    cap_gaps.sort(key=lambda x: x["gap"], reverse=True)

    from_salary = parse_salary_range(from_row.get("salary_raw") or from_row.get("salary"))
    to_salary = parse_salary_range(to_row.get("salary_raw") or to_row.get("salary"))
    salary_delta = None
    if from_salary.get("monthly_min") is not None and to_salary.get("monthly_min") is not None:
        salary_delta = round(float(to_salary["monthly_min"]) - float(from_salary["monthly_min"]), 2)

    exp_gap = round(_safe_float(to_row.get("experience_years")) - _safe_float(from_row.get("experience_years")), 2)

    return {
        "score_summary": {
            "experience_gap": exp_gap,
            "salary_min_delta": salary_delta,
            "overlap_count": len(overlap),
            "missing_count": len(missing),
        },
        "skill_overlap": overlap[:20],
        "skill_missing": missing[:20],
        "transferable_skills": transferable[:20],
        "capability_gaps": cap_gaps,
    }


def _fallback_transition_advice(from_row, to_row, analysis):
    major_gaps = [g for g in analysis["capability_gaps"] if g["gap"] > 8][:3]
    top_gap_names = [g["dimension"].replace("cap_req_", "") for g in major_gaps]
    if not top_gap_names:
        top_gap_names = ["digital", "innovation"]

    return {
        "summary": f"从{from_row.get('title', '当前岗位')}转向{to_row.get('title', '目标岗位')}总体可行，但需要补齐目标岗位关键能力与要求。",
        "feasibility": "中",
        "advantages": analysis["skill_overlap"][:5],
        "gaps": analysis["skill_missing"][:5],
        "learning_plan": [
            f"第1-2周：针对 {top_gap_names[0]} 做岗位 JD 定向学习与项目拆解。",
            "第3-5周：完成 1 个可展示的业务小项目并沉淀文档。",
            "第6-8周：按目标岗位要求补齐案例表达与面试题训练。",
        ],
        "risk_alerts": [
            "若目标岗位经验门槛明显更高，建议先投递相邻层级岗位。",
            "若技能缺口超过 5 项，建议分阶段转岗而非一次跳转。",
        ],
        "final_recommendation": "建议先进行 4-8 周补齐，再发起正式转岗投递。",
    }


def _llm_transition_advice(from_row, to_row, analysis):
    try:
        llm_result = call_ark_json(
            system_prompt=(
                "你是职业发展顾问。"
                "你会基于两个岗位信息和量化差异，给出转岗分析建议。"
                "只输出 JSON 对象，不要输出解释。"
                "字段必须包含: summary, feasibility, advantages, gaps, learning_plan, risk_alerts, final_recommendation。"
                "feasibility 仅允许: 高|中|低。"
                "advantages/gaps/learning_plan/risk_alerts 必须是字符串数组。"
            ),
            payload={"from_job": from_row, "to_job": to_row, "analysis": analysis},
        )
        if not llm_result:
            return _fallback_transition_advice(from_row, to_row, analysis)
        return {
            "summary": str(llm_result.get("summary") or ""),
            "feasibility": str(llm_result.get("feasibility") or "中"),
            "advantages": [str(x) for x in (llm_result.get("advantages") or []) if str(x).strip()][:8],
            "gaps": [str(x) for x in (llm_result.get("gaps") or []) if str(x).strip()][:8],
            "learning_plan": [str(x) for x in (llm_result.get("learning_plan") or []) if str(x).strip()][:8],
            "risk_alerts": [str(x) for x in (llm_result.get("risk_alerts") or []) if str(x).strip()][:8],
            "final_recommendation": str(llm_result.get("final_recommendation") or ""),
        }
    except Exception:
        return _fallback_transition_advice(from_row, to_row, analysis)


@jobs_bp.get("")
def list_jobs():
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    page = max(1, int(request.args.get("page", "1")))
    page_size = max(1, min(int(request.args.get("page_size", "40")), 200))
    skip = (page - 1) * page_size
    keyword = (request.args.get("q") or "").strip()
    sort_mode = _normalize_jobs_sort(request.args.get("sort") or "")
    seed = str(request.args.get("seed") or "").strip()

    if sort_mode == "random":
        if not seed:
            return jsonify({"ok": False, "message": "随机排序需要提供 seed"}), 400
        rows = _shuffled_job_rows(keyword, seed)
        return jsonify({"ok": True, "data": _jobs_page_payload(rows, page=page, page_size=page_size, sort_mode=sort_mode, seed=seed)})

    count_query = f"""
    MATCH (j:Job)
    WHERE {_JOBS_FILTER_WHERE}
    RETURN count(j) AS total
    """

    list_query = f"""
    MATCH (j:Job)
    WHERE {_JOBS_FILTER_WHERE}
    WITH j,
      (coalesce(j.cap_req_theory, 0.0) +
       coalesce(j.cap_req_cross, 0.0) +
       coalesce(j.cap_req_practice, 0.0) +
       coalesce(j.cap_req_digital, 0.0) +
       coalesce(j.cap_req_innovation, 0.0) +
       coalesce(j.cap_req_teamwork, 0.0) +
       coalesce(j.cap_req_social, 0.0) +
       coalesce(j.cap_req_growth, 0.0)) AS total_score
    RETURN
      {_JOBS_RETURN_FIELDS}
    {_jobs_order_clause(sort_mode)}
    SKIP $skip
    LIMIT $limit
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        total_row = session.run(count_query, {"q": keyword}).single()
        total = int((total_row or {}).get("total") or 0)
        rows = [
            dict(r)
            for r in session.run(
                list_query,
                {"limit": page_size, "skip": skip, "q": keyword},
            )
        ]

    data = [serialize_job_row(r) for r in rows]
    total_pages = max(1, (total + page_size - 1) // page_size)
    return jsonify(
        {
            "ok": True,
            "data": {
                "jobs": data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "sort": sort_mode,
            },
        }
    )


@jobs_bp.get("/options")
def list_job_options():
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    page = max(1, int(request.args.get("page", "1")))
    page_size = max(1, min(int(request.args.get("page_size", "20")), 100))
    skip = (page - 1) * page_size
    keyword = (request.args.get("q") or "").strip()

    count_query = """
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
    RETURN count(j) AS total
    """

    list_query = f"""
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      {_SALARY_DISP},
      coalesce(j.experience_years, 0.0) AS experience_years
    ORDER BY title ASC, company ASC
    SKIP $skip
    LIMIT $limit
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        total_row = session.run(count_query, {"q": keyword}).single()
        total = int((total_row or {}).get("total") or 0)
        rows = [
            dict(r)
            for r in session.run(
                list_query,
                {"limit": page_size, "skip": skip, "q": keyword},
            )
        ]

    total_pages = max(1, (total + page_size - 1) // page_size)
    return jsonify(
        {
            "ok": True,
            "data": {
                "jobs": rows,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
        }
    )


@jobs_bp.get("/<path:job_id>")
def job_detail(job_id: str):
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    detail_query = f"""
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    OPTIONAL MATCH (j)-[:REQUIRES]->(req)
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      {_SALARY_DISP},
      {_SALARY_RAW},
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.industry, '') AS industry,
      coalesce(j.company_type, '') AS company_type,
      coalesce(j.company_size, '') AS company_size,
      coalesce(j.company_detail, '') AS company_detail,
      coalesce(j.demand, '') AS demand,
      coalesce(j.experience_text, '') AS experience_text,
      coalesce(j.experience_years, 0.0) AS experience_years,
      coalesce(j.internship_req, '') AS internship_req,
      coalesce(j.updated_date, '') AS updated_date,
      coalesce(j.source_url, '') AS source_url,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_evidence, []) AS cap_evidence,
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
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth,
      collect(DISTINCT {{
        name: coalesce(req.name, ''),
        label: head(labels(req)),
        level: coalesce(req.level, '')
      }}) AS requirements
    LIMIT 1
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        row = session.run(detail_query, {"job_id": job_id}).single()

    if not row:
        return jsonify({"ok": False, "message": "岗位不存在"}), 404

    raw = dict(row)
    detail = serialize_job_row(raw)
    detail.update(
        {
            "industry": raw.get("industry") or "",
            "company_type": raw.get("company_type") or "",
            "company_size": raw.get("company_size") or "",
            "company_detail": raw.get("company_detail") or "",
            "demand": raw.get("demand") or "",
            "experience_text": raw.get("experience_text") or "",
            "experience_years": round(float(raw.get("experience_years") or 0), 2),
            "internship_req": raw.get("internship_req") or "",
            "updated_date": raw.get("updated_date") or "",
            "source_url": raw.get("source_url") or "",
            "cap_evidence": raw.get("cap_evidence") or [],
            "requirements": sorted(
                [
                    {
                        "name": str(item.get("name") or "").strip(),
                        "label": str(item.get("label") or "").strip(),
                        "level": str(item.get("level") or "").strip(),
                    }
                    for item in (raw.get("requirements") or [])
                    if str(item.get("name") or "").strip()
                ],
                key=lambda x: (x["label"], x["name"]),
            ),
        }
    )

    return jsonify({"ok": True, "data": detail})


@jobs_bp.post("/transition-analysis")
def transition_analysis():
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    payload = request.get_json(silent=True) or {}
    from_job_id = str(payload.get("from_job_id") or "").strip()
    to_job_id = str(payload.get("to_job_id") or "").strip()
    if not from_job_id or not to_job_id:
        return jsonify({"ok": False, "message": "from_job_id 和 to_job_id 不能为空"}), 400
    if from_job_id == to_job_id:
        return jsonify({"ok": False, "message": "请至少选择两个不同岗位"}), 400

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        from_row = _fetch_job_for_analysis(session, from_job_id)
        to_row = _fetch_job_for_analysis(session, to_job_id)

    if not from_row or not to_row:
        return jsonify({"ok": False, "message": "岗位不存在"}), 404

    analysis = _build_transition_analysis(from_row, to_row)
    advice = _llm_transition_advice(from_row, to_row, analysis)

    return jsonify(
        {
            "ok": True,
            "data": {
                "from_job": {
                    "id": from_row["id"],
                    "title": from_row["title"],
                    "company": from_row["company"],
                    "location": from_row["location"],
                    "salary": from_row["salary"],
                },
                "to_job": {
                    "id": to_row["id"],
                    "title": to_row["title"],
                    "company": to_row["company"],
                    "location": to_row["location"],
                    "salary": to_row["salary"],
                },
                "analysis": analysis,
                "advice": advice,
            },
        }
    )


@jobs_bp.get("/<path:job_id>/promotion-path")
def get_promotion_path(job_id: str):
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    try:
        max_depth = int(request.args.get("max_depth", "4"))
    except ValueError:
        max_depth = 4
    try:
        max_paths = int(request.args.get("max_paths", "3"))
    except ValueError:
        max_paths = 3

    max_depth = max(1, min(max_depth, 8))
    max_paths = max(1, min(max_paths, 8))
    promotion_limit = max(max_paths, 12)

    start_query = f"""
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.company, '') AS company,
      coalesce(j.location, '') AS location,
      {_SALARY_DISP},
      {_SALARY_RAW},
      coalesce(j.experience_years, 0.0) AS experience_years
    LIMIT 1
    """

    promotion_query = """
    MATCH (start:Job)
    WHERE coalesce(start.job_key, start.job_code, start.name, start.title, elementId(start)) = $job_id
    WITH start, trim(coalesce(start.title, start.name, '')) AS title_name
    OPTIONAL MATCH (start)-[:HAS_TITLE]->(direct_jt:JobTitle)
    OPTIONAL MATCH (fallback_jt:JobTitle {name: title_name})
    WITH title_name, coalesce(direct_jt, fallback_jt) AS jt
    WHERE jt IS NOT NULL
    MATCH (promotion:JobPromotion)-[:FOR_JOB_TITLE]->(jt)
    RETURN
      coalesce(jt.name, title_name) AS from_title,
      coalesce(promotion.promotion_id, promotion.name, '') AS id,
      coalesce(promotion.to_title, promotion.stage3_job_title, promotion.title, promotion.name, '未命名岗位') AS to_title,
      coalesce(promotion.title, promotion.name, '') AS promotion_name,
      coalesce(promotion.stage1, '') AS stage1,
      coalesce(promotion.stage2, '') AS stage2,
      coalesce(promotion.stage3, '') AS stage3,
      coalesce(promotion.stage3_job_title, '') AS stage3_job_title,
      coalesce(promotion.confidence, 0.0) AS confidence,
      coalesce(promotion.rationale, '') AS rationale
    ORDER BY confidence DESC, to_title ASC
    LIMIT $limit
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        start_row = session.run(start_query, {"job_id": job_id}).single()
        if not start_row:
            return jsonify({"ok": False, "message": "岗位不存在"}), 404

        promotion_rows = [
            dict(r)
            for r in session.run(
                promotion_query,
                {"job_id": job_id, "limit": promotion_limit},
            )
        ]

    start_job = dict(start_row)
    normalized_paths = []
    next_steps = []

    for item in promotion_rows:
        confidence = round(_safe_float(item.get("confidence")), 4)
        title = str(item.get("to_title") or item.get("stage3_job_title") or "未命名岗位")
        target = {
            "id": f"jobtitle::{title}",
            "title": title,
            "company": "JobTitle",
            "location": "",
            "salary": "",
            "experience_years": 0.0,
            "confidence": confidence,
            "rationale": str(item.get("rationale") or ""),
            "stage1": str(item.get("stage1") or ""),
            "stage2": str(item.get("stage2") or ""),
            "stage3": str(item.get("stage3") or ""),
            "stage3_job_title": str(item.get("stage3_job_title") or ""),
        }
        next_steps.append(target)

        if len(normalized_paths) >= max_paths:
            continue
        normalized_paths.append(
            {
                "hops": 1,
                "nodes": [start_job, target],
                "edges": [
                    {
                        "source": "JobPromotion",
                        "reason": str(item.get("rationale") or item.get("promotion_name") or ""),
                        "confidence": confidence,
                        "stage1": str(item.get("stage1") or ""),
                        "stage2": str(item.get("stage2") or ""),
                        "stage3": str(item.get("stage3") or ""),
                        "stage3_job_title": str(item.get("stage3_job_title") or ""),
                    }
                ],
            }
        )

    return jsonify(
        {
            "ok": True,
            "data": {
                "job": start_job,
                "paths": normalized_paths,
                "next_steps": next_steps,
                "meta": {
                    "source": "JobPromotion",
                    "job_title": promotion_rows[0]["from_title"] if promotion_rows else start_job.get("title", ""),
                    "max_depth": max_depth,
                    "max_paths": max_paths,
                },
            },
        }
    )
