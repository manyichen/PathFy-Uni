"""Track asynchronous Neo4j commits and MySQL projection retries."""

from alembic import op

revision = "20260715_0007"
down_revision = "20260715_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN confirm_requested_at DATETIME(6) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN neo4j_committed_at DATETIME(6) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN projection_status VARCHAR(32) NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN projection_attempts INT UNSIGNED NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN projection_error TEXT NULL")
    op.execute("ALTER TABLE graph_update_tasks ADD COLUMN projection_next_retry_at DATETIME(6) NULL")
    op.execute("CREATE INDEX ix_graph_tasks_projection_due ON graph_update_tasks (status,projection_status,projection_next_retry_at)")


def downgrade() -> None:
    op.execute("DROP INDEX ix_graph_tasks_projection_due ON graph_update_tasks")
    for column in (
        "projection_next_retry_at",
        "projection_error",
        "projection_attempts",
        "projection_status",
        "neo4j_committed_at",
        "confirm_requested_at",
    ):
        op.execute(f"ALTER TABLE graph_update_tasks DROP COLUMN {column}")
