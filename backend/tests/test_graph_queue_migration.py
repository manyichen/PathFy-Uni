"""Graph queue migration contract."""

from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "migrations/versions/20260713_0002_graph_update_queue.py"
CATALOG_MIGRATION = Path(__file__).parents[1] / "migrations/versions/20260714_0003_graph_task_catalog.py"
LEASE_MIGRATION = Path(__file__).parents[1] / "migrations/versions/20260715_0006_graph_worker_leases.py"


def test_graph_queue_migration_contains_durable_models():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "20260712_0001"' in source
    for table in ("graph_update_tasks", "graph_update_task_events", "graph_write_guard"):
        assert f"CREATE TABLE {table}" in source
        assert f"DROP TABLE IF EXISTS {table}" in source
    for status in ("queued", "running", "awaiting_confirmation", "applying", "succeeded", "partial_failed", "failed", "rejected", "cancelled"):
        assert status in source


def test_guard_starts_unlocked_at_revision_zero():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "INSERT INTO graph_write_guard (id, graph_revision) VALUES (1, 0)" in source


def test_graph_task_catalog_migration_supports_multiple_files():
    source = CATALOG_MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "20260713_0002"' in source
    assert "CREATE TABLE graph_update_task_files" in source
    assert "promotion_recommendation_import" in source
    assert "salary_normalization" in source


def test_graph_worker_lease_migration_is_reversible():
    source = LEASE_MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "20260715_0005"' in source
    for column in (
        "worker_id", "lease_token", "heartbeat_at", "lease_expires_at",
        "attempt_count", "next_retry_at", "last_error_code", "last_error_retryable",
    ):
        assert f"ADD COLUMN {column}" in source
        assert f'"{column}"' in source
    assert "ix_graph_tasks_queue_retry" in source
    assert "ix_graph_tasks_lease_expiry" in source
