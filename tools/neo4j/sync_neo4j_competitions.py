"""
将 datasets/master/competitions.csv 导入 Neo4j 知识图谱。

- 节点标签：Competition
- 主键：competition_id
- job_name 按 | 拆分，与 JobTitle.name 精确匹配后建立关系：
  (Competition)-[:FOR_JOB_TITLE]->(JobTitle)

用法（读取 backend/.env 的 NEO4J_*）：
  python tools/neo4j/sync_neo4j_competitions.py --dry-run
  python tools/neo4j/sync_neo4j_competitions.py
  python tools/neo4j/sync_neo4j_competitions.py --csv path/to/competitions.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "datasets" / "master" / "competitions.csv"
load_dotenv(ROOT / "backend" / ".env")

# CSV 列 -> 节点属性（job_name 仅用于连边，不落库）
_PROP_COLUMNS = (
    "competition_name",
    "competition_desc",
    "official_url",
    "competition_type",
    "organizer",
    "target_audience",
    "team_mode",
    "frequency",
    "difficulty",
    "cap_tags",
    "skill_tags",
    "award_level",
)


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


def _split_job_names(job_name: str) -> list[str]:
    return [p.strip() for p in (job_name or "").split("|") if p.strip()]


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"ERROR: CSV 为空: {path}")
    return rows


def _existing_job_titles(session) -> set[str]:
    return {r["name"] for r in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name")}


def _preview(rows: list[dict], job_titles: set[str]) -> dict:
    edge_count = 0
    missing: set[str] = set()
    for row in rows:
        titles = _split_job_names(row.get("job_name", ""))
        edge_count += len(titles)
        for t in titles:
            if t not in job_titles:
                missing.add(t)
    return {
        "competitions_in_csv": len(rows),
        "for_job_title_edges": edge_count,
        "missing_job_titles": sorted(missing),
    }


def sync(*, csv_path: Path, dry_run: bool) -> int:
    rows = _load_csv(csv_path)
    driver, database = _connect()
    try:
        with driver.session(database=database) as session:
            job_titles = _existing_job_titles(session)
            preview = _preview(rows, job_titles)
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
                CREATE CONSTRAINT competition_id IF NOT EXISTS
                FOR (c:Competition) REQUIRE c.competition_id IS UNIQUE
                """
            )

            linked_edges = 0
            for row in rows:
                cid = (row.get("competition_id") or "").strip()
                if not cid:
                    continue
                props = {k: (row.get(k) or "").strip() for k in _PROP_COLUMNS}
                titles = _split_job_names(row.get("job_name", ""))

                session.run(
                    """
                    MERGE (c:Competition {competition_id: $competition_id})
                    SET c += $props
                    WITH c
                    OPTIONAL MATCH (c)-[old:FOR_JOB_TITLE]->()
                    DELETE old
                    """,
                    competition_id=cid,
                    props=props,
                )

                if titles:
                    result = session.run(
                        """
                        MATCH (c:Competition {competition_id: $competition_id})
                        UNWIND $titles AS title
                        MATCH (jt:JobTitle {name: title})
                        MERGE (c)-[:FOR_JOB_TITLE]->(jt)
                        RETURN count(*) AS linked
                        """,
                        competition_id=cid,
                        titles=titles,
                    ).single()
                    linked_edges += result["linked"] if result else 0

            after = session.run(
                """
                MATCH (c:Competition)
                OPTIONAL MATCH (c)-[r:FOR_JOB_TITLE]->(:JobTitle)
                RETURN count(DISTINCT c) AS competitions, count(r) AS edges
                """
            ).single()

            print("\n=== 导入完成 ===")
            print(
                {
                    "competition_nodes": after["competitions"],
                    "for_job_title_edges": after["edges"],
                    "edges_from_csv_rows": linked_edges,
                }
            )
            return 0
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j Competition 导入")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="competitions.csv 路径")
    args = parser.parse_args()
    if not args.csv.is_file():
        raise SystemExit(f"ERROR: 找不到 CSV: {args.csv}")
    raise SystemExit(sync(csv_path=args.csv, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
