"""
将 datasets/promotion/job_title_promotions.csv 导入 Neo4j。

- 节点标签：JobPromotion
- 主键：promotion_id（节点属性 name 与 promotion_id 相同）
- 关系：(JobPromotion)-[:FOR_JOB_TITLE]->(JobTitle {name: job_title})

读取 backend/.env 的 NEO4J_*；跳过 job_title_promotions_excluded.csv 中的岗位（不应出现在主 CSV）。

用法：
  python tools/neo4j/sync_neo4j_job_promotions.py --dry-run
  python tools/neo4j/sync_neo4j_job_promotions.py
  python tools/neo4j/sync_neo4j_job_promotions.py --clear-orphans
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
DEFAULT_CSV = ROOT / "datasets" / "promotion" / "job_title_promotions.csv"
EXCLUDED_CSV = ROOT / "datasets" / "promotion" / "job_title_promotions_excluded.csv"
load_dotenv(ROOT / "backend" / ".env")

_PROP_KEYS = (
    "title",
    "promotion",
    "stage1",
    "stage2",
    "stage3",
    "stage3_job_title",
    "notes",
    "job_title",
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


def _load_excluded(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {
            (row.get("job_title") or "").strip()
            for row in csv.DictReader(f)
            if (row.get("job_title") or "").strip()
        }


def _load_promotions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"ERROR: CSV 为空: {path}")
    out: list[dict] = []
    for row in rows:
        pid = (row.get("promotion_id") or "").strip()
        jt = (row.get("job_title") or "").strip()
        if not pid or not jt:
            raise SystemExit(f"ERROR: 缺少 promotion_id 或 job_title: {row}")
        props = {k: (row.get(k) or "").strip() for k in _PROP_KEYS}
        props["job_title"] = jt
        out.append({"promotion_id": pid, "props": props})
    return out


def _analyze(rows: list[dict]) -> dict:
    ids = [r["promotion_id"] for r in rows]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    by_job = Counter(r["props"]["job_title"] for r in rows)
    return {
        "rows": len(rows),
        "unique_promotion_id": len(set(ids)),
        "duplicate_promotion_ids": dup,
        "distinct_job_titles": len(by_job),
        "max_routes_per_job": max(by_job.values()) if by_job else 0,
    }


def sync(*, csv_path: Path, excluded_path: Path, dry_run: bool, clear_orphans: bool) -> int:
    excluded = _load_excluded(excluded_path)
    rows = _load_promotions(csv_path)
    analysis = _analyze(rows)
    if analysis["duplicate_promotion_ids"]:
        raise SystemExit(
            f"ERROR: promotion_id 重复: {analysis['duplicate_promotion_ids'][:5]}"
        )

    bad_excluded = [r["props"]["job_title"] for r in rows if r["props"]["job_title"] in excluded]
    if bad_excluded:
        raise SystemExit(
            f"ERROR: 下列 job_title 应在 excluded 中删除主 CSV 行: {sorted(set(bad_excluded))}"
        )

    driver, database = _connect()
    try:
        with driver.session(database=database) as session:
            job_titles = {r["name"] for r in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name")}
            missing = sorted({r["props"]["job_title"] for r in rows if r["props"]["job_title"] not in job_titles})

            print("=== CSV 分析 ===")
            print(analysis)
            print("=== 图谱校验 ===")
            print({"job_title_nodes": len(job_titles), "missing_job_titles": missing})

            if missing:
                print("ERROR: 下列 job_title 无对应 JobTitle，请先运行 sync_neo4j_job_titles.py", file=sys.stderr)
                for name in missing:
                    print(f"  - {name}", file=sys.stderr)
                return 1

            if dry_run:
                print("\n[dry-run] 未写入 Neo4j")
                return 0

            session.run(
                """
                CREATE CONSTRAINT job_promotion_id IF NOT EXISTS
                FOR (p:JobPromotion) REQUIRE p.promotion_id IS UNIQUE
                """
            )

            linked = 0
            for row in rows:
                pid = row["promotion_id"]
                props = dict(row["props"])
                session.run(
                    """
                    MERGE (p:JobPromotion {promotion_id: $promotion_id})
                    SET p.name = $promotion_id,
                        p.title = $title,
                        p.promotion = $promotion,
                        p.stage1 = $stage1,
                        p.stage2 = $stage2,
                        p.stage3 = $stage3,
                        p.stage3_job_title = $stage3_job_title,
                        p.notes = $notes,
                        p.job_title = $job_title
                    WITH p
                    OPTIONAL MATCH (p)-[old:FOR_JOB_TITLE]->()
                    DELETE old
                    """,
                    promotion_id=pid,
                    title=props.get("title") or "",
                    promotion=props.get("promotion") or "",
                    stage1=props.get("stage1") or "",
                    stage2=props.get("stage2") or "",
                    stage3=props.get("stage3") or "",
                    stage3_job_title=props.get("stage3_job_title") or "",
                    notes=props.get("notes") or "",
                    job_title=props["job_title"],
                )
                result = session.run(
                    """
                    MATCH (p:JobPromotion {promotion_id: $promotion_id})
                    MATCH (jt:JobTitle {name: $job_title})
                    MERGE (p)-[:FOR_JOB_TITLE]->(jt)
                    RETURN count(*) AS c
                    """,
                    promotion_id=pid,
                    job_title=props["job_title"],
                ).single()
                linked += int(result["c"] or 0)

            removed_orphans = 0
            if clear_orphans:
                valid_ids = [r["promotion_id"] for r in rows]
                rec = session.run(
                    """
                    MATCH (p:JobPromotion)
                    WHERE NOT p.promotion_id IN $valid_ids
                    WITH p, p.promotion_id AS pid
                    DETACH DELETE p
                    RETURN count(pid) AS removed
                    """,
                    valid_ids=valid_ids,
                ).single()
                removed_orphans = int(rec["removed"] or 0)

            after = session.run(
                """
                MATCH (p:JobPromotion)
                OPTIONAL MATCH (p)-[r:FOR_JOB_TITLE]->(:JobTitle)
                RETURN count(DISTINCT p) AS nodes, count(r) AS edges
                """
            ).single()

            sample = list(
                session.run(
                    """
                    MATCH (p:JobPromotion)-[:FOR_JOB_TITLE]->(jt:JobTitle)
                    RETURN p.promotion_id AS id, jt.name AS job_title, p.title AS route_title
                    ORDER BY jt.name, p.promotion_id
                    LIMIT 8
                    """
                )
            )

            print("\n=== 导入完成 ===")
            print(
                {
                    "job_promotion_nodes": after["nodes"],
                    "for_job_title_edges": after["edges"],
                    "edges_linked_this_run": linked,
                    "orphans_removed": removed_orphans,
                    "sample": [dict(r) for r in sample],
                }
            )
            return 0
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j JobPromotion 导入")
    parser.add_argument("--dry-run", action="store_true", help="仅校验，不写入")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="job_title_promotions.csv 路径",
    )
    parser.add_argument(
        "--clear-orphans",
        action="store_true",
        help="删除不在 CSV 中的旧 JobPromotion 节点",
    )
    args = parser.parse_args()
    if not args.csv.is_file():
        raise SystemExit(f"ERROR: 找不到 CSV: {args.csv}")
    raise SystemExit(
        sync(
            csv_path=args.csv,
            excluded_path=EXCLUDED_CSV,
            dry_run=args.dry_run,
            clear_orphans=args.clear_orphans,
        )
    )


if __name__ == "__main__":
    main()
