"""career report longitudinal personalization and experiment assignment

Revision ID: 20260819_0008
Revises: 20260819_0007
"""

from alembic import op

revision = "20260819_0008"
down_revision = "20260819_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE student_resume "
        "ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP AFTER create_time"
    )
    op.execute(
        """
        CREATE TABLE career_report_experiment_assignments (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          report_id BIGINT UNSIGNED NOT NULL,
          experiment_key VARCHAR(64) NOT NULL,
          variant VARCHAR(32) NOT NULL,
          bucket SMALLINT UNSIGNED NOT NULL,
          assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          UNIQUE KEY uk_report_experiment (report_id, experiment_key),
          KEY idx_experiment_variant (experiment_key, variant, assigned_at),
          CONSTRAINT fk_experiment_assignment_report
            FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE career_report_experiment_assignments")
    op.execute("ALTER TABLE student_resume DROP COLUMN updated_at")
