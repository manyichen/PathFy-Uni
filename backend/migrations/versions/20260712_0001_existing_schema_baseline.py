"""Create the initial schema previously managed by schema.sql and migrations 002-007.

Existing installations must be verified and stamped instead of running this
revision.  Empty databases can run ``alembic upgrade head`` directly.
"""

from pathlib import Path

from alembic import op

revision = "20260712_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    for statement in _schema_statements(schema_sql):
        normalized = statement.lstrip().upper()
        # Alembic connects to MYSQL_DATABASE already. Creating/selecting the
        # legacy hard-coded database here would initialize the wrong schema.
        if normalized.startswith("CREATE DATABASE") or normalized.startswith("USE "):
            continue
        op.execute(statement)


def downgrade() -> None:
    for table_name in (
        "match_run_items",
        "match_runs",
        "career_report_reviews",
        "career_report_targets",
        "career_reports",
        "personality_profiles",
        "personality_test_answers",
        "personality_test_questions",
        "student_resume",
        "job_titles",
        "ai_chat_messages",
        "ai_chat_sessions",
        "users",
    ):
        op.execute(f"DROP TABLE IF EXISTS `{table_name}`")


def _schema_statements(sql: str) -> list[str]:
    """Split the project's plain MySQL schema into executable statements.

    schema.sql contains no stored procedures or semicolons inside string
    literals, so removing full-line comments and splitting on semicolons is
    intentional and keeps the Alembic schema identical to local bootstrap.
    """
    uncommented = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    return [statement.strip() for statement in uncommented.split(";") if statement.strip()]
