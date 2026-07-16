from __future__ import annotations

from contextlib import contextmanager

from app.domains.graph import task_repository
from app.domains.graph.change_storage import canonical_json, encode_change_set


def test_inverse_task_is_copied_to_review_queue_and_locks_current_revision(monkeypatch):
    encoded = encode_change_set({
        "version": 2, "kind": "graph_inverse", "inverse_of_kind": "salary_normalization",
        "jobs": [{"job_key": "j1", "properties": {"salary_norm": "10k"}}],
    })
    chunk_rows = [{
        "group_name": item.group_name, "chunk_no": item.chunk_no,
        "item_count": item.item_count, "chunk_sha256": item.sha256,
        "payload_json": item.payload_json,
    } for item in encoded.chunks]

    class Cursor:
        rowcount = 1
        lastrowid = 99

        def __init__(self):
            self.one = None
            self.many = []
            self.executemany_rows = []
            self.guard_update = None

        def execute(self, query, params=None):
            if "SELECT * FROM graph_write_guard" in query:
                self.one = {"id": 1, "graph_revision": 4, "locked_task_id": None}
            elif "SELECT id,status,task_type" in query:
                self.one = {
                    "id": 7, "status": "succeeded", "task_type": "salary_normalization",
                    "base_graph_revision": 3, "inverse_manifest_json": canonical_json(encoded.manifest),
                    "inverse_sha256": encoded.sha256,
                }
            elif "SELECT 1 FROM graph_update_tasks WHERE inverse_of_task_id" in query:
                self.one = None
            elif "status IN ('running','awaiting_confirmation','applying')" in query:
                self.one = None
            elif "FROM graph_update_task_inverse_chunks" in query:
                self.many = list(chunk_rows)
            elif "INSERT INTO graph_update_tasks" in query:
                self.lastrowid = 99
            elif "UPDATE graph_write_guard SET locked_task_id" in query:
                self.guard_update = params
            elif "SELECT * FROM graph_update_tasks WHERE id" in query:
                self.one = {
                    "id": 99, "task_uuid": "x" * 32, "task_type": "graph_inverse",
                    "status": "awaiting_confirmation", "change_storage_version": 2,
                    "options_json": "{}", "config_snapshot_json": "{}",
                    "change_summary_json": '{"restored_jobs":1}',
                    "change_manifest_json": canonical_json(encoded.manifest),
                    "change_set_json": None, "inverse_manifest_json": None,
                }
            else:
                self.one = None

        def executemany(self, _query, rows):
            self.executemany_rows = list(rows)

        def fetchone(self):
            value, self.one = self.one, None
            return value

        def fetchall(self):
            value, self.many = self.many, []
            return value

    cursor = Cursor()

    @contextmanager
    def fake_db_cursor():
        yield object(), cursor

    monkeypatch.setattr(task_repository, "db_cursor", fake_db_cursor)
    task = task_repository.create_inverse_task(
        7, requested_by=2, settings_revision=5, config_snapshot={"GRAPH_CAP_VERSION": "v2"},
    )
    assert task["id"] == 99
    assert task["status"] == "awaiting_confirmation"
    assert cursor.guard_update == (99,)
    assert cursor.executemany_rows[0][0] == 99
    assert cursor.executemany_rows[0][1] == "jobs"


def test_public_task_detail_omits_frozen_config_snapshot(monkeypatch):
    executed: list[str] = []

    class Cursor:
        def execute(self, query, _params=None):
            executed.append(query)

        def fetchone(self):
            return {
                "id": 4, "task_type": "salary_normalization", "status": "succeeded",
                "options_json": "{}", "change_summary_json": "{}",
                "inverse_available": 0,
            }

        def fetchall(self):
            return []

    @contextmanager
    def fake_db_cursor():
        yield object(), Cursor()

    monkeypatch.setattr(task_repository, "db_cursor", fake_db_cursor)
    task = task_repository.get_task(4)
    assert task["id"] == 4
    assert "config_snapshot" not in task
    task_select = next(query for query in executed if "FROM graph_update_tasks WHERE id" in query)
    assert "config_snapshot_json" not in task_select


def test_operational_metrics_are_bounded_aggregates(monkeypatch):
    rows = iter([
        {"queue_depth": 2, "oldest_queue_seconds": 20, "queue_wait_avg_seconds": 3.5,
         "projection_backlog": 1, "failed_7d": 2, "completed_7d": 8},
        {"active_workers": 1, "worker_heartbeat_age_seconds": 4},
        {"llm_calls": 10, "llm_total_tokens": 900, "llm_duration_ms": 1200,
         "llm_cache_hits": 3, "llm_retries": 2},
        {"graph_lock_seconds": 6},
    ])

    class Cursor:
        def execute(self, _query, _params=None):
            pass

        def fetchone(self):
            return next(rows)

    @contextmanager
    def fake_db_cursor():
        yield object(), Cursor()

    monkeypatch.setattr(task_repository, "db_cursor", fake_db_cursor)
    result = task_repository.operational_metrics()
    assert result["failure_rate_7d"] == 0.25
    assert result["queue_depth"] == 2
    assert result["active_workers"] == 1
    assert result["llm_total_tokens"] == 900
