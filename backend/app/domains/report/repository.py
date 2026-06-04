"""DB 与 Neo4j 查询。"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.db import db_cursor
from app.domains.report.utils import json_dumps
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings, serialize_job_row
from app.infrastructure.salary import cypher_job_salary_display

_SALARY_DISP = cypher_job_salary_display()


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


def _parse_json_field(value: Any, default: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:  # noqa: BLE001
            return default
    return value if value is not None else default


def _query_jobs_by_ids(job_ids: List[str]) -> List[Dict[str, Any]]:
    ids = [str(x).strip() for x in job_ids if str(x).strip()]
    if not ids:
        return []
    uri, user, password, database = neo4j_settings()
    if not password:
        return []
    query = f"""
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) IN $ids
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      {_SALARY_DISP},
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


def _query_all_jobs_browse_lite() -> List[Dict[str, Any]]:
    uri, user, password, database = neo4j_settings()
    if not password:
        return []
    query = f"""
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      {_SALARY_DISP},
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location
    """
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        return [dict(r) for r in session.run(query)]


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


def fetch_report_row(user_id: int, report_id: int) -> Optional[Dict[str, Any]]:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, user_id, resume_id, title, primary_job_id, target_job_ids_json,
                   report_json, created_at, updated_at
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, user_id),
        )
        return cur.fetchone()


def fetch_report_for_export(user_id: int, report_id: int) -> Optional[Dict[str, Any]]:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, title, report_json
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, user_id),
        )
        return cur.fetchone()


def list_user_reports(user_id: int, limit: int) -> List[Dict[str, Any]]:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, title, resume_id, primary_job_id, target_job_ids_json, created_at, updated_at
            FROM career_reports
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        return list(cur.fetchall() or [])


def list_targets_for_reports(report_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    ids = [int(x) for x in report_ids if int(x) > 0]
    if not ids:
        return {}
    _ensure_report_tables()
    placeholders = ", ".join(["%s"] * len(ids))
    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            SELECT report_id, job_id, title, target_order
            FROM career_report_targets
            WHERE report_id IN ({placeholders})
            ORDER BY report_id ASC, target_order ASC
            """,
            tuple(ids),
        )
        rows = list(cur.fetchall() or [])
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["report_id"])].append(dict(row))
    return dict(grouped)


def fetch_report_json_by_ids(report_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    ids = [int(x) for x in report_ids if int(x) > 0]
    if not ids:
        return {}
    _ensure_report_tables()
    placeholders = ", ".join(["%s"] * len(ids))
    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            SELECT id, report_json
            FROM career_reports
            WHERE id IN ({placeholders})
            """,
            tuple(ids),
        )
        rows = list(cur.fetchall() or [])
    out: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        report_obj = _parse_json_field(row.get("report_json"), {})
        if isinstance(report_obj, dict):
            out[int(row["id"])] = report_obj
    return out


def report_owned_by_user(user_id: int, report_id: int) -> bool:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id FROM career_reports WHERE id = %s AND user_id = %s LIMIT 1",
            (report_id, user_id),
        )
        return cur.fetchone() is not None


def list_review_rows(report_id: int, *, limit: int = 80) -> List[Dict[str, Any]]:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, review_cycle, metrics_json, adjustment_json, created_at
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (report_id, limit),
        )
        return list(cur.fetchall() or [])


def list_review_metrics_asc(report_id: int) -> List[Dict[str, Any]]:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, metrics_json
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id ASC
            """,
            (report_id,),
        )
        return list(cur.fetchall() or [])


def count_reviews(report_id: int) -> int:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT COUNT(*) AS c FROM career_report_reviews WHERE report_id = %s",
            (report_id,),
        )
        row = cur.fetchone() or {}
        return int(row.get("c") or 0)


def insert_report(
    *,
    user_id: int,
    resume_id: int,
    title: str,
    primary_job_id: Optional[str],
    target_job_ids: List[str],
    report_obj: Dict[str, Any],
    meta_json: Dict[str, Any],
    target_insights: List[Dict[str, Any]],
) -> int:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO career_reports (
              user_id, resume_id, title, primary_job_id, target_job_ids_json, report_json, meta_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                resume_id,
                title[:160],
                primary_job_id or None,
                json_dumps(target_job_ids),
                json_dumps(report_obj),
                json_dumps(meta_json),
            ),
        )
        report_id = int(cur.lastrowid)
        primary = str(primary_job_id or "").strip()
        for idx, target in enumerate(target_insights):
            job_id = str(target.get("id") or "").strip()
            if not job_id:
                continue
            cur.execute(
                """
                INSERT INTO career_report_targets (
                  report_id, job_id, title, is_primary, target_order, source, meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    report_id,
                    job_id,
                    str(target.get("display_title") or target.get("title") or "")[:191] or None,
                    1 if job_id == primary else 0,
                    idx + 1,
                    "mixed",
                    json_dumps(
                        {
                            "match_score": (target.get("match_preview") or {}).get("match_score"),
                            "trend": target.get("trend"),
                        }
                    ),
                ),
            )
        return report_id


def insert_review(
    *,
    report_id: int,
    review_cycle: str,
    metrics_payload: Dict[str, Any],
    adjustment_payload: Dict[str, Any],
) -> int:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO career_report_reviews (report_id, review_cycle, metrics_json, adjustment_json)
            VALUES (%s, %s, %s, %s)
            """,
            (
                report_id,
                review_cycle,
                json_dumps(metrics_payload),
                json_dumps(adjustment_payload),
            ),
        )
        return int(cur.lastrowid)


def update_report_json(report_id: int, report_obj: Dict[str, Any]) -> None:
    _ensure_report_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            "UPDATE career_reports SET report_json = %s WHERE id = %s",
            (json_dumps(report_obj), report_id),
        )
