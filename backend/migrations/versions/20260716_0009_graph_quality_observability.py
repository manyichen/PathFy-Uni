"""Add capability cache, graph worker telemetry, and reviewed inverse tasks."""

from alembic import op

revision = "20260716_0009"
down_revision = "20260716_0008"
branch_labels = None
depends_on = None


TASK_TYPES = (
    "'job_import','job_capability_evaluation','job_capability_result_import',"
    "'learning_resource_import','competition_import','job_promotion_import',"
    "'job_lateral_import','promotion_recommendation_import','salary_normalization',"
    "'inferred_job_cleanup','graph_inverse','emergency_clear'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE graph_update_tasks DROP CHECK chk_graph_update_tasks_type")
    op.execute(
        "ALTER TABLE graph_update_tasks ADD CONSTRAINT chk_graph_update_tasks_type "
        f"CHECK (task_type IN ({TASK_TYPES}))"
    )
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN inverse_manifest_json LONGTEXT NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN inverse_sha256 CHAR(64) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN inverse_of_task_id BIGINT UNSIGNED NULL")
    op.execute("CREATE INDEX ix_graph_tasks_inverse_of ON graph_update_tasks (inverse_of_task_id)")
    op.execute(
        "ALTER TABLE graph_update_tasks ADD CONSTRAINT fk_graph_tasks_inverse_of "
        "FOREIGN KEY (inverse_of_task_id) REFERENCES graph_update_tasks(id) ON DELETE SET NULL"
    )
    op.execute(
        """
        CREATE TABLE graph_update_task_inverse_chunks (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          task_id BIGINT UNSIGNED NOT NULL,
          group_name VARCHAR(96) NOT NULL,
          chunk_no INT UNSIGNED NOT NULL,
          item_count INT UNSIGNED NOT NULL,
          chunk_sha256 CHAR(64) NOT NULL,
          payload_json LONGTEXT NOT NULL,
          created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          PRIMARY KEY (id),
          UNIQUE KEY uq_graph_task_inverse_chunk (task_id,group_name,chunk_no),
          CONSTRAINT fk_graph_task_inverse_chunk_task FOREIGN KEY (task_id)
            REFERENCES graph_update_tasks(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.execute(
        """
        CREATE TABLE graph_capability_evaluation_cache (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          cap_input_fingerprint CHAR(64) NOT NULL,
          cap_version VARCHAR(80) NOT NULL,
          provider VARCHAR(120) NOT NULL,
          model VARCHAR(240) NOT NULL,
          prompt_version VARCHAR(80) NOT NULL,
          result_json JSON NOT NULL,
          metadata_json JSON NULL,
          hit_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
          created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          last_used_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          PRIMARY KEY (id),
          UNIQUE KEY uq_graph_capability_cache
            (cap_input_fingerprint,cap_version,provider,model,prompt_version),
          KEY ix_graph_capability_cache_last_used (last_used_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.execute(
        """
        CREATE TABLE graph_llm_call_metrics (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          task_id BIGINT UNSIGNED NULL,
          stage VARCHAR(80) NOT NULL,
          provider VARCHAR(80) NOT NULL,
          model VARCHAR(160) NOT NULL,
          request_id VARCHAR(160) NULL,
          duration_ms INT UNSIGNED NOT NULL DEFAULT 0,
          prompt_tokens INT UNSIGNED NOT NULL DEFAULT 0,
          completion_tokens INT UNSIGNED NOT NULL DEFAULT 0,
          retry_count INT UNSIGNED NOT NULL DEFAULT 0,
          cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
          error_code VARCHAR(80) NULL,
          created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          PRIMARY KEY (id),
          KEY ix_graph_llm_metrics_task (task_id,created_at),
          KEY ix_graph_llm_metrics_created (created_at),
          CONSTRAINT fk_graph_llm_metrics_task FOREIGN KEY (task_id)
            REFERENCES graph_update_tasks(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.execute(
        """
        CREATE TABLE graph_worker_heartbeats (
          worker_id VARCHAR(128) NOT NULL,
          current_task_id BIGINT UNSIGNED NULL,
          process_started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          last_heartbeat_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          PRIMARY KEY (worker_id),
          KEY ix_graph_worker_heartbeat (last_heartbeat_at),
          CONSTRAINT fk_graph_worker_current_task FOREIGN KEY (current_task_id)
            REFERENCES graph_update_tasks(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_worker_heartbeats")
    op.execute("DROP TABLE IF EXISTS graph_llm_call_metrics")
    op.execute("DROP TABLE IF EXISTS graph_capability_evaluation_cache")
    op.execute("DROP TABLE IF EXISTS graph_update_task_inverse_chunks")
    op.execute("ALTER TABLE graph_update_tasks DROP FOREIGN KEY fk_graph_tasks_inverse_of")
    op.execute("DROP INDEX ix_graph_tasks_inverse_of ON graph_update_tasks")
    op.execute("ALTER TABLE graph_update_tasks DROP COLUMN inverse_of_task_id")
    op.execute("ALTER TABLE graph_update_tasks DROP COLUMN inverse_sha256")
    op.execute("ALTER TABLE graph_update_tasks DROP COLUMN inverse_manifest_json")
    op.execute("ALTER TABLE graph_update_tasks DROP CHECK chk_graph_update_tasks_type")
    old_types = TASK_TYPES.replace(",'graph_inverse'", "")
    op.execute(
        "ALTER TABLE graph_update_tasks ADD CONSTRAINT chk_graph_update_tasks_type "
        f"CHECK (task_type IN ({old_types}))"
    )
