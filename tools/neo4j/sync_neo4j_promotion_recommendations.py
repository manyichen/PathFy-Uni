"""
将 datasets/promotion/promotion_learning_resources.csv 与 promotion_competitions.csv 导入 Neo4j。

关系：
  (JobPromotion)-[:RECOMMENDS_RESOURCE {stage, stage_role, rank, score, rationale}]->(LearningResource)
  (JobPromotion)-[:RECOMMENDS_COMPETITION {stage, stage_role, rank, score, match_via, rationale}]->(Competition)

前置：已执行 sync_neo4j_job_promotions、sync_neo4j_learning_resources、sync_neo4j_competitions。

用法：
  python tools/neo4j/sync_neo4j_promotion_recommendations.py --dry-run
  python tools/neo4j/sync_neo4j_promotion_recommendations.py
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
LR_CSV = ROOT / "datasets" / "promotion" / "promotion_learning_resources.csv"
COMP_CSV = ROOT / "datasets" / "promotion" / "promotion_competitions.csv"
load_dotenv(ROOT / "backend" / ".env")

BATCH = 200


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


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _fscore(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _istage(v: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _irank(v: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _validate(session, lr_rows: list[dict], comp_rows: list[dict]) -> dict:
    promo_ids = {r["promotion_id"] for r in session.run(
        "MATCH (p:JobPromotion) RETURN p.promotion_id AS promotion_id"
    )}
    lr_ids = {r["resource_id"] for r in session.run(
        "MATCH (lr:LearningResource) RETURN lr.resource_id AS resource_id"
    )}
    comp_ids = {r["competition_id"] for r in session.run(
        "MATCH (c:Competition) RETURN c.competition_id AS competition_id"
    )}

    miss_promo_lr = sorted({r["promotion_id"] for r in lr_rows if r["promotion_id"] not in promo_ids})
    miss_lr = sorted({r["resource_id"] for r in lr_rows if r["resource_id"] not in lr_ids})
    miss_promo_c = sorted({r["promotion_id"] for r in comp_rows if r["promotion_id"] not in promo_ids})
    miss_comp = sorted({r["competition_id"] for r in comp_rows if r["competition_id"] not in comp_ids})

    return {
        "job_promotion_nodes": len(promo_ids),
        "learning_resource_nodes": len(lr_ids),
        "competition_nodes": len(comp_ids),
        "missing_promotion_lr": miss_promo_lr[:10],
        "missing_resource": miss_lr[:10],
        "missing_promotion_comp": miss_promo_c[:10],
        "missing_competition": miss_comp[:10],
        "missing_promotion_lr_count": len(miss_promo_lr),
        "missing_resource_count": len(miss_lr),
        "missing_competition_count": len(miss_comp),
    }


def sync(*, dry_run: bool) -> int:
    lr_rows = _load_csv(LR_CSV)
    comp_rows = _load_csv(COMP_CSV)
    driver, database = _connect()

    lr_payload = [
        {
            "promotion_id": r["promotion_id"].strip(),
            "resource_id": r["resource_id"].strip(),
            "stage": _istage(r.get("stage", "")),
            "stage_role": (r.get("stage_role") or "").strip(),
            "rank": _irank(r.get("rank", "")),
            "score": _fscore(r.get("score", "")),
            "rationale": (r.get("rationale") or "").strip(),
        }
        for r in lr_rows
        if r.get("promotion_id") and r.get("resource_id")
    ]

    comp_payload = [
        {
            "promotion_id": r["promotion_id"].strip(),
            "competition_id": r["competition_id"].strip(),
            "stage": _istage(r.get("stage", "")),
            "stage_role": (r.get("stage_role") or "").strip(),
            "rank": _irank(r.get("rank", "")),
            "score": _fscore(r.get("score", "")),
            "match_via": (r.get("match_via") or "").strip(),
            "rationale": (r.get("rationale") or "").strip(),
        }
        for r in comp_rows
        if r.get("promotion_id") and r.get("competition_id")
    ]

    try:
        with driver.session(database=database) as session:
            check = _validate(session, lr_payload, comp_payload)
            print("=== 校验 ===")
            print(check)

            if (
                check["missing_promotion_lr_count"]
                or check["missing_resource_count"]
                or check["missing_competition_count"]
            ):
                print("ERROR: 存在缺失节点，请先同步 JobPromotion / LearningResource / Competition", file=sys.stderr)
                return 1

            if dry_run:
                print("\n[dry-run] 未写入 Neo4j")
                print({"would_link_lr": len(lr_payload), "would_link_comp": len(comp_payload)})
                return 0

            old_lr = session.run(
                "MATCH ()-[r:RECOMMENDS_RESOURCE]->() RETURN count(r) AS c"
            ).single()
            old_comp = session.run(
                "MATCH ()-[c:RECOMMENDS_COMPETITION]->() RETURN count(c) AS c"
            ).single()
            n_lr = int((old_lr or {}).get("c") or 0)
            n_comp = int((old_comp or {}).get("c") or 0)
            session.run("MATCH ()-[r:RECOMMENDS_RESOURCE]->() DELETE r")
            session.run("MATCH ()-[c:RECOMMENDS_COMPETITION]->() DELETE c")
            print(f"已清除旧边 RECOMMENDS_RESOURCE={n_lr}, RECOMMENDS_COMPETITION={n_comp}")

            lr_linked = 0
            for i in range(0, len(lr_payload), BATCH):
                batch = lr_payload[i : i + BATCH]
                result = session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (p:JobPromotion {promotion_id: row.promotion_id})
                    MATCH (lr:LearningResource {resource_id: row.resource_id})
                    MERGE (p)-[rel:RECOMMENDS_RESOURCE]->(lr)
                    SET rel.stage = row.stage,
                        rel.stage_role = row.stage_role,
                        rel.rank = row.rank,
                        rel.score = row.score,
                        rel.rationale = row.rationale
                    RETURN count(rel) AS c
                    """,
                    {"rows": batch},
                ).single()
                lr_linked += int(result["c"] or 0)

            comp_linked = 0
            for i in range(0, len(comp_payload), BATCH):
                batch = comp_payload[i : i + BATCH]
                result = session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (p:JobPromotion {promotion_id: row.promotion_id})
                    MATCH (c:Competition {competition_id: row.competition_id})
                    MERGE (p)-[rel:RECOMMENDS_COMPETITION]->(c)
                    SET rel.stage = row.stage,
                        rel.stage_role = row.stage_role,
                        rel.rank = row.rank,
                        rel.score = row.score,
                        rel.match_via = row.match_via,
                        rel.rationale = row.rationale
                    RETURN count(rel) AS c
                    """,
                    {"rows": batch},
                ).single()
                comp_linked += int(result["c"] or 0)

            after = session.run(
                """
                MATCH (p:JobPromotion)
                OPTIONAL MATCH (p)-[lr:RECOMMENDS_RESOURCE]->(:LearningResource)
                OPTIONAL MATCH (p)-[cp:RECOMMENDS_COMPETITION]->(:Competition)
                RETURN
                  count(DISTINCT p) AS promotions,
                  count(lr) AS lr_edges,
                  count(cp) AS comp_edges
                """
            ).single()

            sample = list(
                session.run(
                    """
                    MATCH (p:JobPromotion {promotion_id: '测试工程师_promotion1'})
                          -[r:RECOMMENDS_RESOURCE]->(lr:LearningResource)
                    RETURN p.promotion_id AS pid, r.stage AS stage, r.rank AS rank,
                           lr.resource_id AS rid, r.score AS score
                    ORDER BY r.stage, r.rank
                    LIMIT 6
                    """
                )
            )

            print("\n=== 导入完成 ===")
            print(
                {
                    "recommends_resource_edges": after["lr_edges"],
                    "recommends_competition_edges": after["comp_edges"],
                    "job_promotion_nodes": after["promotions"],
                    "lr_rows_imported": lr_linked,
                    "comp_rows_imported": comp_linked,
                    "sample_测试工程师_promotion1": [dict(x) for x in sample],
                }
            )
            return 0
    finally:
        driver.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="导入晋升推荐边到 Neo4j")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not LR_CSV.is_file() or not COMP_CSV.is_file():
        raise SystemExit("ERROR: 缺少 promotion_learning_resources.csv 或 promotion_competitions.csv")
    raise SystemExit(sync(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
