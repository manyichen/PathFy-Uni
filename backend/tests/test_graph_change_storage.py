from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from app.domains.graph import task_repository
from app.domains.graph.change_storage import encode_change_set, verify_chunk_rows


def _rows(encoded):
    return [
        {
            "group_name": chunk.group_name,
            "chunk_no": chunk.chunk_no,
            "item_count": chunk.item_count,
            "chunk_sha256": chunk.sha256,
            "payload_json": chunk.payload_json,
        }
        for chunk in encoded.chunks
    ]


def test_change_set_chunks_have_stable_hash_and_detect_missing_or_tampered_data():
    change = {
        "version": 2,
        "kind": "job_capability_evaluation",
        "jobs": [{"job_key": f"j{index}"} for index in range(5)],
        "delete_manifest": {"jobs": [{"job_key": "old"}]},
    }
    encoded = encode_change_set(change, chunk_size=2)
    rows = _rows(encoded)
    assert encoded.manifest == {"version": 2, "kind": "job_capability_evaluation"}
    assert [(item.group_name, item.chunk_no, item.item_count) for item in encoded.chunks] == [
        ("jobs", 0, 2), ("jobs", 1, 2), ("jobs", 2, 1), ("delete.jobs", 0, 1),
    ]
    assert verify_chunk_rows(encoded.manifest, rows, encoded.sha256)
    assert not verify_chunk_rows(encoded.manifest, rows[:-1], encoded.sha256)
    tampered = [dict(row) for row in rows]
    tampered[0]["payload_json"] = json.dumps([{"job_key": "changed"}])
    assert not verify_chunk_rows(encoded.manifest, tampered, encoded.sha256)
    reordered = [rows[1], rows[0], *rows[2:]]
    assert not verify_chunk_rows(encoded.manifest, reordered, encoded.sha256)


def test_chunked_change_preview_uses_sql_page_without_loading_full_task(monkeypatch):
    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, query, params):
            if "SELECT change_storage_version" in query:
                self.rows = [{"change_storage_version": 2}]
            elif "SUM(item_count) AS total" in query:
                self.rows = [{"group_name": "jobs", "total": 5, "first_id": 1}]
            elif "offset_before" in query:
                assert params == (9, "jobs", 4, 2)
                self.rows = [{
                    "payload_json": json.dumps([{"id": 1}, {"id": 2}, {"id": 3}]),
                    "item_count": 3,
                    "offset_before": 0,
                }, {
                    "payload_json": json.dumps([{"id": 4}, {"id": 5}]),
                    "item_count": 2,
                    "offset_before": 3,
                }]
            else:
                raise AssertionError(query)

        def fetchone(self):
            return self.rows.pop(0) if self.rows else None

        def fetchall(self):
            rows, self.rows = self.rows, []
            return rows

    @contextmanager
    def fake_cursor():
        yield object(), Cursor()

    monkeypatch.setattr(task_repository, "db_cursor", fake_cursor)
    monkeypatch.setattr(task_repository, "get_task", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not load LONGTEXT")))
    result = task_repository.task_changes(9, group="jobs", page=2, page_size=2)
    assert result["items"] == [{"id": 3}, {"id": 4}]
    assert result["total"] == 5


def test_graph_domain_has_one_normal_write_boundary():
    root = Path(__file__).parents[1] / "app/domains/graph"
    sources = {path.name: path.read_text(encoding="utf-8") for path in root.glob("*.py")}
    assert [name for name, source in sources.items() if "execute_write" in source] == ["task_apply.py"]
    for name in ("services.py", "sync_service.py"):
        assert "DETACH DELETE" not in sources[name]
        assert "CREATE CONSTRAINT" not in sources[name]
    assert sources["repository.py"].count("DETACH DELETE") == 1
