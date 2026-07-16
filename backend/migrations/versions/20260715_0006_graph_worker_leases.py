"""Add durable worker leases and retry metadata to graph tasks."""

from alembic import op

revision = "20260715_0006"
down_revision = "20260715_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN worker_id VARCHAR(128) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN lease_token CHAR(32) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN heartbeat_at DATETIME(6) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN lease_expires_at DATETIME(6) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN attempt_count INT UNSIGNED NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN next_retry_at DATETIME(6) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN last_error_code VARCHAR(80) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN last_error_retryable BOOLEAN NULL")
    op.execute("CREATE INDEX ix_graph_tasks_queue_retry ON graph_update_tasks (status,next_retry_at,created_at)")
    op.execute("CREATE INDEX ix_graph_tasks_lease_expiry ON graph_update_tasks (status,lease_expires_at)")


def downgrade() -> None:
    op.execute("DROP INDEX ix_graph_tasks_lease_expiry ON graph_update_tasks")
    op.execute("DROP INDEX ix_graph_tasks_queue_retry ON graph_update_tasks")
    for column in (
        "last_error_retryable",
        "last_error_code",
        "next_retry_at",
        "attempt_count",
        "lease_expires_at",
        "heartbeat_at",
        "lease_token",
        "worker_id",
    ):
        op.execute(f"ALTER TABLE graph_update_tasks DROP COLUMN {column}")
