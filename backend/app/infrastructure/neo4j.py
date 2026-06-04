"""Neo4j 岗位图谱：维度常量、连接与行序列化。"""

from __future__ import annotations

from functools import lru_cache

from flask import current_app
from neo4j import GraphDatabase

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
def neo4j_driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def neo4j_settings() -> tuple[str, str, str, str]:
    return (
        current_app.config["NEO4J_URI"],
        current_app.config["NEO4J_USER"],
        current_app.config["NEO4J_PASSWORD"],
        current_app.config["NEO4J_DATABASE"],
    )


def serialize_job_row(row: dict) -> dict:
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
    out = {
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
    raw = row.get("salary_raw")
    if raw is not None and str(raw).strip():
        out["salary_raw"] = str(raw).strip()
    return out
