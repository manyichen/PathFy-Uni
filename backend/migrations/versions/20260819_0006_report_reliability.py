"""career report reliability and scoped reviews

Revision ID: 20260819_0006
Revises: 20260715_0005
"""

from alembic import op

revision = "20260819_0006"
down_revision = "20260715_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE career_reports "
        "ADD COLUMN report_version INT UNSIGNED NOT NULL DEFAULT 1 AFTER report_json"
    )
    op.execute(
        "ALTER TABLE career_report_reviews "
        "ADD COLUMN scope VARCHAR(16) NOT NULL DEFAULT 'all' AFTER review_cycle, "
        "ADD COLUMN job_id VARCHAR(191) NULL AFTER scope, "
        "ADD KEY idx_career_report_reviews_scope (report_id, scope, job_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE career_report_reviews DROP KEY idx_career_report_reviews_scope")
    op.execute("ALTER TABLE career_report_reviews DROP COLUMN job_id, DROP COLUMN scope")
    op.execute("ALTER TABLE career_reports DROP COLUMN report_version")
