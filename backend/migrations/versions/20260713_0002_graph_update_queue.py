"""Add durable graph update queue, event history, and write guard."""

from alembic import op

revision = "20260713_0002"
down_revision = "20260712_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE graph_update_tasks (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      task_uuid CHAR(32) NOT NULL,
      task_type VARCHAR(40) NOT NULL,
      status VARCHAR(32) NOT NULL DEFAULT 'queued',
      requested_by BIGINT UNSIGNED NOT NULL,
      handled_by BIGINT UNSIGNED NULL,
      input_file_name VARCHAR(255) NOT NULL,
      input_file_path VARCHAR(1024) NULL,
      input_file_size BIGINT UNSIGNED NOT NULL DEFAULT 0,
      input_sha256 CHAR(64) NOT NULL,
      source_id VARCHAR(120) NULL,
      mode VARCHAR(16) NOT NULL DEFAULT 'merge',
      options_json JSON NOT NULL,
      base_graph_revision BIGINT UNSIGNED NULL,
      change_summary_json JSON NULL,
      change_set_json LONGTEXT NULL,
      change_set_sha256 CHAR(64) NULL,
      error_message TEXT NULL,
      rejection_reason TEXT NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      started_at DATETIME NULL,
      prepared_at DATETIME NULL,
      handled_at DATETIME NULL,
      finished_at DATETIME NULL,
      PRIMARY KEY (id),
      UNIQUE KEY uk_graph_update_tasks_uuid (task_uuid),
      KEY idx_graph_update_tasks_status_created (status, created_at),
      KEY idx_graph_update_tasks_type_created (task_type, created_at),
      CONSTRAINT fk_graph_update_tasks_requested_by FOREIGN KEY (requested_by) REFERENCES users(id),
      CONSTRAINT fk_graph_update_tasks_handled_by FOREIGN KEY (handled_by) REFERENCES users(id),
      CONSTRAINT chk_graph_update_tasks_status CHECK (status IN ('queued','running','awaiting_confirmation','applying','succeeded','partial_failed','failed','rejected','cancelled')),
      CONSTRAINT chk_graph_update_tasks_type CHECK (task_type IN ('job_import','learning_resource_import','competition_import','emergency_clear'))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
    CREATE TABLE graph_update_task_events (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      task_id BIGINT UNSIGNED NOT NULL,
      event_type VARCHAR(40) NOT NULL,
      stage VARCHAR(60) NULL,
      message VARCHAR(500) NOT NULL,
      detail_json JSON NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      KEY idx_graph_update_task_events_task_created (task_id, created_at),
      CONSTRAINT fk_graph_update_task_events_task FOREIGN KEY (task_id)
        REFERENCES graph_update_tasks(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
    CREATE TABLE graph_write_guard (
      id TINYINT UNSIGNED NOT NULL,
      graph_revision BIGINT UNSIGNED NOT NULL DEFAULT 0,
      locked_task_id BIGINT UNSIGNED NULL,
      locked_at DATETIME NULL,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      CONSTRAINT chk_graph_write_guard_singleton CHECK (id = 1),
      CONSTRAINT fk_graph_write_guard_task FOREIGN KEY (locked_task_id)
        REFERENCES graph_update_tasks(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("INSERT INTO graph_write_guard (id, graph_revision) VALUES (1, 0)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_write_guard")
    op.execute("DROP TABLE IF EXISTS graph_update_task_events")
    op.execute("DROP TABLE IF EXISTS graph_update_tasks")
