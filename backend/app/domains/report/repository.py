"""DB 与 Neo4j 查询。"""
from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.db import db_cursor
from app.domains.report.utils import json_dumps
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings, serialize_job_row
from app.infrastructure.salary import cypher_job_salary_display

_SALARY_DISP = cypher_job_salary_display()


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
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, user_id, resume_id, personality_profile_id, title, primary_job_id, target_job_ids_json,
                   report_json, settings_revision, report_version, created_at, updated_at
            FROM career_reports
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (report_id, user_id),
        )
        return cur.fetchone()


def fetch_report_for_export(user_id: int, report_id: int) -> Optional[Dict[str, Any]]:
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


def list_evidence_records(report_id: int) -> List[Dict[str, Any]]:
    """Return only user-confirmed outcome evidence with its review target scope."""
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT e.id, e.review_id, e.evidence_type, e.label, e.value_text,
                   e.source_url, e.source_text, e.verification_status, e.created_at,
                   rv.scope, rv.job_id
            FROM career_report_evidence_records e
            LEFT JOIN career_report_reviews rv ON rv.id=e.review_id
            WHERE e.report_id=%s AND e.verification_status='user_confirmed'
            ORDER BY e.id DESC
            LIMIT 100
            """,
            (report_id,),
        )
        return [dict(row) for row in (cur.fetchall() or [])]


def fetch_longitudinal_rows(user_id: int, report_id: int, resume_id: int) -> Dict[str, Any] | None:
    """Load confirmed longitudinal inputs. Review drafts are intentionally excluded."""
    with db_cursor() as (_, cur):
        cur.execute("SELECT id FROM career_reports WHERE id=%s AND user_id=%s", (report_id, user_id))
        if not cur.fetchone():
            return None
        cur.execute(
            "SELECT updated_at, create_time FROM student_resume WHERE id=%s AND user_id=%s LIMIT 1",
            (resume_id, user_id),
        )
        profile = cur.fetchone() or {}
        cur.execute(
            """
            SELECT id, review_cycle, scope, job_id, metrics_json, adjustment_json, created_at
            FROM career_report_reviews WHERE report_id=%s ORDER BY id DESC LIMIT 120
            """,
            (report_id,),
        )
        reviews = list(cur.fetchall() or [])
        cur.execute(
            """
            SELECT id, review_id, status, scope, job_id, diff_json, decision_json,
                   created_at, decided_at
            FROM career_report_plan_versions WHERE report_id=%s ORDER BY id DESC LIMIT 120
            """,
            (report_id,),
        )
        versions = list(cur.fetchall() or [])
        cur.execute(
            """
            SELECT id, review_id, plan_version_id, event_type, action_ref, payload_json, created_at
            FROM career_report_action_events WHERE report_id=%s ORDER BY id DESC LIMIT 500
            """,
            (report_id,),
        )
        events = list(cur.fetchall() or [])
        return {
            "profile_updated_at": profile.get("updated_at") or profile.get("create_time"),
            "reviews": reviews,
            "versions": versions,
            "events": events,
        }


def ensure_report_experiment_assignment(
    user_id: int,
    report_id: int,
    *,
    experiment_key: str = "career_pacing_v1",
) -> Dict[str, Any] | None:
    seed = f"{user_id}:{report_id}:{experiment_key}".encode("utf-8")
    bucket = int(hashlib.sha256(seed).hexdigest()[:8], 16) % 100
    variant = "personalized_v1" if bucket < 50 else "baseline"
    with db_cursor() as (_, cur):
        cur.execute("SELECT id FROM career_reports WHERE id=%s AND user_id=%s", (report_id, user_id))
        if not cur.fetchone():
            return None
        cur.execute(
            """
            INSERT IGNORE INTO career_report_experiment_assignments (
              report_id, experiment_key, variant, bucket
            ) VALUES (%s, %s, %s, %s)
            """,
            (report_id, experiment_key, variant, bucket),
        )
        created = cur.rowcount == 1
        cur.execute(
            """
            SELECT experiment_key, variant, bucket, assigned_at
            FROM career_report_experiment_assignments
            WHERE report_id=%s AND experiment_key=%s
            """,
            (report_id, experiment_key),
        )
        assignment = cur.fetchone() or {}
        if created:
            cur.execute(
                """
                INSERT INTO career_report_action_events (
                  report_id, event_type, payload_json
                ) VALUES (%s, 'experiment_assigned', %s)
                """,
                (report_id, json_dumps({"experiment_key": experiment_key, "variant": variant, "bucket": bucket})),
            )
        return {**assignment, "created": created}


def get_report_experiment_assignment(
    user_id: int,
    report_id: int,
    *,
    experiment_key: str = "career_pacing_v1",
) -> Dict[str, Any] | None:
    """Read assignment without turning report/history loading into a write transaction."""
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT a.experiment_key, a.variant, a.bucket, a.assigned_at
            FROM career_report_experiment_assignments a
            JOIN career_reports r ON r.id=a.report_id
            WHERE a.report_id=%s AND a.experiment_key=%s AND r.user_id=%s
            """,
            (report_id, experiment_key, user_id),
        )
        return cur.fetchone()


def purge_expired_review_drafts(user_id: int, *, retention_days: int = 90) -> int:
    cutoff = datetime.utcnow() - timedelta(days=max(30, min(365, retention_days)))
    with db_cursor() as (_, cur):
        cur.execute(
            """
            DELETE d FROM career_report_review_drafts d
            JOIN career_reports r ON r.id=d.report_id
            WHERE r.user_id=%s AND d.status='draft' AND d.created_at < %s
            """,
            (user_id, cutoff),
        )
        return int(cur.rowcount or 0)


def list_user_reports(user_id: int, limit: int) -> List[Dict[str, Any]]:
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
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id FROM career_reports WHERE id = %s AND user_id = %s LIMIT 1",
            (report_id, user_id),
        )
        return cur.fetchone() is not None


def list_review_rows(report_id: int, *, limit: int = 80) -> List[Dict[str, Any]]:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, review_cycle, scope, job_id, metrics_json, adjustment_json, created_at
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (report_id, limit),
        )
        return list(cur.fetchall() or [])


def list_review_metrics_asc(report_id: int) -> List[Dict[str, Any]]:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, review_cycle, scope, job_id, metrics_json
            FROM career_report_reviews
            WHERE report_id = %s
            ORDER BY id ASC
            """,
            (report_id,),
        )
        return list(cur.fetchall() or [])


def count_reviews(
    report_id: int,
    *,
    scope: str | None = None,
    job_id: str | None = None,
    review_cycle: str | None = None,
) -> int:
    with db_cursor() as (_, cur):
        cycle_sql = " AND review_cycle=%s" if review_cycle else ""
        if scope == "target" and job_id:
            cur.execute(
                f"""
                SELECT COUNT(*) AS c FROM career_report_reviews
                WHERE report_id=%s AND scope='target' AND job_id=%s
                {cycle_sql}
                """,
                (report_id, job_id, review_cycle) if review_cycle else (report_id, job_id),
            )
        elif scope == "all":
            cur.execute(
                f"SELECT COUNT(*) AS c FROM career_report_reviews WHERE report_id=%s AND scope='all'{cycle_sql}",
                (report_id, review_cycle) if review_cycle else (report_id,),
            )
        else:
            cur.execute(
                f"SELECT COUNT(*) AS c FROM career_report_reviews WHERE report_id = %s{cycle_sql}",
                (report_id, review_cycle) if review_cycle else (report_id,),
            )
        row = cur.fetchone() or {}
        return int(row.get("c") or 0)


def insert_review_draft(
    *,
    user_id: int,
    report_id: int,
    review_cycle: str,
    scope: str,
    job_id: str | None,
    review_text: str,
    candidates: List[Dict[str, Any]],
    extraction: Dict[str, Any],
) -> int | None:
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id FROM career_reports WHERE id=%s AND user_id=%s LIMIT 1",
            (report_id, user_id),
        )
        if not cur.fetchone():
            return None
        cur.execute(
            """
            INSERT INTO career_report_review_drafts (
              report_id, review_cycle, scope, job_id, review_text,
              candidates_json, extraction_json, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft')
            """,
            (
                report_id,
                review_cycle,
                scope,
                job_id,
                review_text,
                json_dumps(candidates),
                json_dumps(extraction),
            ),
        )
        return int(cur.lastrowid)


def fetch_review_draft(user_id: int, draft_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT d.*, r.report_version, r.primary_job_id, r.target_job_ids_json,
                   r.resume_id, r.report_json
            FROM career_report_review_drafts d
            JOIN career_reports r ON r.id=d.report_id
            WHERE d.id=%s AND r.user_id=%s
            LIMIT 1
            """,
            (draft_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_plan_version_rows(user_id: int, report_id: int, *, limit: int = 50) -> List[Dict[str, Any]]:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT v.id, v.review_id, v.base_report_version, v.status, v.scope,
                   v.job_id, v.diff_json, v.decision_json, v.created_at, v.decided_at,
                   r.report_version AS current_report_version
            FROM career_report_plan_versions v
            JOIN career_reports r ON r.id=v.report_id
            WHERE v.report_id=%s AND r.user_id=%s
            ORDER BY v.id DESC
            LIMIT %s
            """,
            (report_id, user_id, limit),
        )
        return list(cur.fetchall() or [])


def fetch_plan_version(user_id: int, version_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT v.*, r.user_id, r.report_json, r.report_version, r.primary_job_id
            FROM career_report_plan_versions v
            JOIN career_reports r ON r.id=v.report_id
            WHERE v.id=%s AND r.user_id=%s
            LIMIT 1
            """,
            (version_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_report_privacy_bundle(user_id: int, report_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, resume_id, title, primary_job_id, target_job_ids_json,
                   report_json, meta_json, created_at, updated_at
            FROM career_reports WHERE id=%s AND user_id=%s LIMIT 1
            """,
            (report_id, user_id),
        )
        report = cur.fetchone()
        if not report:
            return None
        tables = {
            "targets": "career_report_targets",
            "reviews": "career_report_reviews",
            "review_drafts": "career_report_review_drafts",
            "plan_versions": "career_report_plan_versions",
            "evidence_records": "career_report_evidence_records",
            "action_events": "career_report_action_events",
            "experiment_assignments": "career_report_experiment_assignments",
            "behavioral_preference_evidence": "behavioral_preference_evidence",
        }
        result: Dict[str, Any] = {"report": dict(report)}
        for key, table in tables.items():
            cur.execute(f"SELECT * FROM {table} WHERE report_id=%s ORDER BY id", (report_id,))
            result[key] = list(cur.fetchall() or [])
        return result


def delete_user_report(user_id: int, report_id: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute("DELETE FROM career_reports WHERE id=%s AND user_id=%s", (report_id, user_id))
        return cur.rowcount == 1


def report_operations_metrics() -> Dict[str, Any]:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM career_reports) AS report_count,
              (SELECT COUNT(*) FROM career_report_review_drafts) AS draft_count,
              (SELECT COUNT(*) FROM career_report_review_drafts WHERE status='confirmed') AS confirmed_draft_count,
              (SELECT COUNT(*) FROM career_report_reviews) AS review_count,
              (SELECT COUNT(*) FROM career_report_plan_versions) AS proposal_count,
              (SELECT COUNT(*) FROM career_report_plan_versions WHERE status='accepted') AS accepted_proposal_count,
              (SELECT COUNT(*) FROM career_report_plan_versions WHERE status='rejected') AS rejected_proposal_count,
              (SELECT COUNT(*) FROM career_report_action_events WHERE event_type='action_completed') AS completion_event_count,
              (SELECT COUNT(*) FROM career_report_action_events WHERE event_type='preference_strategy_accepted') AS preference_strategy_accepted_count,
              (SELECT COUNT(*) FROM career_report_action_events WHERE event_type='preference_strategy_edited') AS preference_strategy_edited_count,
              (SELECT COUNT(*) FROM behavioral_preference_evidence WHERE user_confirmed=1) AS confirmed_preference_evidence_count,
              (SELECT COUNT(*) FROM match_runs WHERE preference_mode='tie_break') AS preference_tie_break_requested_count,
              (SELECT COUNT(*) FROM match_runs WHERE preference_experiment_variant='tie_break') AS preference_tie_break_variant_count,
              (SELECT COUNT(DISTINCT r.user_id) FROM career_report_reviews rv JOIN career_reports r ON r.id=rv.report_id WHERE rv.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)) AS active_reviewer_count_30d
            """
        )
        totals = dict(cur.fetchone() or {})
        cur.execute(
            """
            SELECT
              assignment.experiment_key,
              assignment.variant,
              COUNT(*) AS assignments,
              SUM(CASE WHEN COALESCE(review.review_count, 0) > 0 THEN 1 ELSE 0 END) AS activated_reports,
              SUM(COALESCE(review.review_count, 0)) AS review_count,
              SUM(COALESCE(proposal.proposal_count, 0)) AS proposal_count,
              SUM(COALESCE(proposal.accepted_proposal_count, 0)) AS accepted_proposal_count,
              SUM(COALESCE(action.completion_event_count, 0)) AS completion_event_count
            FROM career_report_experiment_assignments assignment
            LEFT JOIN (
              SELECT report_id, COUNT(*) AS review_count
              FROM career_report_reviews
              GROUP BY report_id
            ) review ON review.report_id=assignment.report_id
            LEFT JOIN (
              SELECT
                report_id,
                COUNT(*) AS proposal_count,
                SUM(CASE WHEN status='accepted' THEN 1 ELSE 0 END) AS accepted_proposal_count
              FROM career_report_plan_versions
              GROUP BY report_id
            ) proposal ON proposal.report_id=assignment.report_id
            LEFT JOIN (
              SELECT report_id, COUNT(*) AS completion_event_count
              FROM career_report_action_events
              WHERE event_type='action_completed'
              GROUP BY report_id
            ) action ON action.report_id=assignment.report_id
            GROUP BY assignment.experiment_key, assignment.variant
            ORDER BY assignment.experiment_key, assignment.variant
            """
        )
        totals["experiments"] = list(cur.fetchall() or [])
        return totals


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
    settings_revision: int | None = None,
    config_snapshot: Dict[str, Any] | None = None,
    personality_profile_id: int | None = None,
) -> int:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO career_reports (
              user_id, resume_id, personality_profile_id, title, primary_job_id, target_job_ids_json, report_json, meta_json,
              settings_revision,config_snapshot_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                resume_id,
                personality_profile_id,
                title[:160],
                primary_job_id or None,
                json_dumps(target_job_ids),
                json_dumps(report_obj),
                json_dumps(meta_json),
                settings_revision,
                json_dumps(config_snapshot or {}),
            ),
        )
        report_id = int(cur.lastrowid)
        initial_job = meta_json.get("enrichment_job") if isinstance(meta_json.get("enrichment_job"), dict) else {}
        cur.execute(
            """
            INSERT INTO career_report_enrichment_jobs (
              report_id, attempt, status, scope, stage, progress, requested_at, started_at, completed_at, error
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                report_id,
                int(initial_job.get("attempt") or 0),
                str(initial_job.get("status") or "pending"),
                str(initial_job.get("scope") or "full"),
                str(initial_job.get("stage") or initial_job.get("status") or "pending"),
                int(initial_job.get("progress") or (100 if initial_job.get("status") == "completed" else 0)),
                initial_job.get("requested_at"),
                initial_job.get("started_at"),
                initial_job.get("completed_at"),
                str(initial_job.get("error") or "")[:500] or None,
            ),
        )
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


def get_report_config_snapshot(user_id: int, report_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute("SELECT settings_revision,config_snapshot_json FROM career_reports WHERE id=%s AND user_id=%s", (report_id, user_id))
        row = cur.fetchone()
    if not row: return None
    raw = row.get("config_snapshot_json")
    return {"revision": row.get("settings_revision"), "settings": json.loads(raw) if isinstance(raw, str) else (raw or {})}


def _enrichment_job_payload(row: Dict[str, Any] | None) -> Dict[str, Any]:
    if not row:
        return {"status": "pending", "attempt": 0, "scope": "full", "stage": "pending", "progress": 0}
    out = dict(row)
    for source, target in (("timing_json", "timing_ms"), ("quality_json", "quality")):
        value = _parse_json_field(out.pop(source, None), None)
        if value is not None:
            out[target] = value
    for key in ("requested_at", "started_at", "completed_at", "updated_at"):
        if isinstance(out.get(key), datetime):
            out[key] = out[key].strftime("%Y-%m-%d %H:%M:%S")
    out["progress"] = int(out.get("progress") or 0)
    out["attempt"] = int(out.get("attempt") or 0)
    out["error"] = str(out.get("error") or "")
    return out


def claim_report_enrichment(user_id: int, report_id: int, *, scope: str = "full") -> Tuple[bool, Dict[str, Any]]:
    """Queue on a dedicated row so slow AI work never locks the report document."""
    with db_cursor() as (_, cur):
        cur.execute("SELECT id FROM career_reports WHERE id=%s AND user_id=%s", (report_id, user_id))
        if not cur.fetchone():
            return False, {"status": "missing"}
        cur.execute("SELECT * FROM career_report_enrichment_jobs WHERE report_id=%s FOR UPDATE", (report_id,))
        current = _enrichment_job_payload(cur.fetchone())
        if current.get("status") in ("queued", "running"):
            anchor = current.get("started_at") or current.get("requested_at")
            try:
                stale = datetime.strptime(str(anchor), "%Y-%m-%d %H:%M:%S") < datetime.utcnow() - timedelta(minutes=8)
            except (TypeError, ValueError):
                stale = False
            if not stale:
                return False, current
        attempt = int(current.get("attempt") or 0) + 1
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO career_report_enrichment_jobs (
              report_id, attempt, status, scope, stage, progress, error, requested_at, started_at, completed_at
            ) VALUES (%s,%s,'queued',%s,'queued',0,NULL,%s,NULL,NULL)
            ON DUPLICATE KEY UPDATE attempt=VALUES(attempt), status='queued', scope=VALUES(scope),
              stage='queued', progress=0, error=NULL, timing_json=NULL, quality_json=NULL,
              requested_at=VALUES(requested_at), started_at=NULL, completed_at=NULL
            """,
            (report_id, attempt, scope, now),
        )
        return True, {
            "status": "queued", "attempt": attempt, "scope": scope, "stage": "queued", "progress": 0,
            "requested_at": now, "started_at": None, "completed_at": None, "error": "",
        }


def update_report_enrichment_status(
    report_id: int,
    status: str,
    *,
    error: str = "",
    timing_ms: Dict[str, Any] | None = None,
    stage: str | None = None,
    progress: int | None = None,
    quality: Dict[str, Any] | None = None,
    expected_attempt: int | None = None,
) -> Dict[str, Any]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT * FROM career_report_enrichment_jobs WHERE report_id=%s FOR UPDATE", (report_id,))
        row = cur.fetchone()
        if not row:
            return {"status": "missing"}
        job = _enrichment_job_payload(row)
        if expected_attempt is not None and int(job.get("attempt") or 0) != int(expected_attempt):
            return {**job, "superseded": True}
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        job = {**job, "status": status, "error": error[:500]}
        if status == "running":
            job["started_at"] = job.get("started_at") or now
        if status in ("completed", "failed"):
            job["completed_at"] = now
        if stage is not None:
            job["stage"] = str(stage)[:64]
        if progress is not None:
            job["progress"] = max(0, min(100, int(progress)))
        if timing_ms is not None:
            job["timing_ms"] = timing_ms
        if quality is not None:
            job["quality"] = quality
        cur.execute(
            """
            UPDATE career_report_enrichment_jobs
            SET status=%s, error=%s, stage=%s, progress=%s, timing_json=%s, quality_json=%s,
                started_at=%s, completed_at=%s
            WHERE report_id=%s
            """,
            (
                status, job.get("error") or None, job.get("stage") or status, int(job.get("progress") or 0),
                json_dumps(job.get("timing_ms")) if job.get("timing_ms") is not None else row.get("timing_json"),
                json_dumps(job.get("quality")) if job.get("quality") is not None else row.get("quality_json"),
                job.get("started_at"), job.get("completed_at"), report_id,
            ),
        )
        return dict(job)


def get_report_enrichment_status(user_id: int, report_id: int) -> Dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT j.* FROM career_reports r
            LEFT JOIN career_report_enrichment_jobs j ON j.report_id=r.id
            WHERE r.id=%s AND r.user_id=%s LIMIT 1
            """,
            (report_id, user_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    return _enrichment_job_payload(row)


def update_report_json_if_version(
    user_id: int,
    report_id: int,
    expected_version: int,
    report_obj: Dict[str, Any],
) -> bool:
    """Compare-and-swap report_json so concurrent user writes cannot be lost."""
    with db_cursor() as (_, cur):
        cur.execute(
            """
            UPDATE career_reports
            SET report_json=%s, report_version=report_version + 1
            WHERE id=%s AND user_id=%s AND report_version=%s
            """,
            (json_dumps(report_obj), report_id, user_id, expected_version),
        )
        return cur.rowcount == 1


def commit_action_progress_update(
    *,
    user_id: int,
    report_id: int,
    expected_version: int,
    report_obj: Dict[str, Any],
    event_type: str,
    action_ref: str,
    payload: Dict[str, Any],
) -> bool:
    """Atomically persist action state and the event used by longitudinal learning."""
    with db_cursor() as (_, cur):
        cur.execute(
            """
            UPDATE career_reports
            SET report_json=%s, report_version=report_version + 1
            WHERE id=%s AND user_id=%s AND report_version=%s
            """,
            (json_dumps(report_obj), report_id, user_id, expected_version),
        )
        if cur.rowcount != 1:
            return False
        cur.execute(
            """
            INSERT INTO career_report_action_events (
              report_id, event_type, action_ref, payload_json
            ) VALUES (%s, %s, %s, %s)
            """,
            (report_id, event_type[:32], action_ref[:191], json_dumps(payload)),
        )
        return True


def _json_member_path(value: str) -> str:
    """Return a quoted MySQL JSON member path for a trusted application key."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'$.action_progress."{escaped}"'


def commit_action_done_patch(
    *,
    user_id: int,
    report_id: int,
    expected_version: int,
    plan_index: int,
    item_index: int,
    action_index: int,
    action_uid: str,
    progress_key: str,
    done: bool,
    done_at: str | None,
    event_type: str,
    action_ref: str,
    payload: Dict[str, Any],
) -> bool:
    """Persist a checkbox change without sending the complete report back to MySQL.

    Career reports can be large enough for managed MySQL proxies to terminate a
    connection while receiving a whole-document UPDATE.  The indexes are safe to
    use because ``report_version`` makes this patch a compare-and-swap operation.
    """
    plan_index = int(plan_index)
    item_index = int(item_index)
    action_index = int(action_index)
    if min(plan_index, item_index, action_index) < 0:
        return False

    action_path = (
        f"$.plans_by_target[{plan_index}].next_month_plan.items[{item_index}]"
        f".custom_actions[{action_index}]"
    )
    done_path = f"{action_path}.done"
    done_at_path = f"{action_path}.done_at"
    stable_progress_path = _json_member_path(action_uid)
    legacy_progress_path = _json_member_path(progress_key)
    entry_json = json_dumps(
        {"done": True, "done_at": done_at} if done else {"done": False}
    )

    set_expression = """
        JSON_SET(
          report_json,
          %s, JSON_EXTRACT(%s, '$'),
          '$.action_progress',
            CASE
              WHEN JSON_TYPE(JSON_EXTRACT(report_json, '$.action_progress')) = 'OBJECT'
              THEN JSON_EXTRACT(report_json, '$.action_progress')
              ELSE JSON_OBJECT()
            END,
          %s, JSON_EXTRACT(%s, '$'),
          %s, JSON_EXTRACT(%s, '$')
        )
    """
    params: list[Any] = [
        done_path,
        "true" if done else "false",
        stable_progress_path,
        entry_json,
        legacy_progress_path,
        entry_json,
    ]
    if done:
        set_expression = f"JSON_SET({set_expression}, %s, %s)"
        params.extend([done_at_path, done_at])
    else:
        set_expression = f"JSON_REMOVE({set_expression}, %s)"
        params.append(done_at_path)

    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            UPDATE career_reports
            SET report_json={set_expression}, report_version=report_version + 1
            WHERE id=%s AND user_id=%s AND report_version=%s
            """,
            (*params, report_id, user_id, expected_version),
        )
        if cur.rowcount != 1:
            return False
        cur.execute(
            """
            INSERT INTO career_report_action_events (
              report_id, event_type, action_ref, payload_json
            ) VALUES (%s, %s, %s, %s)
            """,
            (report_id, event_type[:32], action_ref[:191], json_dumps(payload)),
        )
        return True


def commit_review_update(
    *,
    user_id: int,
    report_id: int,
    expected_version: int,
    report_obj: Dict[str, Any],
    review_cycle: str,
    scope: str,
    job_id: str | None,
    metrics_payload: Dict[str, Any],
    adjustment_payload: Dict[str, Any],
) -> int | None:
    """Persist a report mutation and its review atomically with optimistic locking."""
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT report_version FROM career_reports WHERE id=%s AND user_id=%s FOR UPDATE",
            (report_id, user_id),
        )
        row = cur.fetchone()
        if not row or int(row.get("report_version") or 0) != expected_version:
            return None
        cur.execute(
            """
            INSERT INTO career_report_reviews (
              report_id, review_cycle, scope, job_id, metrics_json, adjustment_json
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                report_id,
                review_cycle,
                scope,
                job_id,
                json_dumps(metrics_payload),
                json_dumps(adjustment_payload),
            ),
        )
        review_id = int(cur.lastrowid)
        evaluation = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
        latest = evaluation.get("latest_review") if isinstance(evaluation.get("latest_review"), dict) else None
        if latest is not None and latest.get("review_id") is None:
            latest["review_id"] = review_id
        latest_by_target = evaluation.get("latest_reviews_by_target")
        if isinstance(latest_by_target, dict):
            for target_latest in latest_by_target.values():
                if isinstance(target_latest, dict) and target_latest.get("review_id") is None:
                    target_latest["review_id"] = review_id
        development = report_obj.get("development_lines") if isinstance(report_obj.get("development_lines"), dict) else {}
        for line in development.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for point in line.get("timeline") or []:
                if isinstance(point, dict) and point.get("kind") == "review" and point.get("review_id") is None:
                    point["review_id"] = review_id
        cur.execute(
            """
            UPDATE career_reports
            SET report_json=%s, report_version=report_version + 1
            WHERE id=%s AND user_id=%s
            """,
            (json_dumps(report_obj), report_id, user_id),
        )
        return review_id


def commit_confirmed_review(
    *,
    user_id: int,
    report_id: int,
    draft_id: int,
    expected_version: int,
    report_obj: Dict[str, Any],
    review_cycle: str,
    scope: str,
    job_id: str | None,
    metrics_payload: Dict[str, Any],
    adjustment_payload: Dict[str, Any],
    proposed_report: Dict[str, Any] | None,
    plan_diff: List[Dict[str, Any]],
    evidence_records: List[Dict[str, Any]],
    preference_evidence: List[Dict[str, Any]] | None = None,
) -> Dict[str, int | None] | None:
    """Confirm a draft and create a non-applied plan proposal in one transaction."""
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT report_version FROM career_reports WHERE id=%s AND user_id=%s FOR UPDATE",
            (report_id, user_id),
        )
        row = cur.fetchone()
        if not row or int(row.get("report_version") or 0) != expected_version:
            return None
        cur.execute(
            """
            SELECT status FROM career_report_review_drafts
            WHERE id=%s AND report_id=%s FOR UPDATE
            """,
            (draft_id, report_id),
        )
        draft = cur.fetchone()
        if not draft or str(draft.get("status") or "") != "draft":
            return None
        cur.execute(
            """
            INSERT INTO career_report_reviews (
              report_id, review_cycle, scope, job_id, metrics_json, adjustment_json
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                report_id,
                review_cycle,
                scope,
                job_id,
                json_dumps(metrics_payload),
                json_dumps(adjustment_payload),
            ),
        )
        review_id = int(cur.lastrowid)

        evaluation = report_obj.get("evaluation") if isinstance(report_obj.get("evaluation"), dict) else {}
        latest = evaluation.get("latest_review") if isinstance(evaluation.get("latest_review"), dict) else None
        if latest is not None and latest.get("review_id") is None:
            latest["review_id"] = review_id
        latest_by_target = evaluation.get("latest_reviews_by_target")
        if isinstance(latest_by_target, dict):
            for target_latest in latest_by_target.values():
                if isinstance(target_latest, dict) and target_latest.get("review_id") is None:
                    target_latest["review_id"] = review_id
        development = report_obj.get("development_lines") if isinstance(report_obj.get("development_lines"), dict) else {}
        for line in development.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for point in line.get("timeline") or []:
                if isinstance(point, dict) and point.get("kind") == "review" and point.get("review_id") is None:
                    point["review_id"] = review_id

        next_version = expected_version + 1
        proposal_id: int | None = None
        if proposed_report is not None and plan_diff:
            cur.execute(
                """
                INSERT INTO career_report_plan_versions (
                  report_id, review_id, base_report_version, status, scope, job_id,
                  snapshot_json, diff_json
                ) VALUES (%s, %s, %s, 'proposed', %s, %s, %s, %s)
                """,
                (
                    report_id,
                    review_id,
                    next_version,
                    scope,
                    job_id,
                    json_dumps(proposed_report),
                    json_dumps(plan_diff),
                ),
            )
            proposal_id = int(cur.lastrowid)

        cur.execute(
            """
            UPDATE career_reports
            SET report_json=%s, report_version=report_version + 1
            WHERE id=%s AND user_id=%s
            """,
            (json_dumps(report_obj), report_id, user_id),
        )
        cur.execute(
            """
            UPDATE career_report_review_drafts
            SET status='confirmed', confirmed_at=CURRENT_TIMESTAMP
            WHERE id=%s AND report_id=%s
            """,
            (draft_id, report_id),
        )
        for evidence in evidence_records:
            if not isinstance(evidence, dict):
                continue
            cur.execute(
                """
                INSERT INTO career_report_evidence_records (
                  report_id, review_id, evidence_type, label, value_text,
                  source_url, source_text, verification_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    report_id,
                    review_id,
                    str(evidence.get("evidence_type") or "other")[:32],
                    str(evidence.get("label") or "复盘证据")[:191],
                    str(evidence.get("value") or "")[:2000] or None,
                    str(evidence.get("source_url") or "")[:2000] or None,
                    str(evidence.get("source_text") or "")[:2000] or None,
                    "user_confirmed",
                ),
            )
        for evidence in preference_evidence or []:
            if not isinstance(evidence, dict):
                continue
            cur.execute(
                """
                INSERT INTO behavioral_preference_evidence (
                  user_id, report_id, review_id, axis_code, observed_value,
                  source_type, source_json, user_confirmed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                """,
                (
                    user_id,
                    report_id,
                    review_id,
                    str(evidence.get("axis_code") or "")[:32],
                    evidence.get("observed_value"),
                    str(evidence.get("source_type") or "confirmed_review_signal")[:32],
                    json_dumps(evidence.get("source") or {}),
                ),
            )
        cur.execute(
            """
            INSERT INTO career_report_action_events (
              report_id, review_id, plan_version_id, event_type, payload_json
            ) VALUES (%s, %s, %s, 'review_confirmed', %s)
            """,
            (report_id, review_id, proposal_id, json_dumps({"status": adjustment_payload.get("review_status")})),
        )
        return {"review_id": review_id, "proposal_id": proposal_id}


def commit_preference_strategy_update(
    *,
    user_id: int,
    report_id: int,
    expected_version: int,
    report_obj: Dict[str, Any],
    decision: str,
) -> bool:
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT report_version FROM career_reports WHERE id=%s AND user_id=%s FOR UPDATE",
            (report_id, user_id),
        )
        row = cur.fetchone()
        if not row or int(row.get("report_version") or 0) != expected_version:
            return False
        cur.execute(
            "UPDATE career_reports SET report_json=%s, report_version=report_version + 1 WHERE id=%s AND user_id=%s",
            (json_dumps(report_obj), report_id, user_id),
        )
        cur.execute(
            """
            INSERT INTO career_report_action_events (report_id, event_type, payload_json)
            VALUES (%s, %s, %s)
            """,
            (
                report_id,
                "preference_strategy_accepted" if decision == "accept" else "preference_strategy_edited",
                json_dumps({"decision": decision, "strategy_version": "preference-strategy-v1"}),
            ),
        )
        return True


def commit_plan_proposal_decision(
    *,
    user_id: int,
    version_id: int,
    decision: str,
    accepted_change_ids: List[str],
    report_obj: Dict[str, Any] | None,
) -> str:
    """Accept or reject a proposal. Returns accepted/rejected/stale/not_found/conflict."""
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT v.report_id, v.review_id, v.base_report_version, v.status,
                   r.report_version
            FROM career_report_plan_versions v
            JOIN career_reports r ON r.id=v.report_id
            WHERE v.id=%s AND r.user_id=%s
            FOR UPDATE
            """,
            (version_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return "not_found"
        if str(row.get("status") or "") != "proposed":
            return "conflict"
        current_version = int(row.get("report_version") or 0)
        base_version = int(row.get("base_report_version") or 0)
        if decision == "accept" and current_version != base_version:
            return "stale"
        status = "accepted" if decision == "accept" else "rejected"
        if decision == "accept":
            if report_obj is None:
                return "conflict"
            cur.execute(
                """
                UPDATE career_reports
                SET report_json=%s, report_version=report_version + 1
                WHERE id=%s AND user_id=%s AND report_version=%s
                """,
                (json_dumps(report_obj), int(row["report_id"]), user_id, base_version),
            )
            if cur.rowcount != 1:
                return "stale"
        cur.execute(
            """
            UPDATE career_report_plan_versions
            SET status=%s, decision_json=%s, decided_at=CURRENT_TIMESTAMP
            WHERE id=%s
            """,
            (status, json_dumps({"accepted_change_ids": accepted_change_ids}), version_id),
        )
        cur.execute(
            """
            INSERT INTO career_report_action_events (
              report_id, review_id, plan_version_id, event_type, payload_json
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                int(row["report_id"]),
                row.get("review_id"),
                version_id,
                f"plan_proposal_{status}",
                json_dumps({"accepted_change_ids": accepted_change_ids}),
            ),
        )
        return status


def _merge_user_action_state(
    previous_plan: Dict[str, Any],
    enriched_plan: Dict[str, Any],
    *,
    job_id: str,
    tombstones: List[Any],
) -> Dict[str, Any]:
    """Keep user intent while allowing newly enriched plan content to become visible."""
    from app.domains.report.plan_action_progress import build_stable_action_ref

    previous_nmp = previous_plan.get("next_month_plan") if isinstance(previous_plan.get("next_month_plan"), dict) else {}
    enriched_nmp = enriched_plan.get("next_month_plan") if isinstance(enriched_plan.get("next_month_plan"), dict) else {}
    if not enriched_nmp:
        return previous_nmp
    previous_items = previous_nmp.get("items") if isinstance(previous_nmp.get("items"), list) else []
    enriched_items = enriched_nmp.get("items") if isinstance(enriched_nmp.get("items"), list) else []

    deleted_uids = {str(value) for value in tombstones if isinstance(value, str)}
    deleted_slots = set()
    for value in tombstones:
        if not isinstance(value, dict) or str(value.get("job_id") or "") != job_id:
            continue
        deleted_uids.add(str(value.get("action_uid") or ""))
        deleted_slots.add((int(value.get("item_index") or 0), int(value.get("action_index") or 0), str(value.get("kind") or "")))

    for item_index, item in enumerate(enriched_items):
        if not isinstance(item, dict):
            continue
        dimension = str(item.get("focus_dimension") or "")
        previous_item = next(
            (candidate for candidate in previous_items if isinstance(candidate, dict) and dimension and str(candidate.get("focus_dimension") or "") == dimension),
            previous_items[item_index] if item_index < len(previous_items) and isinstance(previous_items[item_index], dict) else {},
        )
        old_actions = [value for value in previous_item.get("custom_actions") or [] if isinstance(value, dict)]
        new_actions = [value for value in item.get("custom_actions") or [] if isinstance(value, dict)]
        used_old: set[int] = set()
        merged_actions: List[Dict[str, Any]] = []
        for action_index, action in enumerate(new_actions):
            kind = str(action.get("kind") or "practice")
            old_index = next(
                (idx for idx, old in enumerate(old_actions) if idx not in used_old and str(old.get("kind") or "practice") == kind),
                action_index if action_index < len(old_actions) and action_index not in used_old else -1,
            )
            old = old_actions[old_index] if old_index >= 0 else {}
            if old_index >= 0:
                used_old.add(old_index)
            action_uid = str(old.get("action_uid") or action.get("action_uid") or build_stable_action_ref(job_id, action))
            action["action_uid"] = action_uid
            for field in old.get("user_edited_fields") or []:
                if field in old:
                    action[str(field)] = old[field]
            if old.get("done"):
                action["done"] = True
                if old.get("done_at"):
                    action["done_at"] = old["done_at"]
            elif "done" in old:
                action["done"] = False
                action.pop("done_at", None)
            slot = (item_index, action_index, kind)
            if action_uid not in deleted_uids and slot not in deleted_slots:
                merged_actions.append(action)
        for old_index, old in enumerate(old_actions):
            if old_index in used_old or not old.get("user_created"):
                continue
            action_uid = str(old.get("action_uid") or build_stable_action_ref(job_id, old))
            if action_uid not in deleted_uids:
                old["action_uid"] = action_uid
                merged_actions.append(old)
        item["custom_actions"] = merged_actions
    enriched_nmp["items"] = enriched_items
    return enriched_nmp


def merge_report_enrichment(
    report_id: int,
    enriched: Dict[str, Any],
    *,
    expected_attempt: int | None = None,
    refresh_scope: str = "full",
) -> Dict[str, Any] | None:
    """Merge AI-owned fields without overwriting reviews or user action state."""
    with db_cursor() as (_, cur):
        cur.execute("SELECT attempt FROM career_report_enrichment_jobs WHERE report_id=%s", (report_id,))
        job_row = cur.fetchone() or {}
        cur.execute("SELECT report_json, primary_job_id FROM career_reports WHERE id=%s FOR UPDATE", (report_id,))
        row = cur.fetchone()
        if not row:
            return None
        if expected_attempt is not None and int(job_row.get("attempt") or 0) != int(expected_attempt):
            return None
        latest = _parse_json_field(row.get("report_json"), {})
        if not isinstance(latest, dict):
            latest = {}

        latest_plans = {
            str(plan.get("job_id") or ""): plan
            for plan in latest.get("plans_by_target") or []
            if isinstance(plan, dict) and plan.get("job_id")
        }
        enriched_plans = []
        for plan in enriched.get("plans_by_target") or []:
            if not isinstance(plan, dict):
                continue
            merged_plan = dict(plan)
            previous = latest_plans.get(str(plan.get("job_id") or "")) or {}
            if previous.get("current_plan_month") is not None:
                merged_plan["current_plan_month"] = previous["current_plan_month"]
            merged_plan["next_month_plan"] = _merge_user_action_state(
                previous,
                merged_plan,
                job_id=str(plan.get("job_id") or ""),
                tombstones=latest.get("user_action_tombstones") or [],
            )
            enriched_plans.append(merged_plan)

        owned_by_scope = {
            "full": {"recommendations", "growth_plan", "narrative"},
            "resources": {"recommendations", "growth_plan"},
            "plan": {"growth_plan"},
            "narrative": {"narrative"},
        }
        always_owned = {
            "enrichment", "enrichment_quality", "enrichment_evidence",
            "input_snapshot", "generation_timing_ms",
        }
        for key in owned_by_scope.get(refresh_scope, owned_by_scope["full"]) | always_owned:
            if key in enriched:
                latest[key] = enriched[key]
        if refresh_scope in ("full", "resources", "plan", "narrative"):
            latest["plans_by_target"] = enriched_plans
        latest["llm_enrich_pending"] = False
        # Rebuild the system-owned decision view after preserving the newest
        # user action state from ``latest_plans``.
        from app.domains.report.decision_support import attach_decision_support

        attach_decision_support(latest, primary_job_id=str(row.get("primary_job_id") or ""))
        cur.execute(
            "UPDATE career_reports SET report_json=%s, report_version=report_version + 1 WHERE id=%s",
            (json_dumps(latest), report_id),
        )
        return latest
