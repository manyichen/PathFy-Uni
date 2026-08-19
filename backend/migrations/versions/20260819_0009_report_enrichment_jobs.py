"""isolate career report enrichment job state

Revision ID: 20260819_0009
Revises: 20260819_0008
"""

from alembic import op

revision = "20260819_0009"
down_revision = "20260819_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS career_report_enrichment_jobs (
          report_id BIGINT UNSIGNED NOT NULL,
          attempt INT UNSIGNED NOT NULL DEFAULT 0,
          status VARCHAR(24) NOT NULL DEFAULT 'pending',
          scope VARCHAR(24) NOT NULL DEFAULT 'full',
          stage VARCHAR(64) NOT NULL DEFAULT 'pending',
          progress TINYINT UNSIGNED NOT NULL DEFAULT 0,
          error VARCHAR(500) NULL,
          timing_json JSON NULL,
          quality_json JSON NULL,
          requested_at DATETIME NULL,
          started_at DATETIME NULL,
          completed_at DATETIME NULL,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (report_id),
          KEY idx_report_enrichment_status (status, updated_at),
          CONSTRAINT fk_report_enrichment_report
            FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.execute(
        """
        INSERT IGNORE INTO career_report_enrichment_jobs (
          report_id, attempt, status, scope, stage, progress,
          requested_at, started_at, completed_at
        )
        SELECT id, 0,
          CASE WHEN JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.status')) IN ('pending','queued','running','completed','failed')
            THEN JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.status')) ELSE 'pending' END,
          COALESCE(JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.scope')), 'full'),
          COALESCE(JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.stage')), 'pending'),
          COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.progress')) AS UNSIGNED), 0),
          STR_TO_DATE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.requested_at')), 'null'), '%Y-%m-%d %H:%i:%s'),
          STR_TO_DATE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.started_at')), 'null'), '%Y-%m-%d %H:%i:%s'),
          STR_TO_DATE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.enrichment_job.completed_at')), 'null'), '%Y-%m-%d %H:%i:%s')
        FROM career_reports
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE career_report_enrichment_jobs")
