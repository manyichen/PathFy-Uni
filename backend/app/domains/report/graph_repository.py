"""Neo4j：竞赛与学习资源检索（经 JobTitle）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.infrastructure.neo4j import neo4j_driver, neo4j_settings


def resolve_job_title_names(job_ids: List[str]) -> Dict[str, str]:
    """job_id -> JobTitle.name；优先 HAS_TITLE，否则 trim(Job.title)。"""
    ids = [str(x).strip() for x in job_ids if str(x).strip()]
    if not ids:
        return {}
    uri, user, password, database = neo4j_settings()
    if not password:
        return {}
    query = """
    UNWIND $ids AS jid
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = jid
    OPTIONAL MATCH (j)-[:HAS_TITLE]->(jt:JobTitle)
    RETURN
      jid AS job_id,
      coalesce(jt.name, trim(j.title), '') AS job_title_name
    """
    driver = neo4j_driver(uri, user, password)
    out: Dict[str, str] = {}
    with driver.session(database=database) as session:
        for row in session.run(query, {"ids": ids}):
            rec = dict(row)
            jid = str(rec.get("job_id") or "").strip()
            name = str(rec.get("job_title_name") or "").strip()
            if jid and name:
                out[jid] = name
    return out


def fetch_learning_resources_for_title(job_title_name: str) -> List[Dict[str, Any]]:
    title = str(job_title_name or "").strip()
    if not title:
        return []
    uri, user, password, database = neo4j_settings()
    if not password:
        return []
    query = """
    MATCH (jt:JobTitle {name: $title})<-[:FOR_JOB_TITLE]-(lr:LearningResource)
    RETURN
      lr.resource_id AS resource_id,
      lr.resource_name AS resource_name,
      lr.resource_desc AS resource_desc,
      lr.resource_url AS resource_url,
      lr.resource_type AS resource_type,
      lr.difficulty AS difficulty,
      lr.source AS source,
      lr.skill_tag AS skill_tag
    ORDER BY lr.resource_id ASC
    """
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        return [dict(r) for r in session.run(query, {"title": title})]


def _neo4j_settings_safe() -> tuple[str, str, str, str]:
    try:
        return neo4j_settings()
    except RuntimeError:
        import os

        return (
            os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", ""),
            os.environ.get("NEO4J_DATABASE", "neo4j"),
        )


def fetch_track_graph_stats_batch() -> Dict[str, Dict[str, int]]:
    """
    批量统计各 JobTitle 的晋升路线数、横向相似数、学习资源数、竞赛数。
    返回 job_title_name -> counts。
    """
    uri, user, password, database = _neo4j_settings_safe()
    if not password:
        return {}
    query = """
    MATCH (jt:JobTitle)
    OPTIONAL MATCH (jp:JobPromotion)-[:FOR_JOB_TITLE]->(jt)
    WITH jt, count(DISTINCT jp) AS promotion_route_count
    OPTIONAL MATCH (jt)-[lat:SIMILAR_FOR_LATERAL]->(:JobTitle)
    WITH jt, promotion_route_count, count(DISTINCT lat) AS lateral_similar_count
    OPTIONAL MATCH (lr:LearningResource)-[:FOR_JOB_TITLE]->(jt)
    WITH jt, promotion_route_count, lateral_similar_count, count(DISTINCT lr) AS learning_resource_count
    OPTIONAL MATCH (c:Competition)-[:FOR_JOB_TITLE]->(jt)
    RETURN
      jt.name AS job_title,
      promotion_route_count,
      lateral_similar_count,
      learning_resource_count,
      count(DISTINCT c) AS competition_count
    """
    driver = neo4j_driver(uri, user, password)
    out: Dict[str, Dict[str, int]] = {}
    with driver.session(database=database) as session:
        for row in session.run(query):
            rec = dict(row)
            name = str(rec.get("job_title") or "").strip()
            if not name:
                continue
            out[name] = {
                "promotion_route_count": int(rec.get("promotion_route_count") or 0),
                "lateral_similar_count": int(rec.get("lateral_similar_count") or 0),
                "learning_resource_count": int(rec.get("learning_resource_count") or 0),
                "competition_count": int(rec.get("competition_count") or 0),
            }
    return out


def fetch_competitions_for_title(job_title_name: str) -> List[Dict[str, Any]]:
    title = str(job_title_name or "").strip()
    if not title:
        return []
    uri, user, password, database = neo4j_settings()
    if not password:
        return []
    query = """
    MATCH (jt:JobTitle {name: $title})<-[:FOR_JOB_TITLE]-(c:Competition)
    RETURN
      c.competition_id AS competition_id,
      c.competition_name AS competition_name,
      c.competition_desc AS competition_desc,
      c.official_url AS official_url,
      c.competition_type AS competition_type,
      c.organizer AS organizer,
      c.target_audience AS target_audience,
      c.team_mode AS team_mode,
      c.frequency AS frequency,
      c.difficulty AS difficulty,
      c.cap_tags AS cap_tags,
      c.skill_tags AS skill_tags,
      c.award_level AS award_level
    ORDER BY c.competition_id ASC
    """
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        return [dict(r) for r in session.run(query, {"title": title})]
