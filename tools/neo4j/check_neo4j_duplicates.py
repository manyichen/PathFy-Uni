"""检查 Neo4j 图谱重复节点与重复关系。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")


def main() -> int:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not password:
        raise SystemExit("ERROR: 未设置 NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            print("=== 节点：按业务主键是否重复 ===\n")
            for label, prop in [
                ("Job", "job_id"),
                ("JobTitle", "name"),
                ("LearningResource", "resource_id"),
                ("Competition", "competition_id"),
                ("JobPromotion", "promotion_id"),
            ]:
                rows = list(
                    session.run(
                        f"""
                        MATCH (n:{label})
                        WITH n.{prop} AS key, count(*) AS c
                        WHERE c > 1
                        RETURN key, c ORDER BY c DESC LIMIT 10
                        """
                    )
                )
                total = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]
                dup_groups = session.run(
                    f"""
                    MATCH (n:{label})
                    WITH n.{prop} AS key, count(*) AS c
                    WHERE c > 1
                    RETURN count(*) AS groups, sum(c) AS nodes
                    """
                ).single()
                print(
                    f"{label} ({prop}): nodes={total}, "
                    f"dup_key_groups={dup_groups['groups'] or 0}, "
                    f"dup_nodes={dup_groups['nodes'] or 0}"
                )
                for r in rows:
                    print(f"  - {r['key']!r}: {r['c']} copies")

            print("\n=== 关系：同起终点+类型是否多条 ===\n")
            rel_checks = [
                (
                    "FOR_JOB_TITLE",
                    """
                    MATCH (lr:LearningResource)-[r:FOR_JOB_TITLE]->(jt:JobTitle)
                    WITH lr.resource_id AS lr_id, jt.name AS jt_name, count(r) AS c
                    WHERE c > 1 RETURN count(*) AS dup_pairs, sum(c) AS rels
                    """,
                    """
                    MATCH (lr:LearningResource)-[r:FOR_JOB_TITLE]->(jt:JobTitle)
                    WITH lr.resource_id AS lr_id, jt.name AS jt_name, count(r) AS c
                    WHERE c > 1
                    RETURN lr_id, jt_name, c ORDER BY c DESC LIMIT 5
                    """,
                ),
                (
                    "RECOMMENDS_RESOURCE",
                    """
                    MATCH (p:JobPromotion)-[r:RECOMMENDS_RESOURCE]->(lr:LearningResource)
                    WITH p.promotion_id AS pid, lr.resource_id AS rid, count(r) AS c
                    WHERE c > 1 RETURN count(*) AS dup_pairs, sum(c) AS rels
                    """,
                    """
                    MATCH (p:JobPromotion)-[r:RECOMMENDS_RESOURCE]->(lr:LearningResource)
                    WITH p.promotion_id AS pid, lr.resource_id AS rid, count(r) AS c
                    WHERE c > 1
                    RETURN pid, rid, c ORDER BY c DESC LIMIT 10
                    """,
                ),
                (
                    "RECOMMENDS_RESOURCE (含 stage)",
                    """
                    MATCH (p:JobPromotion)-[r:RECOMMENDS_RESOURCE]->(lr:LearningResource)
                    WITH p.promotion_id AS pid, lr.resource_id AS rid, r.stage AS stage, count(r) AS c
                    WHERE c > 1 RETURN count(*) AS dup_pairs, sum(c) AS rels
                    """,
                    """
                    MATCH (p:JobPromotion)-[r:RECOMMENDS_RESOURCE]->(lr:LearningResource)
                    WITH p.promotion_id AS pid, lr.resource_id AS rid, r.stage AS stage, count(r) AS c
                    WHERE c > 1
                    RETURN pid, rid, stage, c ORDER BY c DESC LIMIT 10
                    """,
                ),
                (
                    "RECOMMENDS_COMPETITION",
                    """
                    MATCH (p:JobPromotion)-[r:RECOMMENDS_COMPETITION]->(c:Competition)
                    WITH p.promotion_id AS pid, c.competition_id AS cid, count(r) AS c
                    WHERE c > 1 RETURN count(*) AS dup_pairs, sum(c) AS rels
                    """,
                    """
                    MATCH (p:JobPromotion)-[r:RECOMMENDS_COMPETITION]->(c:Competition)
                    WITH p.promotion_id AS pid, c.competition_id AS cid, count(r) AS c
                    WHERE c > 1
                    RETURN pid, cid, c ORDER BY c DESC LIMIT 10
                    """,
                ),
                (
                    "FOR_JOB_TITLE (JobPromotion)",
                    """
                    MATCH (jp:JobPromotion)-[r:FOR_JOB_TITLE]->(jt:JobTitle)
                    WITH jp.promotion_id AS pid, jt.name AS jt_name, count(r) AS c
                    WHERE c > 1 RETURN count(*) AS dup_pairs, sum(c) AS rels
                    """,
                    """
                    MATCH (jp:JobPromotion)-[r:FOR_JOB_TITLE]->(jt:JobTitle)
                    WITH jp.promotion_id AS pid, jt.name AS jt_name, count(r) AS c
                    WHERE c > 1
                    RETURN pid, jt_name, c ORDER BY c DESC LIMIT 5
                    """,
                ),
            ]
            for name, sum_q, sample_q in rel_checks:
                s = session.run(sum_q).single()
                print(
                    f"{name}: dup_pairs={s['dup_pairs'] or 0}, "
                    f"extra_rels={max(0, (s['rels'] or 0) - (s['dup_pairs'] or 0))}"
                )
                samples = list(session.run(sample_q))
                for r in samples:
                    print(f"  - {dict(r)}")

            print("\n=== 关系总量 vs CSV 预期（约） ===\n")
            counts = session.run(
                """
                MATCH (lr:LearningResource) WITH count(lr) AS lr
                MATCH ()-[a:FOR_JOB_TITLE]->() WITH lr, count(a) AS for_jt
                MATCH ()-[b:RECOMMENDS_RESOURCE]->() WITH lr, for_jt, count(b) AS rec_lr
                MATCH ()-[c:RECOMMENDS_COMPETITION]->() WITH lr, for_jt, rec_lr, count(c) AS rec_comp
                MATCH (jp:JobPromotion) WITH lr, for_jt, rec_lr, rec_comp, count(jp) AS promos
                RETURN lr, for_jt, rec_lr, rec_comp, promos
                """
            ).single()
            print(dict(counts))
            print("  预期 FOR_JOB_TITLE ≈ 1131 (master/learning_resources.csv)")
            print("  预期 RECOMMENDS_RESOURCE ≈ 1216 (promotion/promotion_learning_resources.csv)")
            print("  预期 RECOMMENDS_COMPETITION ≈ 340 (promotion/promotion_competitions.csv)")

            print("\n=== 晋升推荐：同 promotion+resource 跨 stage 合并为单边（MERGE 特性） ===\n")
            cross = list(
                session.run(
                    """
                    MATCH (p:JobPromotion)-[r:RECOMMENDS_RESOURCE]->(lr:LearningResource)
                    WITH p.promotion_id AS pid, lr.resource_id AS rid, collect(DISTINCT r.stage) AS stages, count(r) AS c
                    WHERE size(stages) > 1 OR c > 1
                    RETURN pid, rid, stages, c
                    ORDER BY c DESC LIMIT 15
                    """
                )
            )
            print(f"同 (promotion, resource) 多 stage 或多边: {len(cross)} 组（展示前 15）")
            for r in cross:
                print(f"  - {r['pid']} -> {r['rid']}: stages={r['stages']}, rel_count={r['c']}")

    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
