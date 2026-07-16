"""Idempotent MySQL projections derived from an already committed Neo4j graph."""

from __future__ import annotations

from typing import Any

from app.domains.graph.services import _sync_job_titles_from_graph
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings


def _sync_mysql_job_titles() -> dict[str, int]:
    uri, user, password, database = neo4j_settings()
    if not password:
        raise RuntimeError("未配置 NEO4J_PASSWORD")
    driver = neo4j_driver(uri, user, password)
    try:
        with driver.session(database=database) as session:
            rows = session.run(
                """MATCH (jt:JobTitle)
                RETURN jt.name AS name,coalesce(jt.job_count,0) AS count,
                  coalesce(jt.company_count,0) AS company_count,
                  coalesce(jt.job_code_count,0) AS job_code_count"""
            )
            data = [dict(row) for row in rows]
        _sync_job_titles_from_graph(data)
        return {"job_titles": len(data)}
    finally:
        close = getattr(driver, "close", None)
        if callable(close):
            close()


def projection_required(task: dict[str, Any]) -> bool:
    return task.get("task_type") == "job_import"


def project_task(task: dict[str, Any]) -> dict[str, Any]:
    if task.get("task_type") == "job_import":
        return _sync_mysql_job_titles()
    return {"skipped": True}
