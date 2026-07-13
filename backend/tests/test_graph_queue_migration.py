"""Graph queue migration contract."""

from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "migrations/versions/20260713_0002_graph_update_queue.py"


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
