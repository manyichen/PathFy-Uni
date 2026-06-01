"""DB 与 Neo4j 查询。"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from app.db import db_cursor
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings, serialize_job_row

def _ensure_report_tables() -> None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS career_reports (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              user_id BIGINT UNSIGNED NOT NULL,
              resume_id BIGINT UNSIGNED NOT NULL,
              title VARCHAR(160) NOT NULL,
              primary_job_id VARCHAR(191) NULL,
              target_job_ids_json JSON NOT NULL,
              report_json LONGTEXT NOT NULL,
              meta_json JSON NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_career_reports_user_id_created_at (user_id, created_at DESC),
              CONSTRAINT fk_career_reports_user_id
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS career_report_targets (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              report_id BIGINT UNSIGNED NOT NULL,
              job_id VARCHAR(191) NOT NULL,
              title VARCHAR(191) NULL,
              is_primary TINYINT(1) NOT NULL DEFAULT 0,
              target_order INT NOT NULL DEFAULT 0,
              source VARCHAR(32) NOT NULL DEFAULT 'manual',
              meta_json JSON NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              UNIQUE KEY uk_report_job (report_id, job_id),
              KEY idx_career_report_targets_report_id_order (report_id, target_order),
              CONSTRAINT fk_career_report_targets_report_id
                FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS career_report_reviews (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              report_id BIGINT UNSIGNED NOT NULL,
              review_cycle VARCHAR(32) NOT NULL DEFAULT 'biweekly',
              metrics_json JSON NOT NULL,
              adjustment_json JSON NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_career_report_reviews_report_id_created_at (report_id, created_at DESC),
              CONSTRAINT fk_career_report_reviews_report_id
                FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def _query_jobs_by_ids(job_ids: List[str]) -> List[Dict[str, Any]]:
    ids = [str(x).strip() for x in job_ids if str(x).strip()]
    if not ids:
        return []
    uri, user, password, database = neo4j_settings()
    if not password:
        return []
    query = """
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) IN $ids
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.salary, '薪资面议') AS salary,
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
      coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
      coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
      coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
      coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
      coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
      coalesce(j.cap_req_social, 0.0) AS cap_req_social,
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
      coalesce(j.cap_conf_theory, 0.0) AS cap_conf_theory,
      coalesce(j.cap_conf_cross, 0.0) AS cap_conf_cross,
      coalesce(j.cap_conf_practice, 0.0) AS cap_conf_practice,
      coalesce(j.cap_conf_digital, 0.0) AS cap_conf_digital,
      coalesce(j.cap_conf_innovation, 0.0) AS cap_conf_innovation,
      coalesce(j.cap_conf_teamwork, 0.0) AS cap_conf_teamwork,
      coalesce(j.cap_conf_social, 0.0) AS cap_conf_social,
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth
    """
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"ids": ids})]
    cards = [serialize_job_row(r) for r in rows]
    order = {jid: idx for idx, jid in enumerate(ids)}
    cards.sort(key=lambda x: order.get(x["id"], 999999))
    return cards


def _query_job_relations(job_ids: List[str], max_per_job: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    ids = [str(x).strip() for x in job_ids if str(x).strip()]
    if not ids:
        return {}
    uri, user, password, database = neo4j_settings()
    if not password:
        return {}
    query = """
    UNWIND $ids AS jid
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = jid
    OPTIONAL MATCH (j)-[r:PROMOTE_TO|TRANSFER_TO]->(n:Job)
    WITH jid, j, r, n
    ORDER BY type(r) ASC, coalesce(n.title, n.name, '') ASC
    RETURN
      jid AS source_id,
      type(r) AS relation_type,
      coalesce(n.job_key, n.job_code, n.name, n.title, elementId(n)) AS target_id,
      coalesce(n.title, n.name, '未命名岗位') AS target_title,
      coalesce(n.company, '未知公司') AS target_company,
      coalesce(n.location, '未知地点') AS target_location
    """
    driver = neo4j_driver(uri, user, password)
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    with driver.session(database=database) as session:
        for row in session.run(query, {"ids": ids}):
            rec = dict(row)
            source_id = str(rec.get("source_id") or "").strip()
            relation_type = str(rec.get("relation_type") or "").strip()
            target_id = str(rec.get("target_id") or "").strip()
            if not source_id or not relation_type or not target_id:
                continue
            if len(out[source_id]) >= max_per_job:
                continue
            out[source_id].append(
                {
                    "relation_type": relation_type,
                    "target_id": target_id,
                    "target_title": rec.get("target_title"),
                    "target_company": rec.get("target_company"),
                    "target_location": rec.get("target_location"),
                }
            )
    return out


