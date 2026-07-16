"""Read-only Neo4j repository plus the explicitly audited emergency clear."""

from __future__ import annotations

from typing import Any, Dict, List

from neo4j import Driver


def clear_all_graph(driver: Driver, database: str) -> Dict[str, int]:
    """Emergency-only writer invoked behind admin confirmation and the guard."""
    with driver.session(database=database) as session:
        result = session.run("MATCH (n) DETACH DELETE n RETURN count(n) AS deleted")
        record = result.single()
        return {"deleted_nodes": int(record["deleted"]) if record else 0}


def list_import_runs(driver: Driver, database: str, *, limit: int = 20) -> List[Dict[str, Any]]:
    """Read legacy audit nodes; new updates are audited in MySQL tasks."""
    with driver.session(database=database) as session:
        rows = session.run(
            """MATCH (run:GraphImportRun) RETURN run{.*} AS item
            ORDER BY run.started_at DESC LIMIT $limit""",
            limit=max(1, min(int(limit), 100)),
        )
        return [dict(row["item"]) for row in rows]


def fetch_job_import_fingerprints(
    driver: Driver, database: str, job_keys: List[str]
) -> Dict[str, str]:
    if not job_keys:
        return {}
    with driver.session(database=database) as session:
        rows = session.run(
            """UNWIND $job_keys AS key MATCH (j:Job {job_key:key})
            RETURN j.job_key AS job_key,coalesce(j.import_fingerprint,'') AS fingerprint""",
            job_keys=job_keys,
        )
        return {str(row["job_key"]): str(row["fingerprint"] or "") for row in rows}


def get_graph_statistics(driver: Driver, database: str) -> Dict[str, int]:
    with driver.session(database=database) as session:
        stats: Dict[str, int] = {}
        for label in (
            "Job", "JobTitle", "JobPromotion", "Company", "Skill",
            "Certificate", "SoftSkill", "CareerLevel", "LearningResource", "Competition",
            "GraphImportRun",
        ):
            record = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt").single()
            stats[f"{label.lower()}_count"] = int(record["cnt"]) if record else 0
        for rel_type in (
            "BELONGS_TO", "REQUIRES", "HAS_TITLE", "FOR_JOB_TITLE",
            "SIMILAR_FOR_LATERAL", "VERTICAL_UP",
        ):
            record = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt").single()
            stats[f"{rel_type.lower()}_count"] = int(record["cnt"]) if record else 0
        return stats
