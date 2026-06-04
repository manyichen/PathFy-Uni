"""
将 datasets/master/learning_resources.csv 导入 Neo4j 知识图谱。

- 节点标签：LearningResource（学习资源实体 learning_resources）
- 主键：resource_id
- job_name 按 | 拆分后与 JobTitle.name 匹配，建立：
  (LearningResource)-[:FOR_JOB_TITLE]->(JobTitle)
- job_name 为 ALL（可与其他名用 | 组合）时，与该图谱中全部 JobTitle 建立关系

用法（读取 backend/.env 的 NEO4J_*）：
  python tools/neo4j/sync_neo4j_learning_resources.py --dry-run
  python tools/neo4j/sync_neo4j_learning_resources.py
  python tools/neo4j/sync_neo4j_learning_resources.py --csv path/to/learning_resources.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "datasets" / "master" / "learning_resources.csv"
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


UNIVERSAL_JOB_NAME = "ALL"


def _split_job_names(job_name: str) -> list[str]:
    return [p.strip() for p in (job_name or "").split("|") if p.strip()]


def _is_universal(titles: list[str]) -> bool:
    return UNIVERSAL_JOB_NAME in titles


def _specific_titles(titles: list[str]) -> list[str]:
    return [t for t in titles if t != UNIVERSAL_JOB_NAME]


def _existing_job_titles(session) -> set[str]:
    return {r["name"] for r in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name")}

_PROP_COLUMNS = (
    "resource_name",
    "resource_desc",
    "resource_url",
    "resource_type",
    "difficulty",
    "source",
    "skill_tag",
)


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"ERROR: CSV 为空: {path}")
    return rows


def _analyze(rows: list[dict]) -> dict:
    ids = [r.get("resource_id", "").strip() for r in rows]
    dup_ids = [k for k, v in Counter(ids).items() if v > 1]
    job_fields = Counter((r.get("job_name") or "").strip() for r in rows)
    pipe_rows = sum(1 for r in rows if "|" in (r.get("job_name") or ""))
    types = Counter((r.get("resource_type") or "").strip() for r in rows)
    diff = Counter((r.get("difficulty") or "").strip() for r in rows)
    return {
        "resources_in_csv": len(rows),
        "unique_resource_id": len(set(ids)),
        "duplicate_resource_ids": dup_ids,
        "distinct_job_name_fields": len(job_fields),
        "rows_with_pipe_in_job_name": pipe_rows,
        "per_job_name_avg": round(len(rows) / max(len(job_fields), 1), 1),
        "resource_type": dict(types),
        "difficulty": dict(diff),
    }


def _preview(rows: list[dict], job_titles: set[str]) -> dict:
    edge_count = 0
    universal_rows = 0
    missing: set[str] = set()
    n_titles = len(job_titles)
    for row in rows:
        titles = _split_job_names(row.get("job_name", ""))
        if _is_universal(titles):
            universal_rows += 1
            edge_count += n_titles
            for t in _specific_titles(titles):
                if t not in job_titles:
                    missing.add(t)
                else:
                    edge_count += 1
        else:
            edge_count += len(titles)
            for t in titles:
                if t not in job_titles:
                    missing.add(t)
    return {
        "for_job_title_edges": edge_count,
        "universal_resource_rows": universal_rows,
        "job_title_nodes": n_titles,
        "missing_job_titles": sorted(missing),
    }


def sync(*, csv_path: Path, dry_run: bool) -> int:
    rows = _load_csv(csv_path)
    analysis = _analyze(rows)
    if analysis["duplicate_resource_ids"]:
        raise SystemExit(
            f"ERROR: resource_id 重复: {analysis['duplicate_resource_ids'][:5]}"
        )

    driver, database = _connect()
    try:
        with driver.session(database=database) as session:
            job_titles = _existing_job_titles(session)
            preview = _preview(rows, job_titles)

            print("=== CSV 分析 ===")
            print(analysis)
            print("=== 导入预览 ===")
            print(preview)

            if preview["missing_job_titles"]:
                print(
                    "ERROR: 下列 job_name 在图谱中无对应 JobTitle，请先同步岗位名或修正 CSV",
                    file=sys.stderr,
                )
                for name in preview["missing_job_titles"]:
                    print(f"  - {name}", file=sys.stderr)
                return 1

            if dry_run:
                print("\n[dry-run] 未写入 Neo4j")
                return 0

            session.run(
                """
                CREATE CONSTRAINT learning_resource_id IF NOT EXISTS
                FOR (lr:LearningResource) REQUIRE lr.resource_id IS UNIQUE
                """
            )

            linked_edges = 0
            for row in rows:
                rid = (row.get("resource_id") or "").strip()
                if not rid:
                    continue
                props = {k: (row.get(k) or "").strip() for k in _PROP_COLUMNS}
                titles = _split_job_names(row.get("job_name", ""))

                session.run(
                    """
                    MERGE (lr:LearningResource {resource_id: $resource_id})
                    SET lr += $props
                    WITH lr
                    OPTIONAL MATCH (lr)-[old:FOR_JOB_TITLE]->()
                    DELETE old
                    """,
                    resource_id=rid,
                    props=props,
                )

                if titles:
                    n_linked = 0
                    if _is_universal(titles):
                        result = session.run(
                            """
                            MATCH (lr:LearningResource {resource_id: $resource_id})
                            MATCH (jt:JobTitle)
                            MERGE (lr)-[:FOR_JOB_TITLE]->(jt)
                            RETURN count(*) AS linked
                            """,
                            resource_id=rid,
                        ).single()
                        n_linked += int(result["linked"] or 0) if result else 0
                    specific = _specific_titles(titles)
                    if specific:
                        result = session.run(
                            """
                            MATCH (lr:LearningResource {resource_id: $resource_id})
                            UNWIND $titles AS title
                            MATCH (jt:JobTitle {name: title})
                            MERGE (lr)-[:FOR_JOB_TITLE]->(jt)
                            RETURN count(*) AS linked
                            """,
                            resource_id=rid,
                            titles=specific,
                        ).single()
                        n_linked += int(result["linked"] or 0) if result else 0
                    linked_edges += n_linked

            after = session.run(
                """
                MATCH (lr:LearningResource)
                OPTIONAL MATCH (lr)-[r:FOR_JOB_TITLE]->(:JobTitle)
                RETURN count(DISTINCT lr) AS resources, count(r) AS edges
                """
            ).single()

            by_job = session.run(
                """
                MATCH (jt:JobTitle)<-[:FOR_JOB_TITLE]-(lr:LearningResource)
                RETURN jt.name AS job, count(lr) AS n
                ORDER BY n DESC
                LIMIT 5
                """
            )
            top = [(r["job"], r["n"]) for r in by_job]

            print("\n=== 导入完成 ===")
            print(
                {
                    "learning_resource_nodes": after["resources"],
                    "for_job_title_edges": after["edges"],
                    "edges_from_csv_rows": linked_edges,
                    "top5_jobs_by_resource_count": top,
                }
            )
            return 0
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j LearningResource 导入")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="learning_resources.csv 路径",
    )
    args = parser.parse_args()
    if not args.csv.is_file():
        raise SystemExit(f"ERROR: 找不到 CSV: {args.csv}")
    raise SystemExit(sync(csv_path=args.csv, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
