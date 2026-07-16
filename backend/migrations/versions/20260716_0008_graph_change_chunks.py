"""Store reviewed graph changes in independently verifiable chunks."""

from alembic import op

revision = "20260716_0008"
down_revision = "20260715_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN change_manifest_json LONGTEXT NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN change_storage_version TINYINT UNSIGNED NOT NULL DEFAULT 1")
    op.execute(
        """
        CREATE TABLE graph_update_task_change_chunks (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          task_id BIGINT UNSIGNED NOT NULL,
          group_name VARCHAR(96) NOT NULL,
          chunk_no INT UNSIGNED NOT NULL,
          item_count INT UNSIGNED NOT NULL,
          chunk_sha256 CHAR(64) NOT NULL,
          payload_json LONGTEXT NOT NULL,
          created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          PRIMARY KEY (id),
          UNIQUE KEY uq_graph_task_change_chunk (task_id,group_name,chunk_no),
          KEY ix_graph_task_change_group (task_id,group_name,chunk_no),
          CONSTRAINT fk_graph_task_change_chunk_task FOREIGN KEY (task_id)
            REFERENCES graph_update_tasks(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_update_task_change_chunks")
    op.execute("ALTER TABLE graph_update_tasks DROP COLUMN change_storage_version")
    op.execute("ALTER TABLE graph_update_tasks DROP COLUMN change_manifest_json")
