#!/usr/bin/env python3
"""Check runtime database shape for the current backend.

The script is read-only. It is meant to be run before/after Alembic upgrades
when old local databases may be missing columns that the current code expects.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app import create_app
from app.db import db_cursor
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings


def _expected_alembic_head() -> str:
    """Read the migration head from Alembic instead of duplicating it here."""
    config = AlembicConfig(str(_BACKEND_ROOT / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if not head:
        raise RuntimeError("Alembic migration head is missing")
    return str(head)


EXPECTED_ALEMBIC_HEAD = _expected_alembic_head()

REQUIRED_TABLE_COLUMNS: dict[str, set[str]] = {
    "users": {"id", "username", "is_admin"},
    "student_resume": {"id", "user_id", "cap_conf_theory", "detailed_analysis", "updated_at"},
    "match_runs": {
        "id",
        "user_id",
        "resume_id",
        "settings_revision",
        "config_snapshot_json",
        "personality_profile_id",
        "preference_mode",
        "preference_snapshot_json",
        "preference_algorithm_version",
        "workstyle_snapshot_version",
        "preference_experiment_variant",
        "preference_ranking_diff_json",
    },
    "match_run_items": {"id", "run_id", "job_id", "rank_index", "job_json"},
    "career_reports": {
        "id",
        "user_id",
        "resume_id",
        "report_json",
        "report_version",
        "settings_revision",
        "config_snapshot_json",
        "personality_profile_id",
    },
    "behavioral_preference_evidence": {
        "id",
        "user_id",
        "report_id",
        "review_id",
        "axis_code",
        "observed_value",
        "source_type",
        "source_json",
        "user_confirmed",
        "created_at",
    },
    "career_report_targets": {"id", "report_id", "job_id", "target_order", "title"},
    "career_report_reviews": {"id", "report_id", "scope", "job_id", "metrics_json"},
    "career_report_review_drafts": {"id", "report_id", "review_cycle", "candidates_json", "status"},
    "career_report_plan_versions": {"id", "report_id", "base_report_version", "status", "diff_json"},
    "career_report_evidence_records": {"id", "report_id", "review_id", "evidence_type"},
    "career_report_action_events": {"id", "report_id", "event_type", "payload_json"},
    "career_report_experiment_assignments": {"id", "report_id", "experiment_key", "variant", "bucket"},
    "graph_update_tasks": {
        "id",
        "task_uuid",
        "task_type",
        "status",
        "settings_revision",
        "config_snapshot_json",
    },
    "graph_update_task_events": {"id", "task_id", "event_type", "message"},
    "graph_update_task_files": {"id", "task_id", "role", "original_name"},
    "graph_write_guard": {"id", "graph_revision", "locked_task_id"},
    "system_setting_revisions": {"id", "revision", "settings_json", "created_at"},
    "system_setting_state": {"id", "current_revision_id", "updated_at"},
    "user_preferences": {"user_id", "version", "preferences_json"},
    "personality_profiles": {
        "id",
        "user_id",
        "dimension_scores_json",
        "question_set_version",
        "scoring_version",
        "result_status",
        "is_active",
        "personalization_enabled",
        "completed_at",
        "answer_signature",
    },
    "personality_test_answers": {
        "id",
        "user_id",
        "question_id",
        "personality_profile_id",
        "question_set_version",
    },
}

REQUIRED_DELETE_RULES: dict[tuple[str, str], str] = {
    ("career_report_targets", "fk_career_report_targets_report_id"): "CASCADE",
    ("career_report_reviews", "fk_career_report_reviews_report_id"): "CASCADE",
    ("career_report_review_drafts", "fk_review_drafts_report"): "CASCADE",
    ("career_report_plan_versions", "fk_plan_versions_report"): "CASCADE",
    ("career_report_evidence_records", "fk_evidence_records_report"): "CASCADE",
    ("career_report_action_events", "fk_action_events_report"): "CASCADE",
    ("career_report_experiment_assignments", "fk_experiment_assignment_report"): "CASCADE",
    ("personality_profiles", "fk_personality_profiles_superseded"): "SET NULL",
    ("personality_test_answers", "fk_personality_answers_profile"): "CASCADE",
    ("match_runs", "fk_match_runs_personality_profile"): "SET NULL",
    ("career_reports", "fk_career_reports_personality_profile"): "SET NULL",
    ("behavioral_preference_evidence", "fk_behavioral_preference_user"): "CASCADE",
    ("behavioral_preference_evidence", "fk_behavioral_preference_report"): "CASCADE",
    ("behavioral_preference_evidence", "fk_behavioral_preference_review"): "SET NULL",
}

REQUIRED_INDEXES: set[tuple[str, str]] = {
    ("career_report_reviews", "idx_career_report_reviews_scope"),
    ("career_report_review_drafts", "idx_review_drafts_report_status"),
    ("career_report_plan_versions", "idx_plan_versions_report_status"),
    ("career_report_action_events", "idx_action_events_report_created"),
    ("career_report_experiment_assignments", "uk_report_experiment"),
    ("career_report_experiment_assignments", "idx_experiment_variant"),
    ("personality_profiles", "idx_personality_profiles_user_active"),
    ("personality_test_answers", "idx_personality_answers_profile"),
    ("match_runs", "idx_match_runs_personality_profile"),
    ("career_reports", "idx_career_reports_personality_profile"),
    ("behavioral_preference_evidence", "idx_behavioral_preference_user_axis"),
    ("behavioral_preference_evidence", "idx_behavioral_preference_report_review"),
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def load_mysql_state() -> tuple[
    dict[str, set[str]],
    list[str],
    str,
    dict[tuple[str, str], str],
    set[tuple[str, str]],
]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT DATABASE() AS database_name")
        db_name = str((cur.fetchone() or {}).get("database_name") or "")
        cur.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """
        )
        columns: dict[str, set[str]] = {}
        for row in cur.fetchall() or []:
            columns.setdefault(str(row["TABLE_NAME"]), set()).add(str(row["COLUMN_NAME"]))

        versions: list[str] = []
        if "alembic_version" in columns:
            cur.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
            versions = [str(row["version_num"]) for row in cur.fetchall() or []]

        cur.execute(
            """
            SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE
            FROM information_schema.REFERENTIAL_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
            """
        )
        delete_rules = {
            (str(row["TABLE_NAME"]), str(row["CONSTRAINT_NAME"])): str(row["DELETE_RULE"]).upper()
            for row in cur.fetchall() or []
        }
        cur.execute(
            """
            SELECT DISTINCT TABLE_NAME, INDEX_NAME
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
            """
        )
        indexes = {
            (str(row["TABLE_NAME"]), str(row["INDEX_NAME"]))
            for row in cur.fetchall() or []
        }

    return columns, versions, db_name, delete_rules, indexes


def evaluate_schema(columns: dict[str, set[str]], alembic_versions: list[str]) -> list[CheckResult]:
    results: list[CheckResult] = []

    for table, required_columns in sorted(REQUIRED_TABLE_COLUMNS.items()):
        if table not in columns:
            results.append(CheckResult(table, "FAIL", "table is missing"))
            continue
        missing = sorted(required_columns - columns[table])
        if missing:
            results.append(CheckResult(table, "FAIL", f"missing columns: {', '.join(missing)}"))
        else:
            results.append(CheckResult(table, "OK", f"{len(required_columns)} required columns found"))

    if not alembic_versions:
        results.append(CheckResult("alembic_version", "FAIL", "table missing or no revision stamped"))
    elif EXPECTED_ALEMBIC_HEAD not in alembic_versions:
        found = ", ".join(alembic_versions)
        results.append(
            CheckResult(
                "alembic_version",
                "WARN",
                f"expected {EXPECTED_ALEMBIC_HEAD}, found {found}",
            )
        )
    else:
        results.append(CheckResult("alembic_version", "OK", EXPECTED_ALEMBIC_HEAD))

    return results


def evaluate_runtime_guards(
    delete_rules: dict[tuple[str, str], str],
    indexes: set[tuple[str, str]],
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for key, expected_rule in sorted(REQUIRED_DELETE_RULES.items()):
        table, constraint = key
        actual_rule = delete_rules.get(key)
        if actual_rule != expected_rule:
            results.append(CheckResult(f"{table}.{constraint}", "FAIL", f"expected ON DELETE {expected_rule}, found {actual_rule or 'missing'}"))
        else:
            results.append(CheckResult(f"{table}.{constraint}", "OK", f"ON DELETE {actual_rule}"))
    for table, index in sorted(REQUIRED_INDEXES):
        if (table, index) not in indexes:
            results.append(CheckResult(f"{table}.{index}", "FAIL", "index is missing"))
        else:
            results.append(CheckResult(f"{table}.{index}", "OK", "index found"))
    return results


def check_neo4j() -> CheckResult:
    uri, user, password, database = neo4j_settings()
    if not password:
        return CheckResult("neo4j", "WARN", "password is empty; graph check skipped")
    try:
        driver = neo4j_driver(uri, user, password)
        with driver.session(database=database) as session:
            count = session.run("MATCH (j:Job) RETURN count(j) AS count").single()["count"]
    except Exception as exc:  # noqa: BLE001
        return CheckResult("neo4j", "WARN", f"connection/query failed: {exc}")
    if int(count or 0) <= 0:
        return CheckResult("neo4j", "FAIL", "Job nodes are empty")
    return CheckResult("neo4j", "OK", f"{count} Job nodes found")


def print_results(db_name: str, results: list[CheckResult]) -> None:
    print(f"Runtime schema check for MySQL database: {db_name or '<unknown>'}")
    for result in results:
        print(f"[{result.status}] {result.name}: {result.detail}")


def main() -> int:
    app = create_app()
    with app.app_context():
        try:
            columns, versions, db_name, delete_rules, indexes = load_mysql_state()
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] mysql: {exc}", file=sys.stderr)
            return 1
        results = evaluate_schema(columns, versions)
        results.extend(evaluate_runtime_guards(delete_rules, indexes))
        results.append(check_neo4j())

    print_results(db_name, results)
    return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
