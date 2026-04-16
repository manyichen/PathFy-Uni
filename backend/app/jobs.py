from functools import lru_cache

from flask import Blueprint, current_app, jsonify, request
from neo4j import GraphDatabase

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
