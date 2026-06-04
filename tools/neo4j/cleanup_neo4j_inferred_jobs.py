"""
删除 Neo4j 中 source='inferred' 的 Job，以及 job_count < 2 的 JobTitle。

删除 inferred Job 后会按实连 Job 数刷新 JobTitle.job_count，再删除 job_count < 2 的节点。

用法（读取 backend/.env 的 NEO4J_*）：
  python tools/neo4j/cleanup_neo4j_inferred_jobs.py --dry-run
  python tools/neo4j/cleanup_neo4j_inferred_jobs.py
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")


def _connect():
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not password:
        raise SystemExit("ERROR: 未设置 NEO4J_PASSWORD（请在 backend/.env 配置）")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver, database


def _preview(session) -> dict:
    row = session.run(
        """
        MATCH (j:Job)
        WHERE j.source = 'inferred'
        RETURN count(j) AS inferred_jobs
        """
    ).single()
    jt = session.run(
        """
        MATCH (jt:JobTitle)
        WHERE coalesce(jt.job_count, 0) < 2
        RETURN count(jt) AS job_titles_lt2
        """
    ).single()
    total = session.run("MATCH (j:Job) RETURN count(j) AS jobs").single()
    titles = session.run("MATCH (jt:JobTitle) RETURN count(jt) AS job_titles").single()
    return {
        "jobs_total": total["jobs"],
        "inferred_jobs": row["inferred_jobs"],
        "job_titles_total": titles["job_titles"],
        "job_titles_lt2": jt["job_titles_lt2"],
    }


def cleanup(*, dry_run: bool) -> int:
    driver, database = _connect()
    try:
        with driver.session(database=database) as session:
            before = _preview(session)
            print("=== 清理前 ===")
            for k, v in before.items():
                print(f"  {k}: {v}")

            if dry_run:
                print("\n[dry-run] 未修改 Neo4j")
                return 0

            deleted_jobs = session.run(
                """
                MATCH (j:Job)
                WHERE j.source = 'inferred'
                WITH collect(j) AS nodes
                FOREACH (x IN nodes | DETACH DELETE x)
                RETURN size(nodes) AS deleted
                """
            ).single()
            print(f"\n已删除 inferred Job: {deleted_jobs['deleted'] if deleted_jobs else 0}")

            session.run(
                """
                MATCH (jt:JobTitle)
                OPTIONAL MATCH (j:Job)-[:HAS_TITLE]->(jt)
                WITH jt, count(j) AS actual
                SET jt.job_count = actual
                """
            )

            deleted_titles = session.run(
                """
                MATCH (jt:JobTitle)
                WHERE coalesce(jt.job_count, 0) < 2
                WITH collect(jt) AS nodes
                FOREACH (x IN nodes | DETACH DELETE x)
                RETURN size(nodes) AS deleted
                """
            ).single()
            print(
                f"已删除 job_count < 2 的 JobTitle: "
                f"{deleted_titles['deleted'] if deleted_titles else 0}"
            )

            after = _preview(session)
            after_jobs = session.run("MATCH (j:Job) RETURN count(j) AS n").single()["n"]
            after_titles = session.run("MATCH (jt:JobTitle) RETURN count(jt) AS n").single()["n"]
            print("\n=== 清理后 ===")
            print(f"  jobs_total: {after_jobs}")
            print(f"  job_titles_total: {after_titles}")
            print(f"  inferred_jobs: {after['inferred_jobs']}")
            print(f"  job_titles_lt2: {after['job_titles_lt2']}")
            return 0
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="删除 inferred Job 与低频 JobTitle")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不删除")
    args = parser.parse_args()
    raise SystemExit(cleanup(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
