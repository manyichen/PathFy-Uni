import json
import re
from functools import lru_cache

from flask import Blueprint, current_app, jsonify, request
from neo4j import GraphDatabase
from openai import OpenAI

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")

DIM_KEYS = [
    "cap_req_theory",
    "cap_req_cross",
    "cap_req_practice",
    "cap_req_digital",
    "cap_req_innovation",
    "cap_req_teamwork",
    "cap_req_social",
    "cap_req_growth",
]

CONF_KEYS = [
    "cap_conf_theory",
    "cap_conf_cross",
    "cap_conf_practice",
    "cap_conf_digital",
    "cap_conf_innovation",
    "cap_conf_teamwork",
    "cap_conf_social",
    "cap_conf_growth",
]

PROMOTION_EDGE_SOURCES = ["openai_lmstudio"]


@lru_cache(maxsize=1)
def _driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def _neo4j_settings():
    return (
        current_app.config["NEO4J_URI"],
        current_app.config["NEO4J_USER"],
        current_app.config["NEO4J_PASSWORD"],
        current_app.config["NEO4J_DATABASE"],
    )


def _serialize_row(row):
    scores = {}
    for key in DIM_KEYS:
        scores[key] = round(float(row.get(key) or 0), 2)

    confidences = {}
    for key in CONF_KEYS:
        raw = float(row.get(key) or 0)
        raw = min(1.0, max(0.0, raw))
        confidences[key] = round(raw, 4)

    score_avg = round(sum(scores.values()) / len(DIM_KEYS), 2)
    conf_avg = round((sum(confidences.values()) / len(CONF_KEYS)) * 100, 2)
    return {
        "id": row["id"],
        "title": row["title"],
        "salary": row["salary"],
        "company": row["company"],
        "location": row["location"],
        "risk_flags": row.get("risk_flags") or [],
        "scores": scores,
        "confidences": confidences,
        "score_avg": score_avg,
        "conf_avg": conf_avg,
    }


def _normalize_salary_text(text):
    raw = str(text or "").strip().lower()
    raw = raw.replace("k", "千")
    raw = raw.replace("／", "/")
    raw = raw.replace("·", "")
    raw = raw.replace(" ", "")
    return raw


def _parse_salary_range(text):
    raw = str(text or "").strip()
    norm = _normalize_salary_text(raw)
    if not norm:
        return {"monthly_min": None, "monthly_max": None}

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)万", norm)
    if m:
        return {
            "monthly_min": float(m.group(1)) * 10000,
            "monthly_max": float(m.group(2)) * 10000,
        }

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)千", norm)
    if m:
        return {
            "monthly_min": float(m.group(1)) * 1000,
            "monthly_max": float(m.group(2)) * 1000,
        }

    m = re.search(r"(\d+(?:\.\d+)?)万以上", norm)
    if m:
        value = float(m.group(1)) * 10000
        return {"monthly_min": value, "monthly_max": None}

    m = re.search(r"(\d+(?:\.\d+)?)千以上", norm)
    if m:
        value = float(m.group(1)) * 1000
        return {"monthly_min": value, "monthly_max": None}

    return {"monthly_min": None, "monthly_max": None}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_openai_client():
    api_key = current_app.config.get("ARK_API_KEY", "")
    if not api_key:
        return None
    timeout = int(current_app.config.get("AI_LLM_TIMEOUT_SECONDS", 90))
    base_url = str(current_app.config.get("ARK_BASE_URL", "")).strip()
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def _strip_fenced_json(text):
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()


def _llm_json_call(system_prompt, payload):
    client = _build_openai_client()
    if client is None:
        return None

    model = current_app.config.get("ARK_MODEL", "doubao-seed-2-0-mini-260215")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
        stream=False,
        response_format={"type": "json_object"},
    )
    content = (resp.choices[0].message.content or "").strip()
    content = _strip_fenced_json(content)
    data = json.loads(content)
    if not isinstance(data, dict):
        return None
    return data


def _fetch_job_for_analysis(session, job_id):
    row = session.run(
        """
        MATCH (j:Job)
        WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
        OPTIONAL MATCH (j)-[:REQUIRES]->(req)
        RETURN
          coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
          coalesce(j.title, j.name, '未命名岗位') AS title,
          coalesce(j.salary, '薪资面议') AS salary,
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

    from_salary = _parse_salary_range(from_row.get("salary"))
    to_salary = _parse_salary_range(to_row.get("salary"))
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
        llm_result = _llm_json_call(
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
    uri, user, password, database = _neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    page = max(1, int(request.args.get("page", "1")))
    page_size = max(1, min(int(request.args.get("page_size", "40")), 200))
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

    list_query = """
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
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
    ORDER BY total_score DESC, title ASC
    SKIP $skip
    LIMIT $limit
    """

    driver = _driver(uri, user, password)
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

    data = [_serialize_row(r) for r in rows]
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
            },
        }
    )


@jobs_bp.get("/options")
def list_job_options():
    uri, user, password, database = _neo4j_settings()
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

    list_query = """
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
      coalesce(j.salary, '薪资面议') AS salary,
      coalesce(j.experience_years, 0.0) AS experience_years
    ORDER BY title ASC, company ASC
    SKIP $skip
    LIMIT $limit
    """

    driver = _driver(uri, user, password)
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
    uri, user, password, database = _neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    detail_query = """
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    OPTIONAL MATCH (j)-[:REQUIRES]->(req)
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.salary, '薪资面议') AS salary,
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
      collect(DISTINCT {
        name: coalesce(req.name, ''),
        label: head(labels(req)),
        level: coalesce(req.level, '')
      }) AS requirements
    LIMIT 1
    """

    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        row = session.run(detail_query, {"job_id": job_id}).single()

    if not row:
        return jsonify({"ok": False, "message": "岗位不存在"}), 404

    raw = dict(row)
    detail = _serialize_row(raw)
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
    uri, user, password, database = _neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    payload = request.get_json(silent=True) or {}
    from_job_id = str(payload.get("from_job_id") or "").strip()
    to_job_id = str(payload.get("to_job_id") or "").strip()
    if not from_job_id or not to_job_id:
        return jsonify({"ok": False, "message": "from_job_id 和 to_job_id 不能为空"}), 400
    if from_job_id == to_job_id:
        return jsonify({"ok": False, "message": "请至少选择两个不同岗位"}), 400

    driver = _driver(uri, user, password)
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
    uri, user, password, database = _neo4j_settings()
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

    path_query = f"""
    MATCH (start:Job)
    WHERE coalesce(start.job_key, start.job_code, start.name, start.title, elementId(start)) = $job_id
    OPTIONAL MATCH p=(start)-[rels:VERTICAL_UP*1..{max_depth}]->(target:Job)
    WHERE all(r IN rels WHERE coalesce(r.source, '') IN $sources)
    RETURN
      [n in nodes(p) | {{
        id: coalesce(n.job_key, n.job_code, n.name, n.title, elementId(n)),
        title: coalesce(n.title, n.name, '未命名岗位'),
        company: coalesce(n.company, ''),
        experience_years: coalesce(n.experience_years, 0.0)
      }}] AS nodes,
      [r in relationships(p) | {{
        source: coalesce(r.source, ''),
        reason: coalesce(r.reason, ''),
        score_gap: coalesce(r.score_gap, 0.0),
        exp_gap: coalesce(r.exp_gap, 0.0)
      }}] AS edges,
      length(p) AS hops
    ORDER BY hops ASC
    LIMIT {max_paths}
    """

    next_query = """
        MATCH (start:Job)-[r:VERTICAL_UP]->(next:Job)
    WHERE coalesce(start.job_key, start.job_code, start.name, start.title, elementId(start)) = $job_id
            AND coalesce(r.source, '') IN $sources
    RETURN
      coalesce(next.job_key, next.job_code, next.name, next.title, elementId(next)) AS id,
      coalesce(next.title, next.name, '未命名岗位') AS title,
      coalesce(next.company, '') AS company,
      coalesce(next.experience_years, 0.0) AS experience_years,
      coalesce(r.score_gap, 0.0) AS score_gap,
      coalesce(r.exp_gap, 0.0) AS exp_gap
    ORDER BY score_gap DESC, experience_years ASC
    LIMIT 12
    """

    start_query = """
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.company, '') AS company,
      coalesce(j.location, '') AS location,
      coalesce(j.salary, '') AS salary,
      coalesce(j.experience_years, 0.0) AS experience_years
    LIMIT 1
    """

    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        start_row = session.run(start_query, {"job_id": job_id}).single()
        if not start_row:
            return jsonify({"ok": False, "message": "岗位不存在"}), 404

        params = {"job_id": job_id, "sources": PROMOTION_EDGE_SOURCES}
        paths = [dict(r) for r in session.run(path_query, params)]
        next_jobs = [dict(r) for r in session.run(next_query, params)]

    normalized_paths = []
    for item in paths:
        nodes = item.get("nodes") or []
        edges = item.get("edges") or []
        if not nodes:
            continue
        normalized_paths.append(
            {
                "hops": int(item.get("hops") or 0),
                "nodes": nodes,
                "edges": edges,
            }
        )

    return jsonify(
        {
            "ok": True,
            "data": {
                "job": dict(start_row),
                "paths": normalized_paths,
                "next_steps": next_jobs,
                "meta": {
                    "sources": PROMOTION_EDGE_SOURCES,
                    "max_depth": max_depth,
                    "max_paths": max_paths,
                },
            },
        }
    )
