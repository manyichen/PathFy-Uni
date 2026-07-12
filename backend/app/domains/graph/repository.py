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
from app.infrastructure.salary import neo4j_salary_properties
from app.domains.graph.incremental import job_key_for_row


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

def ensure_graph_schema(driver: Driver, database: str) -> None:
    """Create the uniqueness constraints required for idempotent MERGE operations."""
    constraints = (
        ("job_key", "Job", "job_key"),
        ("company_name", "Company", "name"),
        ("skill_name", "Skill", "name"),
        ("certificate_name", "Certificate", "name"),
        ("soft_skill_name", "SoftSkill", "name"),
        ("career_level_name", "CareerLevel", "name"),
        ("job_title_name", "JobTitle", "name"),
        ("graph_import_run_id", "GraphImportRun", "run_id"),
    )
    with driver.session(database=database) as session:
        for constraint_name, label, property_name in constraints:
            session.run(
                f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"
            )


def start_import_run(
    driver: Driver,
    database: str,
    *,
    run_id: str,
    source_id: str,
    mode: str,
    input_rows: int,
    changed_jobs: int,
) -> None:
    with driver.session(database=database) as session:
        session.run(
            """
            CREATE (run:GraphImportRun {
                run_id: $run_id,
                source_id: $source_id,
                mode: $mode,
                status: 'running',
                input_rows: $input_rows,
                changed_jobs: $changed_jobs,
                started_at: datetime()
            })
            """,
            run_id=run_id,
            source_id=source_id,
            mode=mode,
            input_rows=input_rows,
            changed_jobs=changed_jobs,
        )


def finish_import_run(
    driver: Driver,
    database: str,
    *,
    run_id: str,
    status: str,
    jobs_written: int,
    unchanged_jobs: int,
    pruned_jobs: int,
    error_count: int,
) -> None:
    with driver.session(database=database) as session:
        session.run(
            """
            MATCH (run:GraphImportRun {run_id: $run_id})
            SET run.status = $status,
                run.jobs_written = $jobs_written,
                run.unchanged_jobs = $unchanged_jobs,
                run.pruned_jobs = $pruned_jobs,
                run.error_count = $error_count,
                run.finished_at = datetime()
            """,
            run_id=run_id,
            status=status,
            jobs_written=jobs_written,
            unchanged_jobs=unchanged_jobs,
            pruned_jobs=pruned_jobs,
            error_count=error_count,
        )


def list_import_runs(driver: Driver, database: str, *, limit: int = 20) -> List[Dict[str, Any]]:
    with driver.session(database=database) as session:
        rows = session.run(
            """
            MATCH (run:GraphImportRun)
            RETURN run{.*} AS item
            ORDER BY run.started_at DESC
            LIMIT $limit
            """,
            limit=max(1, min(int(limit), 100)),
        )
        return [dict(row["item"]) for row in rows]

def merge_batch_to_neo4j(
    driver: Driver,
    database: str,
    batch_df: pd.DataFrame,
    ai_records: List[Dict[str, Any]],
    core_templates: set,
    *,
    run_id: str,
    source_id: str,
    fingerprints: Dict[str, str],
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
            job_key = job_key_for_row(row)
            raw_salary = normalize_text(row["salary"])
            sal = neo4j_salary_properties(raw_salary)

            # MERGE Job 节点
            tx.run(
                """
                MERGE (j:Job {job_key: $job_key})
                SET j.title = $title,
                    j.company = $company,
                    j.location = $location,
                    j.salary = $salary,
                    j.salary_norm = $salary_norm,
                    j.salary_negotiable = $salary_negotiable,
                    j.salary_parse_version = $salary_parse_version,
                    j.salary_monthly_min = $salary_monthly_min,
                    j.salary_monthly_max = $salary_monthly_max,
                    j.salary_bonus_months = $salary_bonus_months,
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
                    j.is_core_template = $is_core_template,
                    j.import_fingerprint = $import_fingerprint,
                    j.import_source_id = $source_id,
                    j.last_seen_run_id = $run_id,
                    j.last_imported_at = datetime(),
                    j.import_managed = true
                """,
                job_key=job_key,
                title=job_title,
                company=company_name,
                location=normalize_text(row["location"]),
                salary=sal["salary"],
                salary_norm=sal["salary_norm"],
                salary_negotiable=sal["salary_negotiable"],
                salary_parse_version=sal["salary_parse_version"],
                salary_monthly_min=sal.get("salary_monthly_min"),
                salary_monthly_max=sal.get("salary_monthly_max"),
                salary_bonus_months=sal.get("salary_bonus_months"),
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
                import_fingerprint=fingerprints[job_key],
                source_id=source_id,
                run_id=run_id,
            )

            # Reconcile relationships owned by this importer. Without this,
            # removed skills/certificates survive forever after an update.
            tx.run(
                """
                MATCH (j:Job {job_key: $job_key})-[r:REQUIRES|BELONGS_TO]->(n)
                WHERE n:Skill OR n:Certificate OR n:SoftSkill OR n:CareerLevel OR n:Company
                DELETE r
                """,
                job_key=job_key,
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
                        WITH s
                        MATCH (j:Job {job_key: $job_key})
                        MERGE (j)-[r:REQUIRES]->(s)
                        SET r.level = $level
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


def fetch_job_import_fingerprints(
    driver: Driver, database: str, job_keys: List[str]
) -> Dict[str, str]:
    """Fetch current fingerprints for only the candidate business keys."""
    if not job_keys:
        return {}
    with driver.session(database=database) as session:
        rows = session.run(
            """
            UNWIND $job_keys AS key
            MATCH (j:Job {job_key: key})
            RETURN j.job_key AS job_key, coalesce(j.import_fingerprint, '') AS fingerprint
            """,
            job_keys=job_keys,
        )
        return {str(row["job_key"]): str(row["fingerprint"] or "") for row in rows}


def mark_existing_jobs_seen(
    driver: Driver,
    database: str,
    *,
    job_keys: List[str],
    run_id: str,
    source_id: str,
) -> int:
    """Mark input keys before processing so a failed update is never pruned."""
    if not job_keys:
        return 0
    with driver.session(database=database) as session:
        record = session.run(
            """
            UNWIND $job_keys AS key
            MATCH (j:Job {job_key: key})
            SET j.last_seen_run_id = $run_id,
                j.import_source_id = $source_id,
                j.import_managed = true
            RETURN count(j) AS marked
            """,
            job_keys=job_keys,
            run_id=run_id,
            source_id=source_id,
        ).single()
        return int(record["marked"] if record else 0)


def prune_missing_jobs(
    driver: Driver, database: str, *, run_id: str, source_id: str
) -> int:
    """Delete stale jobs only inside one explicitly selected snapshot source."""
    with driver.session(database=database) as session:
        record = session.run(
            """
            MATCH (j:Job {import_source_id: $source_id, import_managed: true})
            WHERE coalesce(j.last_seen_run_id, '') <> $run_id
            WITH collect(j) AS stale, count(j) AS total
            FOREACH (j IN stale | DETACH DELETE j)
            RETURN total
            """,
            run_id=run_id,
            source_id=source_id,
        ).single()
        return int(record["total"] if record else 0)


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
            WITH collect(r) AS rels, count(r) AS total
            FOREACH (r IN rels | DELETE r)
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
    """旧 Job 层晋升边写入已废弃；晋升路径统一写入 JobPromotion。"""
    raise RuntimeError(
        "persist_promotion_edges 已废弃；请通过 JobTitle/JobPromotion 层生成和查询晋升路径。"
    )


# ============================================================
# 图谱统计
# ============================================================

def get_graph_statistics(driver: Driver, database: str) -> Dict[str, int]:
    """返回各标签节点数和各类型关系数。"""
    with driver.session(database=database) as session:
        stats: Dict[str, int] = {}

        # 节点统计
        for label in (
            "Job", "JobTitle", "JobPromotion", "Company", "Skill",
            "Certificate", "SoftSkill", "CareerLevel", "LearningResource", "Competition",
            "GraphImportRun",
        ):
            result = session.run(
                f"MATCH (n:{label}) RETURN count(n) AS cnt"
            )
            record = result.single()
            stats[f"{label.lower()}_count"] = int(record["cnt"]) if record else 0

        # 关系统计
        for rel_type in (
            "BELONGS_TO", "REQUIRES", "HAS_TITLE", "FOR_JOB_TITLE",
            "SIMILAR_FOR_LATERAL", "VERTICAL_UP",
        ):
            result = session.run(
                f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt"
            )
            record = result.single()
            stats[f"{rel_type.lower()}_count"] = int(record["cnt"]) if record else 0

        return stats
