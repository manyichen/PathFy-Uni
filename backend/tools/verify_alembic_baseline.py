#!/usr/bin/env python3
"""Verify the pre-Alembic schema before stamping the baseline revision."""

from __future__ import annotations

import sys
from pathlib import Path

import pymysql

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import Config

EXPECTED_COLUMNS = {
    "users": {"id", "is_admin"},
    "student_resume": {
        "id",
        "cap_conf_theory",
        "cap_conf_growth",
        "detailed_analysis",
    },
    "career_reports": {"id", "user_id", "report_json"},
    "career_report_targets": {"id", "report_id", "job_id"},
    "career_report_reviews": {"id", "report_id", "metrics_json"},
    "match_runs": {"id", "user_id", "resume_id"},
    "match_run_items": {"id", "run_id", "job_id"},
    "job_titles": {"id", "title", "record_count"},
}


def load_columns() -> dict[str, set[str]]:
    connection = pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        charset="utf8mb4",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT TABLE_NAME, COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                """,
                (Config.MYSQL_DATABASE,),
            )
            found: dict[str, set[str]] = {}
            for table, column in cursor.fetchall():
                found.setdefault(str(table), set()).add(str(column))
            return found
    finally:
        connection.close()


def main() -> int:
    found = load_columns()
    problems = []
    for table, required in EXPECTED_COLUMNS.items():
        missing = sorted(required - found.get(table, set()))
        if missing:
            problems.append(f"{table}: missing {', '.join(missing)}")
    if problems:
        print("Alembic baseline verification failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("Alembic baseline verified; safe to stamp 20260712_0001.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
