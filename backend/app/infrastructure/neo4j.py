"""Neo4j 岗位图谱：维度常量、连接与行序列化。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from flask import current_app
from neo4j import GraphDatabase, Query

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
    connection_timeout = max(
        1.0,
        float(current_app.config.get("NEO4J_CONNECTION_TIMEOUT_SECONDS", 5.0)),
    )
    return GraphDatabase.driver(
        uri,
        auth=(user, password),
        connection_timeout=connection_timeout,
        connection_acquisition_timeout=connection_timeout,
    )


def neo4j_query(
    session,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
    *,
    timeout: float | None = None,
):
    """Run an interactive query with a server-side deadline.

    The driver connection timeout only covers establishing a Bolt connection. A
    Cypher query can otherwise wait indefinitely, which is especially harmful to
    user-triggered graph pages.
    """
    configured = timeout
    if configured is None:
        configured = float(current_app.config.get("NEO4J_QUERY_TIMEOUT_SECONDS", 12.0))
    effective_timeout = max(1.0, min(float(configured), 60.0))
    return session.run(Query(statement, timeout=effective_timeout), parameters or {})


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
    workstyle = row.get("workstyle")
    if isinstance(workstyle, dict):
        out["workstyle"] = workstyle
    return out
