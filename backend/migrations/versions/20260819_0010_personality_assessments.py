"""version and group personality assessments

Revision ID: 20260819_0010
Revises: 20260819_0009
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260819_0010"
down_revision = "20260819_0009"
branch_labels = None
depends_on = None


def _scalar(sql: str, **params):
    return op.get_bind().execute(text(sql), params).scalar()


def _has_column(table: str, column: str) -> bool:
    return bool(
        _scalar(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND COLUMN_NAME=:column
            """,
            table=table,
            column=column,
        )
    )


def _has_index(table: str, index: str) -> bool:
    return bool(
        _scalar(
            """
            SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND INDEX_NAME=:index
            """,
            table=table,
            index=index,
        )
    )


def _has_constraint(table: str, constraint: str) -> bool:
    return bool(
        _scalar(
            """
            SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=:table
              AND CONSTRAINT_NAME=:constraint
            """,
            table=table,
            constraint=constraint,
        )
    )


def _add_column(table: str, column: str, definition: str) -> None:
    if not _has_column(table, column):
        op.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


def upgrade() -> None:
    _add_column("personality_profiles", "detailed_analysis", "LONGTEXT NULL")
    _add_column("personality_profiles", "dimension_scores_json", "JSON NULL")
    _add_column(
        "personality_profiles",
        "question_set_version",
        "VARCHAR(64) NOT NULL DEFAULT 'legacy-v1'",
    )
    _add_column(
        "personality_profiles",
        "scoring_version",
        "VARCHAR(64) NOT NULL DEFAULT 'mbti-count-v1'",
    )
    _add_column(
        "personality_profiles",
        "result_status",
        "VARCHAR(24) NOT NULL DEFAULT 'legacy_signature'",
    )
    _add_column("personality_profiles", "is_active", "TINYINT(1) NOT NULL DEFAULT 0")
    _add_column(
        "personality_profiles",
        "personalization_enabled",
        "TINYINT(1) NOT NULL DEFAULT 0",
    )
    _add_column("personality_profiles", "completed_at", "DATETIME NULL")
    _add_column("personality_profiles", "superseded_by_profile_id", "INT NULL")
    _add_column("personality_profiles", "answer_signature", "CHAR(64) NULL")

    if not _has_index("personality_profiles", "idx_personality_profiles_user_active"):
        op.execute(
            "CREATE INDEX idx_personality_profiles_user_active "
            "ON personality_profiles (user_id, is_active, completed_at)"
        )
    if not _has_constraint("personality_profiles", "fk_personality_profiles_superseded"):
        op.execute(
            "ALTER TABLE personality_profiles ADD CONSTRAINT fk_personality_profiles_superseded "
            "FOREIGN KEY (superseded_by_profile_id) REFERENCES personality_profiles(id) "
            "ON DELETE SET NULL"
        )

    _add_column("personality_test_answers", "personality_profile_id", "INT NULL")
    _add_column("personality_test_answers", "question_set_version", "VARCHAR(64) NULL")
    if not _has_index("personality_test_answers", "idx_personality_answers_profile"):
        op.execute(
            "CREATE INDEX idx_personality_answers_profile "
            "ON personality_test_answers (personality_profile_id, question_id)"
        )
    if not _has_constraint("personality_test_answers", "fk_personality_answers_profile"):
        op.execute(
            "ALTER TABLE personality_test_answers ADD CONSTRAINT fk_personality_answers_profile "
            "FOREIGN KEY (personality_profile_id) REFERENCES personality_profiles(id) "
            "ON DELETE CASCADE"
        )

    # Recover continuous dimensions only when the historical JSON contains them.
    op.execute(
        """
        UPDATE personality_profiles
        SET dimension_scores_json=JSON_EXTRACT(detailed_analysis, '$.dimension_scores')
        WHERE dimension_scores_json IS NULL
          AND detailed_analysis IS NOT NULL
          AND JSON_VALID(detailed_analysis)
          AND JSON_EXTRACT(detailed_analysis, '$.dimension_scores') IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE personality_profiles
        SET result_status=CASE
              WHEN dimension_scores_json IS NOT NULL THEN 'measured'
              ELSE 'legacy_signature'
            END,
            completed_at=COALESCE(completed_at, created_at),
            is_active=0
        """
    )
    op.execute(
        """
        UPDATE personality_profiles p
        JOIN (
          SELECT user_id, MAX(id) AS latest_id
          FROM personality_profiles
          GROUP BY user_id
        ) latest ON latest.latest_id=p.id
        SET p.is_active=1
        """
    )


def downgrade() -> None:
    if _has_constraint("personality_test_answers", "fk_personality_answers_profile"):
        op.execute(
            "ALTER TABLE personality_test_answers DROP FOREIGN KEY fk_personality_answers_profile"
        )
    if _has_index("personality_test_answers", "idx_personality_answers_profile"):
        op.execute("DROP INDEX idx_personality_answers_profile ON personality_test_answers")
    for column in ("question_set_version", "personality_profile_id"):
        if _has_column("personality_test_answers", column):
            op.execute(f"ALTER TABLE personality_test_answers DROP COLUMN `{column}`")

    if _has_constraint("personality_profiles", "fk_personality_profiles_superseded"):
        op.execute(
            "ALTER TABLE personality_profiles DROP FOREIGN KEY fk_personality_profiles_superseded"
        )
    if _has_index("personality_profiles", "idx_personality_profiles_user_active"):
        op.execute("DROP INDEX idx_personality_profiles_user_active ON personality_profiles")
    for column in (
        "answer_signature",
        "superseded_by_profile_id",
        "completed_at",
        "personalization_enabled",
        "is_active",
        "result_status",
        "scoring_version",
        "question_set_version",
        "dimension_scores_json",
        "detailed_analysis",
    ):
        if _has_column("personality_profiles", column):
            op.execute(f"ALTER TABLE personality_profiles DROP COLUMN `{column}`")
