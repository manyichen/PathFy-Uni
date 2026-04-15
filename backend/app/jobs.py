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

    score_avg = round(sum(scores.values()) / len(DIM_KEYS), 2)
    return {
        "id": row["id"],
        "title": row["title"],
        "salary": row["salary"],
        "company": row["company"],
        "location": row["location"],
        "risk_flags": row.get("risk_flags") or [],
        "scores": scores,
        "score_avg": score_avg,
    }


@jobs_bp.get("")
def list_jobs():
    uri, user, password, database = _neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    limit = max(1, min(int(request.args.get("limit", "60")), 200))
    keyword = (request.args.get("q") or "").strip()

    query = """
    MATCH (j:Job)
    WHERE $q = '' OR
      toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
      toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
      toLower(coalesce(j.location, '')) CONTAINS toLower($q)
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
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth
    ORDER BY total_score DESC, title ASC
    LIMIT $limit
    """

    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"limit": limit, "q": keyword})]

    data = [_serialize_row(r) for r in rows]
    return jsonify({"ok": True, "data": {"jobs": data, "total": len(data)}})
