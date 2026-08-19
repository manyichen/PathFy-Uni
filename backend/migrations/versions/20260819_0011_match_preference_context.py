"""freeze personality preference context in match snapshots

Revision ID: 20260819_0011
Revises: 20260819_0010
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260819_0011"
down_revision = "20260819_0010"
branch_labels = None
depends_on = None


def _scalar(sql: str, **params):
    return op.get_bind().execute(text(sql), params).scalar()


def _has_column(table: str, column: str) -> bool:
    return bool(
        _scalar(
            """SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND COLUMN_NAME=:column""",
            table=table,
            column=column,
        )
    )


def _has_index(table: str, index: str) -> bool:
    return bool(
        _scalar(
            """SELECT COUNT(*) FROM information_schema.STATISTICS
               WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND INDEX_NAME=:index""",
            table=table,
            index=index,
        )
    )


def _has_constraint(table: str, constraint: str) -> bool:
    return bool(
        _scalar(
            """SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
               WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=:table
                 AND CONSTRAINT_NAME=:constraint""",
            table=table,
            constraint=constraint,
        )
    )


def _add_column(column: str, definition: str) -> None:
    if not _has_column("match_runs", column):
        op.execute(f"ALTER TABLE match_runs ADD COLUMN `{column}` {definition}")


def upgrade() -> None:
    _add_column("personality_profile_id", "INT NULL")
    _add_column("preference_mode", "VARCHAR(24) NOT NULL DEFAULT 'off'")
    _add_column("preference_snapshot_json", "LONGTEXT NULL")
    _add_column("preference_algorithm_version", "VARCHAR(64) NULL")
    _add_column("workstyle_snapshot_version", "VARCHAR(64) NULL")
    if not _has_index("match_runs", "idx_match_runs_personality_profile"):
        op.execute(
            "CREATE INDEX idx_match_runs_personality_profile "
            "ON match_runs (personality_profile_id)"
        )
    if not _has_constraint("match_runs", "fk_match_runs_personality_profile"):
        op.execute(
            "ALTER TABLE match_runs ADD CONSTRAINT fk_match_runs_personality_profile "
            "FOREIGN KEY (personality_profile_id) REFERENCES personality_profiles(id) "
            "ON DELETE SET NULL"
        )


def downgrade() -> None:
    if _has_constraint("match_runs", "fk_match_runs_personality_profile"):
        op.execute(
            "ALTER TABLE match_runs DROP FOREIGN KEY fk_match_runs_personality_profile"
        )
    if _has_index("match_runs", "idx_match_runs_personality_profile"):
        op.execute("DROP INDEX idx_match_runs_personality_profile ON match_runs")
    for column in (
        "workstyle_snapshot_version",
        "preference_algorithm_version",
        "preference_snapshot_json",
        "preference_mode",
        "personality_profile_id",
    ):
        if _has_column("match_runs", column):
            op.execute(f"ALTER TABLE match_runs DROP COLUMN `{column}`")
