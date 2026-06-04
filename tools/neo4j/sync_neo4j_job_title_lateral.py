"""
将 datasets/master/job_title_lateral_transfer.csv 导入 Neo4j。

关系：(JobTitle)-[:SIMILAR_FOR_LATERAL {props}]->(JobTitle)

用法：
  python tools/neo4j/sync_neo4j_job_title_lateral.py --dry-run
  python tools/neo4j/sync_neo4j_job_title_lateral.py
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
DEFAULT_CSV = ROOT / "datasets" / "master" / "job_title_lateral_transfer.csv"
load_dotenv(ROOT / "backend" / ".env")

REL_PROPS = (
    "score",
    "rank",
    "track_from",
    "track_to",
    "cap_similarity",
    "same_track",
    "promotion_linked",
    "rationale",
)


def _connect():
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not password:
        raise SystemExit("ERROR: 未设置 NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver, database


def _load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _f(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _i(v: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def sync(*, csv_path: Path, dry_run: bool) -> int:
    rows = _load(csv_path)
    if not rows:
        raise SystemExit(f"ERROR: CSV 为空: {csv_path}")

    driver, database = _connect()
    try:
        with driver.session(database=database) as session:
            titles = {r["name"] for r in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name")}
            missing = sorted(
                {
                    t
                    for row in rows
                    for t in (row.get("from_job_title", ""), row.get("to_job_title", ""))
                    if t.strip() and t.strip() not in titles
                }
            )
            if missing:
                print("ERROR: 下列 JobTitle 不在图谱中:", file=sys.stderr)
                for m in missing[:15]:
                    print(f"  - {m}", file=sys.stderr)
                return 1

            print(f"CSV 行数: {len(rows)}, JobTitle 节点: {len(titles)}")
            if dry_run:
                print("[dry-run] 未写入")
                return 0

            old = session.run(
                "MATCH ()-[r:SIMILAR_FOR_LATERAL]->() RETURN count(r) AS c"
            ).single()
            n_old = int((old or {}).get("c") or 0)
            session.run("MATCH ()-[r:SIMILAR_FOR_LATERAL]->() DELETE r")
            print(f"已清除旧边 SIMILAR_FOR_LATERAL={n_old}")

            payload = []
            for row in rows:
                payload.append(
                    {
                        "from_title": row["from_job_title"].strip(),
                        "to_title": row["to_job_title"].strip(),
                        "score": _f(row.get("score", "")),
                        "rank": _i(row.get("rank", "")),
                        "track_from": (row.get("track_from") or "").strip(),
                        "track_to": (row.get("track_to") or "").strip(),
                        "cap_similarity": _f(row.get("cap_similarity", "")),
                        "same_track": (row.get("same_track") or "").strip() == "1",
                        "promotion_linked": (row.get("promotion_linked") or "").strip()
                        == "1",
                        "rationale": (row.get("rationale") or "").strip(),
                    }
                )

            result = session.run(
                """
                UNWIND $rows AS row
                MATCH (a:JobTitle {name: row.from_title})
                MATCH (b:JobTitle {name: row.to_title})
                MERGE (a)-[r:SIMILAR_FOR_LATERAL]->(b)
                SET r.score = row.score,
                    r.rank = row.rank,
                    r.track_from = row.track_from,
                    r.track_to = row.track_to,
                    r.cap_similarity = row.cap_similarity,
                    r.same_track = row.same_track,
                    r.promotion_linked = row.promotion_linked,
                    r.rationale = row.rationale
                RETURN count(r) AS c
                """,
                {"rows": payload},
            ).single()
            n_new = int(result["c"] or 0) if result else 0

            sample = list(
                session.run(
                    """
                    MATCH (a:JobTitle {name: 'Java'})-[r:SIMILAR_FOR_LATERAL]->(b:JobTitle)
                    RETURN b.name AS target, r.score AS score, r.rank AS rank, r.rationale AS rationale
                    ORDER BY r.rank LIMIT 5
                    """
                )
            )
            print({"edges_written": n_new, "sample_Java": [dict(x) for x in sample]})
            return 0
    finally:
        driver.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 JobTitle 水平换岗相似边")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    if not args.csv.is_file():
        raise SystemExit(f"ERROR: 找不到 {args.csv}，请先运行 build_job_title_lateral_similarity.py")
    return sync(csv_path=args.csv, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
