"""personality report calibration and controlled preference ranking

Revision ID: 20260819_0012
Revises: 20260819_0011
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260819_0012"
down_revision = "20260819_0011"
branch_labels = None
depends_on = None


def _scalar(sql: str, **params):
    return op.get_bind().execute(text(sql), params).scalar()


def _has_column(table: str, column: str) -> bool:
    return bool(_scalar("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND COLUMN_NAME=:column", table=table, column=column))


def _has_index(table: str, index: str) -> bool:
    return bool(_scalar("SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND INDEX_NAME=:index", table=table, index=index))


def _has_constraint(table: str, constraint: str) -> bool:
    return bool(_scalar("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=:table AND CONSTRAINT_NAME=:constraint", table=table, constraint=constraint))


def upgrade() -> None:
    if not _has_column("career_reports", "personality_profile_id"):
        op.execute("ALTER TABLE career_reports ADD COLUMN personality_profile_id INT NULL AFTER resume_id")
    if not _has_index("career_reports", "idx_career_reports_personality_profile"):
        op.execute("CREATE INDEX idx_career_reports_personality_profile ON career_reports (personality_profile_id)")
    if not _has_constraint("career_reports", "fk_career_reports_personality_profile"):
        op.execute("ALTER TABLE career_reports ADD CONSTRAINT fk_career_reports_personality_profile FOREIGN KEY (personality_profile_id) REFERENCES personality_profiles(id) ON DELETE SET NULL")
    for column, definition in (
        ("preference_experiment_variant", "VARCHAR(32) NULL"),
        ("preference_ranking_diff_json", "JSON NULL"),
    ):
        if not _has_column("match_runs", column):
            op.execute(f"ALTER TABLE match_runs ADD COLUMN `{column}` {definition}")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS behavioral_preference_evidence (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          user_id BIGINT UNSIGNED NOT NULL,
          report_id BIGINT UNSIGNED NULL,
          review_id BIGINT UNSIGNED NULL,
          axis_code VARCHAR(32) NOT NULL,
          observed_value DECIMAL(6,2) NULL,
          source_type VARCHAR(32) NOT NULL,
          source_json JSON NULL,
          user_confirmed TINYINT(1) NOT NULL DEFAULT 0,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          KEY idx_behavioral_preference_user_axis (user_id, axis_code, created_at),
          KEY idx_behavioral_preference_report_review (report_id, review_id),
          CONSTRAINT fk_behavioral_preference_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
          CONSTRAINT fk_behavioral_preference_report FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE,
          CONSTRAINT fk_behavioral_preference_review FOREIGN KEY (review_id) REFERENCES career_report_reviews(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS behavioral_preference_evidence")
    for column in ("preference_ranking_diff_json", "preference_experiment_variant"):
        if _has_column("match_runs", column):
            op.execute(f"ALTER TABLE match_runs DROP COLUMN `{column}`")
    if _has_constraint("career_reports", "fk_career_reports_personality_profile"):
        op.execute("ALTER TABLE career_reports DROP FOREIGN KEY fk_career_reports_personality_profile")
    if _has_index("career_reports", "idx_career_reports_personality_profile"):
        op.execute("DROP INDEX idx_career_reports_personality_profile ON career_reports")
    if _has_column("career_reports", "personality_profile_id"):
        op.execute("ALTER TABLE career_reports DROP COLUMN personality_profile_id")
