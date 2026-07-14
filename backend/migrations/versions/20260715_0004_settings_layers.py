"""layered system settings, user preferences, and execution snapshots

Revision ID: 20260715_0004
Revises: 20260714_0003
"""

from alembic import op

revision = "20260715_0004"
down_revision = "20260714_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE system_setting_revisions (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      revision INT UNSIGNED NOT NULL,
      settings_json JSON NOT NULL,
      created_by BIGINT UNSIGNED NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_system_setting_revisions_revision (revision),
      CONSTRAINT fk_system_setting_revisions_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
    CREATE TABLE system_setting_state (
      id TINYINT UNSIGNED NOT NULL,
      current_revision_id BIGINT UNSIGNED NULL,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      CONSTRAINT chk_system_setting_state_singleton CHECK (id = 1),
      CONSTRAINT fk_system_setting_state_revision FOREIGN KEY (current_revision_id) REFERENCES system_setting_revisions(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("INSERT INTO system_setting_state (id,current_revision_id) VALUES (1,NULL)")
    op.execute("""
    CREATE TABLE user_preferences (
      user_id BIGINT UNSIGNED NOT NULL,
      version INT UNSIGNED NOT NULL DEFAULT 1,
      preferences_json JSON NOT NULL,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (user_id),
      CONSTRAINT fk_user_preferences_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    for table in ("graph_update_tasks", "match_runs", "career_reports"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN settings_revision INT UNSIGNED NULL")
        op.execute(f"ALTER TABLE {table} ADD COLUMN config_snapshot_json JSON NULL")


def downgrade() -> None:
    for table in ("career_reports", "match_runs", "graph_update_tasks"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN config_snapshot_json")
        op.execute(f"ALTER TABLE {table} DROP COLUMN settings_revision")
    op.execute("DROP TABLE IF EXISTS user_preferences")
    op.execute("DROP TABLE IF EXISTS system_setting_state")
    op.execute("DROP TABLE IF EXISTS system_setting_revisions")
