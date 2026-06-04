"""
在 Neo4j 中建立 JobTitle 实体，并按 Job.title 关联。

- JobTitle 仅保留属性：name（岗位名称）、job_count（由当前连接的 Job 数量计算）
- 不使用 job_title_record_counts.csv 中的 record_count / pct / company_count 等
- 关系：(Job)-[:HAS_TITLE]->(JobTitle)

用法（读取 backend/.env 中的 NEO4J_*）：
  python tools/neo4j/sync_neo4j_job_titles.py --dry-run
  python tools/neo4j/sync_neo4j_job_titles.py
  python tools/neo4j/sync_neo4j_job_titles.py --clear-relationships  # 先删旧 HAS_TITLE 再重建
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
_BACKEND = ROOT / "backend"
load_dotenv(_BACKEND / ".env")


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


def _stats(session) -> dict:
    rows = session.run(
        """
        MATCH (j:Job)
        RETURN
          count(j) AS jobs_total,
          sum(CASE WHEN j.title IS NULL OR trim(j.title) = '' THEN 1 ELSE 0 END) AS jobs_no_title
        """
    ).single()
    jt = session.run(
        """
        OPTIONAL MATCH (jt:JobTitle)
        OPTIONAL MATCH ()-[r:HAS_TITLE]->(jt:JobTitle)
        RETURN count(DISTINCT jt) AS job_title_nodes, count(r) AS has_title_edges
        """
    ).single()
    return {
        "jobs_total": rows["jobs_total"],
        "jobs_no_title": rows["jobs_no_title"],
        "job_title_nodes": jt["job_title_nodes"],
        "has_title_edges": jt["has_title_edges"],
    }


def _aggregate_titles(session) -> list[dict]:
    return list(
        session.run(
            """
            MATCH (j:Job)
            WHERE j.title IS NOT NULL AND trim(j.title) <> ''
            WITH trim(j.title) AS title, count(j) AS job_count
            RETURN title, job_count
            ORDER BY job_count DESC, title ASC
            """
        )
    )


def sync(*, dry_run: bool, clear_relationships: bool) -> int:
    driver, database = _connect()
    try:
        with driver.session(database=database) as session:
            before = _stats(session)
            titles = _aggregate_titles(session)

            print("=== 同步前 ===")
            print(before)
            print(f"distinct_titles_from_jobs: {len(titles)}")
            if titles[:10]:
                print("Top 10 titles by job_count (Neo4j Job nodes):")
                for row in titles[:10]:
                    print(f"  {row['job_count']:4d}  {row['title']}")

            if dry_run:
                print("\n[dry-run] 未写入 Neo4j")
                return 0

            if clear_relationships:
                session.run("MATCH ()-[r:HAS_TITLE]->() DELETE r")
                print("已删除全部 HAS_TITLE 关系")

            # 约束（幂等）
            session.run(
                """
                CREATE CONSTRAINT job_title_name IF NOT EXISTS
                FOR (t:JobTitle) REQUIRE t.name IS UNIQUE
                """
            )

            # 1) 合并 JobTitle 并写入 job_count（仅来自 Job 聚合）
            session.run(
                """
                MATCH (j:Job)
                WHERE j.title IS NOT NULL AND trim(j.title) <> ''
                WITH trim(j.title) AS title, count(j) AS job_count
                MERGE (jt:JobTitle {name: title})
                SET jt.job_count = job_count
                """
            )

            # 2) 建立 Job -> JobTitle 关联（按 title 精确匹配）
            session.run(
                """
                MATCH (j:Job)
                WHERE j.title IS NOT NULL AND trim(j.title) <> ''
                WITH j, trim(j.title) AS title
                MATCH (jt:JobTitle {name: title})
                MERGE (j)-[:HAS_TITLE]->(jt)
                """
            )

            # 3) 删除已无 Job 连接的 JobTitle（孤立节点）
            orphan_row = session.run(
                """
                MATCH (jt:JobTitle)
                WHERE NOT (jt)<-[:HAS_TITLE]-(:Job)
                WITH collect(jt) AS orphans
                FOREACH (x IN orphans | DETACH DELETE x)
                RETURN size(orphans) AS removed
                """
            ).single()
            removed = orphan_row["removed"] if orphan_row else 0

            after = _stats(session)
            mismatch = session.run(
                """
                MATCH (jt:JobTitle)
                OPTIONAL MATCH (j:Job)-[:HAS_TITLE]->(jt)
                WITH jt, jt.job_count AS stored, count(j) AS actual
                WHERE stored <> actual
                RETURN count(jt) AS mismatch_count
                """
            ).single()["mismatch_count"]

            print("\n=== 同步后 ===")
            print(after)
            print(f"removed_orphan_job_titles: {removed}")
            print(f"job_count_mismatch: {mismatch}")
            if mismatch:
                print("WARN: 存在 job_count 与实连 Job 数不一致的 JobTitle", file=sys.stderr)
                return 1
            return 0
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j JobTitle 实体同步")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计，不写入",
    )
    parser.add_argument(
        "--clear-relationships",
        action="store_true",
        help="写入前删除所有 HAS_TITLE 关系（不删 JobTitle 节点，随后会重建）",
    )
    args = parser.parse_args()
    raise SystemExit(sync(dry_run=args.dry_run, clear_relationships=args.clear_relationships))


if __name__ == "__main__":
    main()
