"""Graph ETL 域：Neo4j 交互层（使用官方 neo4j 驱动）。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from neo4j import Driver

from app.domains.graph.constants import (
    SOFT_SKILL_DIMS,
    JobProfile,
    PromotionEdge,
    calc_career_score,
    normalize_text,
    normalize_title,
    parse_experience_years,
)


# ============================================================
# 图谱清空
# ============================================================

def clear_all_graph(driver: Driver, database: str) -> Dict[str, int]:
    """清空 Neo4j 中所有节点和关系，返回删除统计。"""
    with driver.session(database=database) as session:
        result = session.run("MATCH (n) DETACH DELETE n RETURN count(n) AS deleted")
        record = result.single()
        deleted = int(record["deleted"]) if record else 0
        return {"deleted_nodes": deleted}


# ============================================================
# 批量写入岗位（从 Excel 导入）
# ============================================================

def merge_batch_to_neo4j(
    driver: Driver,
    database: str,
    batch_df: pd.DataFrame,
    ai_records: List[Dict[str, Any]],
    core_templates: set,
) -> Dict[str, int]:
    """将一个批次的 DataFrame + LLM 提取结果写入 Neo4j。"""

    # 建立 idx -> ai_data 的映射
    idx_to_ai: Dict[int, Dict[str, Any]] = {}
    for item in ai_records:
        if isinstance(item, dict) and isinstance(item.get("idx"), int):
            idx_to_ai[item["idx"]] = item

    def _merge_tx(tx):
        written = 0
        for local_idx, row in batch_df.reset_index(drop=True).iterrows():
            ai_data = idx_to_ai.get(local_idx, {})
            job_title = normalize_text(row["name"])
            company_name = normalize_text(row["company"])
            exp_text = normalize_text(ai_data.get("experience_req", "未知"))
            demand = normalize_text(row["demand"])
            job_key = f"{normalize_title(job_title)}::{company_name.lower()}"

            # MERGE Job 节点
            tx.run(
                """
                MERGE (j:Job {job_key: $job_key})
                SET j.title = $title,
                    j.company = $company,
                    j.location = $location,
                    j.salary = $salary,
                    j.industry = $industry,
                    j.company_size = $company_size,
                    j.company_type = $company_type,
                    j.job_code = $job_code,
                    j.updated_date = $updated_date,
                    j.experience_text = $experience_text,
                    j.experience_years = $experience_years,
                    j.internship_req = $internship_req,
                    j.demand = $demand,
                    j.source_url = $source_url,
                    j.company_detail = $company_detail,
                    j.is_core_template = $is_core_template
                """,
                job_key=job_key,
                title=job_title,
                company=company_name,
                location=normalize_text(row["location"]),
                salary=normalize_text(row["salary"]),
                industry=normalize_text(row["industry"]),
                company_size=normalize_text(row["company_size"]),
                company_type=normalize_text(row["company_type"]),
                job_code=normalize_text(row["job_code"]),
                updated_date=normalize_text(row["updated_date"]),
                experience_text=exp_text,
                experience_years=parse_experience_years(exp_text),
                internship_req=normalize_text(ai_data.get("internship_req", "未知")),
                demand=demand,
                source_url=normalize_text(row["source_url"]),
                company_detail=normalize_text(row["company_detail"]),
                is_core_template=normalize_title(job_title) in core_templates,
            )

            # MERGE Company + BELONGS_TO
            tx.run(
                """
                MERGE (c:Company {name: $company})
                WITH c
                MATCH (j:Job {job_key: $job_key})
                MERGE (j)-[:BELONGS_TO]->(c)
                """,
                company=company_name,
                job_key=job_key,
            )

            # MERGE Skill 节点 + REQUIRES
            hard_skills = {
                normalize_text(x)
                for x in ai_data.get("hard_skills", [])
                if normalize_text(x)
            }
            for skill in hard_skills:
                tx.run(
                    """
                    MERGE (s:Skill {name: $name})
                    WITH s
                    MATCH (j:Job {job_key: $job_key})
                    MERGE (j)-[:REQUIRES]->(s)
                    """,
                    name=skill,
                    job_key=job_key,
                )

            # MERGE Certificate 节点 + REQUIRES
            certificates = ai_data.get("certificates", [])
            if isinstance(certificates, list):
                for cert in certificates:
                    cert_name = normalize_text(cert)
                    if not cert_name:
                        continue
                    tx.run(
                        """
                        MERGE (c:Certificate {name: $name})
                        WITH c
                        MATCH (j:Job {job_key: $job_key})
                        MERGE (j)-[:REQUIRES]->(c)
                        """,
                        name=cert_name,
                        job_key=job_key,
                    )

            # MERGE SoftSkill 节点 + REQUIRES
            soft_skills = ai_data.get("soft_skills", {})
            if isinstance(soft_skills, dict):
                for dim in SOFT_SKILL_DIMS:
                    level = normalize_text(soft_skills.get(dim, "未知")) or "未知"
                    tx.run(
                        """
                        MERGE (s:SoftSkill {name: $name})
                        SET s.level = $level
                        WITH s
                        MATCH (j:Job {job_key: $job_key})
                        MERGE (j)-[:REQUIRES]->(s)
                        """,
                        name=dim,
                        level=level,
                        job_key=job_key,
                    )

            # MERGE CareerLevel + BELONGS_TO
            tx.run(
                """
                MERGE (cl:CareerLevel {name: $level_name})
                WITH cl
                MATCH (j:Job {job_key: $job_key})
                MERGE (j)-[:BELONGS_TO]->(cl)
                """,
                level_name=exp_text or "未知",
                job_key=job_key,
            )

            written += 1

        return written

    with driver.session(database=database) as session:
        written = session.execute_write(_merge_tx)
        return {"written": written}


# ============================================================
# 获取所有 Job（用于晋升推断）
# ============================================================

def fetch_all_jobs(
    driver: Driver, database: str, *, include_inferred: bool = False
) -> List[JobProfile]:
    """从 Neo4j 获取所有 Job 节点，返回 JobProfile 列表。"""
    with driver.session(database=database) as session:
        rows = session.run(
            """
            MATCH (j:Job)
            WHERE coalesce(trim(toString(j.company)), '') <> ''
              AND coalesce(trim(j.title), '') <> ''
              AND ($include_inferred = true OR coalesce(j.source, '') <> 'inferred')
            RETURN
              j.job_key AS job_key,
              j.title AS title,
              j.company AS company,
              toFloat(coalesce(j.experience_years, 0.0)) AS experience_years,
              coalesce(j.location, '') AS location,
              coalesce(j.demand, '') AS demand
            """,
            include_inferred=include_inferred,
        )

        jobs: List[JobProfile] = []
        for row in rows:
            title = normalize_text(row["title"])
            company = normalize_text(row["company"])
            exp = float(row.get("experience_years") or 0.0)
            jobs.append(
                JobProfile(
                    job_key=str(row["job_key"]),
                    title=title,
                    company=company,
                    experience_years=exp,
                    location=normalize_text(row.get("location")),
                    demand=normalize_text(row.get("demand")),
                    career_score=calc_career_score(title, exp),
                )
            )
        return jobs


# ============================================================
# 晋升边管理
# ============================================================

def delete_edges_by_source(
    driver: Driver, database: str, source_tag: str
) -> int:
    """删除指定 source 的所有 VERTICAL_UP 边，返回删除数。"""
    with driver.session(database=database) as session:
        result = session.run(
            """
            MATCH ()-[r:VERTICAL_UP {source: $source}]->()
            WITH count(r) AS total
            DELETE r
            RETURN total
            """,
            source=source_tag,
        )
        record = result.single()
        return int(record["total"]) if record else 0


def persist_promotion_edges(
    driver: Driver,
    database: str,
    edges: List[PromotionEdge],
    source_tag: str,
) -> int:
    """批量写入晋升边（VERTICAL_UP 关系）。"""

    def _persist_tx(tx):
        count = 0
        for e in edges:
            tx.run(
                """
                MATCH (a:Job {job_key: $from_key})
                MATCH (b:Job {job_key: $to_key})
                MERGE (a)-[r:VERTICAL_UP {source: $source}]->(b)
                SET r.reason = $reason,
                    r.company = $company,
                    r.confidence = $confidence,
                    r.updated_at = datetime()
                """,
                from_key=e.from_key,
                to_key=e.to_key,
                source=source_tag,
                reason=e.reason,
                company=e.company,
                confidence=e.confidence,
            )
            count += 1
        return count

    with driver.session(database=database) as session:
        return session.execute_write(_persist_tx)


# ============================================================
# 图谱统计
# ============================================================

def get_graph_statistics(driver: Driver, database: str) -> Dict[str, int]:
    """返回各标签节点数和各类型关系数。"""
    with driver.session(database=database) as session:
        stats: Dict[str, int] = {}

        # 节点统计
        for label in ("Job", "Company", "Skill", "Certificate", "SoftSkill", "CareerLevel"):
            result = session.run(
                f"MATCH (n:{label}) RETURN count(n) AS cnt"
            )
            record = result.single()
            stats[f"{label.lower()}_count"] = int(record["cnt"]) if record else 0

        # 关系统计
        for rel_type in ("BELONGS_TO", "REQUIRES", "VERTICAL_UP"):
            result = session.run(
                f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt"
            )
            record = result.single()
            stats[f"{rel_type.lower()}_count"] = int(record["cnt"]) if record else 0

        return stats
