"""一次性 Neo4j 图谱分析脚本（读取 backend/.env）。"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_BACKEND, ".env"))


def run_query(session, query: str, **params):
    return [record.data() for record in session.run(query, **params)]


def main() -> int:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if not password:
        print("ERROR: NEO4J_PASSWORD not set", file=sys.stderr)
        return 1

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
    except Exception as exc:
        print(f"CONNECT_FAIL: {exc}", file=sys.stderr)
        return 1

    report: dict = {"uri": uri, "database": database}

    with driver.session(database=database) as session:
        labels = [
            r["label"]
            for r in run_query(session, "CALL db.labels() YIELD label RETURN label ORDER BY label")
        ]
        rel_types = [
            r["relationshipType"]
            for r in run_query(
                session,
                "CALL db.relationshipTypes() YIELD relationshipType "
                "RETURN relationshipType ORDER BY relationshipType",
            )
        ]
        report["labels"] = labels
        report["relationship_types"] = rel_types

        node_counts = {}
        for label in labels:
            safe = label.replace("`", "")
            cnt = run_query(session, f"MATCH (n:`{safe}`) RETURN count(n) AS c")[0]["c"]
            node_counts[label] = cnt
        report["node_counts"] = node_counts

        rel_counts = {}
        for rt in rel_types:
            safe = rt.replace("`", "")
            cnt = run_query(session, f"MATCH ()-[r:`{safe}`]->() RETURN count(r) AS c")[0]["c"]
            rel_counts[rt] = cnt
        report["relationship_counts"] = rel_counts

        job_stats = run_query(
            session,
            """
            MATCH (j:Job)
            RETURN
              count(j) AS total,
              count(j.cap_req_theory) AS has_cap_theory,
              count(j.cap_req_practice) AS has_cap_practice,
              avg(j.cap_req_theory) AS avg_cap_theory,
              count(j.is_core_template) AS has_core_flag,
              sum(CASE WHEN j.is_core_template = true THEN 1 ELSE 0 END) AS core_template_jobs
            """,
        )
        report["job_capability_stats"] = job_stats[0] if job_stats else {}

        vertical = run_query(
            session,
            """
            MATCH ()-[r:VERTICAL_UP]->()
            RETURN count(r) AS edges, collect(DISTINCT r.source) AS sources
            """,
        )
        report["vertical_up"] = vertical[0] if vertical else {}

        promotion_paths = run_query(
            session,
            """
            MATCH (j:Job)
            WHERE EXISTS { MATCH (j)-[:VERTICAL_UP]->(:Job) }
            RETURN count(j) AS jobs_with_outgoing
            """,
        )
        report["jobs_with_promotion_out"] = (
            promotion_paths[0]["jobs_with_outgoing"] if promotion_paths else 0
        )

        sample_job = run_query(
            session,
            """
            MATCH (j:Job)
            WHERE j.cap_req_theory IS NOT NULL
            RETURN properties(j) AS props
            LIMIT 1
            """,
        )
        if sample_job:
            props = sample_job[0]["props"]
            report["job_property_keys"] = sorted(props.keys())

        top_companies = run_query(
            session,
            """
            MATCH (j:Job)-[:BELONGS_TO]->(c:Company)
            RETURN c.name AS company, count(j) AS jobs
            ORDER BY jobs DESC LIMIT 15
            """,
        )
        report["top_companies"] = top_companies

        top_locations = run_query(
            session,
            """
            MATCH (j:Job)
            WHERE j.location IS NOT NULL AND trim(j.location) <> ''
            RETURN j.location AS location, count(*) AS jobs
            ORDER BY jobs DESC LIMIT 15
            """,
        )
        report["top_locations"] = top_locations

        top_titles = run_query(
            session,
            """
            MATCH (j:Job)
            WHERE j.title IS NOT NULL
            RETURN j.title AS title, count(*) AS c
            ORDER BY c DESC LIMIT 15
            """,
        )
        report["top_titles"] = top_titles

        skill_top = run_query(
            session,
            """
            MATCH (j:Job)-[:REQUIRES]->(s:Skill)
            RETURN s.name AS skill, count(j) AS jobs
            ORDER BY jobs DESC LIMIT 15
            """,
        )
        report["top_skills"] = skill_top

        career_levels = run_query(
            session,
            """
            MATCH (j:Job)-[:BELONGS_TO]->(cl:CareerLevel)
            RETURN cl.name AS level, count(j) AS jobs
            ORDER BY jobs DESC LIMIT 10
            """,
        )
        report["career_levels"] = career_levels

        orphan_jobs = run_query(
            session,
            """
            MATCH (j:Job)
            WHERE NOT (j)-[:BELONGS_TO]->(:Company)
            RETURN count(j) AS c
            """,
        )
        report["jobs_without_company"] = orphan_jobs[0]["c"] if orphan_jobs else 0

        cap_cov = run_query(
            session,
            """
            MATCH (j:Job)
            RETURN
              count(j) AS total,
              sum(CASE WHEN j.cap_req_theory IS NOT NULL THEN 1 ELSE 0 END) AS with_caps,
              sum(CASE WHEN j.cap_req_theory IS NULL THEN 1 ELSE 0 END) AS without_caps
            """,
        )
        if cap_cov:
            t = cap_cov[0]["total"] or 1
            cap_cov[0]["pct_with_caps"] = round(100.0 * cap_cov[0]["with_caps"] / t, 1)
        report["cap_coverage"] = cap_cov[0] if cap_cov else {}

        promo_depth = run_query(
            session,
            """
            MATCH p=(a:Job)-[:VERTICAL_UP*1..5]->(b:Job)
            RETURN length(p) AS depth, count(*) AS paths ORDER BY depth
            """,
        )
        report["promotion_path_depths"] = promo_depth

        promo_samples = run_query(
            session,
            """
            MATCH (a:Job)-[r:VERTICAL_UP]->(b:Job)
            RETURN a.title AS from_title, a.company AS from_company,
                   b.title AS to_title, b.company AS to_company,
                   r.confidence AS confidence
            LIMIT 8
            """,
        )
        report["promotion_samples"] = promo_samples

        cap_dist = run_query(
            session,
            """
            MATCH (j:Job)
            WHERE j.cap_req_theory IS NOT NULL
            RETURN
              round(avg(j.cap_req_theory), 1) AS avg_theory,
              round(avg(j.cap_req_practice), 1) AS avg_practice,
              round(avg(j.cap_req_digital), 1) AS avg_digital,
              round(avg(j.cap_req_growth), 1) AS avg_growth,
              round(avg(j.cap_conf_theory), 3) AS avg_conf_theory
            """,
        )
        report["cap_averages"] = cap_dist[0] if cap_dist else {}

        db_stats = run_query(session, "CALL db.stats.retrieve('GRAPH COUNTS') YIELD section, data")
        if db_stats:
            report["db_stats"] = db_stats

    driver.close()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
