"""career review drafts, plan proposals and audit history

Revision ID: 20260819_0007
Revises: 20260819_0006
"""

from alembic import op

revision = "20260819_0007"
down_revision = "20260819_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE career_report_review_drafts (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          report_id BIGINT UNSIGNED NOT NULL,
          review_cycle VARCHAR(16) NOT NULL DEFAULT 'monthly',
          scope VARCHAR(16) NOT NULL DEFAULT 'target',
          job_id VARCHAR(191) NULL,
          review_text LONGTEXT NOT NULL,
          candidates_json JSON NOT NULL,
          extraction_json JSON NULL,
          status VARCHAR(16) NOT NULL DEFAULT 'draft',
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          confirmed_at DATETIME NULL,
          PRIMARY KEY (id),
          KEY idx_review_drafts_report_status (report_id, status, created_at),
          CONSTRAINT fk_review_drafts_report
            FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.execute(
        """
        CREATE TABLE career_report_plan_versions (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          report_id BIGINT UNSIGNED NOT NULL,
          review_id BIGINT UNSIGNED NULL,
          base_report_version INT UNSIGNED NOT NULL,
          status VARCHAR(16) NOT NULL DEFAULT 'proposed',
          scope VARCHAR(16) NOT NULL DEFAULT 'target',
          job_id VARCHAR(191) NULL,
          snapshot_json LONGTEXT NOT NULL,
          diff_json JSON NOT NULL,
          decision_json JSON NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          decided_at DATETIME NULL,
          PRIMARY KEY (id),
          KEY idx_plan_versions_report_status (report_id, status, created_at),
          CONSTRAINT fk_plan_versions_report
            FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE,
          CONSTRAINT fk_plan_versions_review
            FOREIGN KEY (review_id) REFERENCES career_report_reviews(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.execute(
        """
        CREATE TABLE career_report_evidence_records (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          report_id BIGINT UNSIGNED NOT NULL,
          review_id BIGINT UNSIGNED NULL,
          evidence_type VARCHAR(32) NOT NULL DEFAULT 'other',
          label VARCHAR(191) NOT NULL,
          value_text TEXT NULL,
          source_url TEXT NULL,
          source_text TEXT NULL,
          verification_status VARCHAR(16) NOT NULL DEFAULT 'user_confirmed',
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          KEY idx_evidence_records_report_review (report_id, review_id),
          CONSTRAINT fk_evidence_records_report
            FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE,
          CONSTRAINT fk_evidence_records_review
            FOREIGN KEY (review_id) REFERENCES career_report_reviews(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.execute(
        """
        CREATE TABLE career_report_action_events (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          report_id BIGINT UNSIGNED NOT NULL,
          review_id BIGINT UNSIGNED NULL,
          plan_version_id BIGINT UNSIGNED NULL,
          event_type VARCHAR(32) NOT NULL,
          action_ref VARCHAR(191) NULL,
          payload_json JSON NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (id),
          KEY idx_action_events_report_created (report_id, created_at),
          CONSTRAINT fk_action_events_report
            FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE,
          CONSTRAINT fk_action_events_review
            FOREIGN KEY (review_id) REFERENCES career_report_reviews(id) ON DELETE SET NULL,
          CONSTRAINT fk_action_events_plan_version
            FOREIGN KEY (plan_version_id) REFERENCES career_report_plan_versions(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE career_report_action_events")
    op.execute("DROP TABLE career_report_evidence_records")
    op.execute("DROP TABLE career_report_plan_versions")
    op.execute("DROP TABLE career_report_review_drafts")
