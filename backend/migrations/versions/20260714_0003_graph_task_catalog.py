"""Expand graph task catalog and support zero or multiple private inputs."""

from alembic import op

revision = "20260714_0003"
down_revision = "20260713_0002"
branch_labels = None
depends_on = None


TASK_TYPES = (
    "'job_import','job_capability_evaluation','job_capability_result_import',"
    "'learning_resource_import','competition_import','job_promotion_import',"
    "'job_lateral_import','promotion_recommendation_import','salary_normalization',"
    "'inferred_job_cleanup','emergency_clear'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE graph_update_tasks DROP CHECK chk_graph_update_tasks_type")
    op.execute("ALTER TABLE graph_update_tasks MODIFY input_file_name VARCHAR(255) NULL")
    op.execute("ALTER TABLE graph_update_tasks MODIFY input_file_size BIGINT UNSIGNED NULL")
    op.execute("ALTER TABLE graph_update_tasks MODIFY input_sha256 CHAR(64) NULL")
    op.execute(
        "ALTER TABLE graph_update_tasks ADD CONSTRAINT chk_graph_update_tasks_type "
        f"CHECK (task_type IN ({TASK_TYPES}))"
    )
    op.execute("""
    CREATE TABLE graph_update_task_files (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      task_id BIGINT UNSIGNED NOT NULL,
      role VARCHAR(40) NOT NULL,
      original_name VARCHAR(255) NOT NULL,
      private_path VARCHAR(1024) NULL,
      size BIGINT UNSIGNED NOT NULL,
      sha256 CHAR(64) NOT NULL,
      media_type VARCHAR(120) NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_graph_update_task_files_role (task_id, role),
      CONSTRAINT fk_graph_update_task_files_task FOREIGN KEY (task_id)
        REFERENCES graph_update_tasks(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
    INSERT INTO graph_update_task_files
      (task_id,role,original_name,private_path,size,sha256,media_type)
    SELECT id,'file',input_file_name,input_file_path,COALESCE(input_file_size,0),
           input_sha256,NULL
    FROM graph_update_tasks
    WHERE input_file_name IS NOT NULL AND input_file_name <> '-'
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_update_task_files")
    op.execute("ALTER TABLE graph_update_tasks DROP CHECK chk_graph_update_tasks_type")
    op.execute("UPDATE graph_update_tasks SET input_file_name='-',input_file_size=0,input_sha256=REPEAT('0',64) WHERE input_file_name IS NULL")
    op.execute("ALTER TABLE graph_update_tasks MODIFY input_file_name VARCHAR(255) NOT NULL")
    op.execute("ALTER TABLE graph_update_tasks MODIFY input_file_size BIGINT UNSIGNED NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE graph_update_tasks MODIFY input_sha256 CHAR(64) NOT NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD CONSTRAINT chk_graph_update_tasks_type CHECK (task_type IN ('job_import','learning_resource_import','competition_import','emergency_clear'))")
