from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext

from app.domains.graph import worker
from app.domains.graph.task_planner import TaskPlanningError


def _task():
    return {
        "id": 7,
        "task_uuid": "a" * 32,
        "task_type": "job_import",
        "status": "running",
        "lease_token": "b" * 32,
        "attempt_count": 1,
        "base_graph_revision": 0,
        "config_snapshot": {},
    }


def test_error_policy_separates_invalid_input_and_transient_failures():
    assert worker._error_policy(TaskPlanningError("CSV 缺少必要字段")) == ("invalid_input", False)
    assert worker._error_policy(TimeoutError("provider timed out")) == ("transient_io", True)
    assert worker._error_policy(RuntimeError("LLM service unavailable")) == ("transient_provider", True)
    assert worker._error_policy(RuntimeError("未配置 NEO4J_PASSWORD"))[1] is False


def test_retry_delay_is_bounded_and_spreads_tasks():
    assert worker._retry_delay(1, 5, 1) == 6
    assert worker._retry_delay(2, 5, 2) == 12
    assert worker._retry_delay(20, 5, 7) <= 305


def test_worker_does_not_retry_invalid_dataset(app, monkeypatch):
    captured = {}
    monkeypatch.setattr(worker.repo, "claim_next_task", lambda **_kwargs: _task())
    monkeypatch.setattr(worker.repo, "add_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "build_change_set", lambda *_args, **_kwargs: (_ for _ in ()).throw(TaskPlanningError("字段错误")))
    monkeypatch.setattr(worker.repo, "fail_or_retry_task", lambda task_id, message, **kwargs: captured.update(task_id=task_id, message=message, **kwargs))

    with app.app_context():
        assert worker.process_one(worker_id="test", lease_seconds=60, max_attempts=3, retry_base_seconds=5) is True

    assert captured["task_id"] == 7
    assert captured["error_code"] == "invalid_input"
    assert captured["retryable"] is False
    assert captured["lease_token"] == "b" * 32


def test_worker_schedules_retry_for_transient_provider_error(app, monkeypatch):
    captured = {}
    monkeypatch.setattr(worker.repo, "claim_next_task", lambda **_kwargs: _task())
    monkeypatch.setattr(worker.repo, "add_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "build_change_set", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("provider timed out")))
    monkeypatch.setattr(worker.repo, "fail_or_retry_task", lambda task_id, message, **kwargs: captured.update(task_id=task_id, message=message, **kwargs))

    with app.app_context():
        assert worker.process_one(worker_id="test", lease_seconds=60, max_attempts=3, retry_base_seconds=5) is True

    assert captured["error_code"] == "transient_io"
    assert captured["retryable"] is True
    assert captured["max_attempts"] == 3
    assert captured["retry_delay_seconds"] == 6


def test_worker_prepares_new_tasks_as_chunked_change_sets(app, monkeypatch):
    captured = {}
    monkeypatch.setattr(worker.repo, "claim_next_task", lambda **_kwargs: _task())
    monkeypatch.setattr(worker.repo, "add_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "graph_write_lock", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(
        worker,
        "build_change_set",
        lambda *_args, **_kwargs: (
            {"version": 2, "kind": "job_capability_evaluation", "jobs": [{"job_key": "j1"}]},
            {"jobs": 1},
        ),
    )
    monkeypatch.setattr(worker.repo, "prepare_task", lambda task_id, **kwargs: captured.update(task_id=task_id, **kwargs) or True)

    with app.app_context():
        assert worker.process_one(worker_id="test", lease_seconds=60) is True

    assert captured["task_id"] == 7
    assert captured["change_manifest"] == {"version": 2, "kind": "job_capability_evaluation"}
    assert len(captured["change_chunks"]) == 1
    assert captured["change_chunks"][0].group_name == "jobs"
    assert "change_set_json" not in captured


def _applying_task(*, committed=False, task_type="competition_import"):
    change = {"version": 2, "kind": task_type, "items": []}
    encoded = json.dumps(change, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "id": 11,
        "task_uuid": "c" * 32,
        "task_type": task_type,
        "status": "applying",
        "lease_token": "d" * 32,
        "change_set": change,
        "change_set_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "neo4j_committed_at": "2026-07-16" if committed else None,
        "projection_attempts": 0,
    }


def test_confirmed_task_is_applied_by_worker_not_http_request(app, monkeypatch):
    task = _applying_task(); calls = []
    monkeypatch.setattr(worker.repo, "claim_next_applying_task", lambda **_kwargs: task)
    monkeypatch.setattr(worker.repo, "verify_task_change_set", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(worker.repo, "iter_change_group_chunks", lambda *_args, **_kwargs: iter(()))
    monkeypatch.setattr(worker, "graph_write_lock", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(worker, "is_task_applied", lambda _uuid: False)
    monkeypatch.setattr(worker, "apply_change_set", lambda change, **kwargs: calls.append((change, kwargs)) or {})
    monkeypatch.setattr(worker.repo, "mark_neo4j_committed", lambda task_id, **_kwargs: calls.append(("committed", task_id)) or True)
    monkeypatch.setattr(worker, "projection_required", lambda _task: False)
    monkeypatch.setattr(worker.repo, "finish_projection", lambda task_id, **kwargs: calls.append(("finished", task_id, kwargs)) or True)

    with app.app_context():
        assert worker.process_applying_one(worker_id="test", lease_seconds=60) is True

    assert calls[0][1]["task_uuid"] == "c" * 32
    assert calls[0][1]["group_loader"] is None
    assert ("committed", 11) in calls
    assert ("finished", 11, {"lease_token": "d" * 32, "required": False}) in calls


def test_projection_failure_retries_without_reapplying_neo4j(app, monkeypatch):
    task = _applying_task(committed=True, task_type="job_import"); captured = {}
    monkeypatch.setattr(worker.repo, "claim_next_applying_task", lambda **_kwargs: task)
    monkeypatch.setattr(worker.repo, "verify_task_change_set", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(worker, "apply_change_set", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not reapply Neo4j")))
    monkeypatch.setattr(worker, "projection_required", lambda _task: True)
    monkeypatch.setattr(worker.repo, "start_projection", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(worker, "project_task", lambda _task: (_ for _ in ()).throw(TimeoutError("mysql unavailable")))
    monkeypatch.setattr(worker.repo, "schedule_projection_retry", lambda task_id, error, **kwargs: captured.update(task_id=task_id, error=error, **kwargs) or True)

    with app.app_context():
        assert worker.process_applying_one(worker_id="test", lease_seconds=60, retry_base_seconds=5) is True

    assert captured["task_id"] == 11
    assert "mysql unavailable" in captured["error"]
    assert captured["lease_token"] == "d" * 32


def test_chunked_applying_task_receives_streaming_group_loader(app, monkeypatch):
    task = _applying_task()
    task["change_storage_version"] = 2
    calls = []
    monkeypatch.setattr(worker.repo, "claim_next_applying_task", lambda **_kwargs: task)
    monkeypatch.setattr(worker.repo, "verify_task_change_set", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(worker.repo, "iter_change_group_chunks", lambda task_id, group: iter([[{"task": task_id, "group": group}]]))
    monkeypatch.setattr(worker, "graph_write_lock", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(worker, "is_task_applied", lambda _uuid: False)

    def apply(_change, **kwargs):
        calls.extend(kwargs["group_loader"]("items"))
        return {}

    monkeypatch.setattr(worker, "apply_change_set", apply)
    monkeypatch.setattr(worker.repo, "mark_neo4j_committed", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(worker, "projection_required", lambda _task: False)
    monkeypatch.setattr(worker.repo, "finish_projection", lambda *_args, **_kwargs: True)
    with app.app_context():
        assert worker.process_applying_one(worker_id="test", lease_seconds=60) is True
    assert calls == [[{"task": 11, "group": "items"}]]


def test_mysql_commit_record_failure_never_marks_committed_graph_failed(app, monkeypatch):
    task = _applying_task(); calls = {"marker_checks": 0, "released": 0, "failed": 0}
    monkeypatch.setattr(worker.repo, "claim_next_applying_task", lambda **_kwargs: task)
    monkeypatch.setattr(worker.repo, "verify_task_change_set", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(worker.repo, "iter_change_group_chunks", lambda *_args, **_kwargs: iter(()))
    monkeypatch.setattr(worker, "graph_write_lock", lambda **_kwargs: nullcontext())

    def marker(_uuid):
        calls["marker_checks"] += 1
        return calls["marker_checks"] > 1

    monkeypatch.setattr(worker, "is_task_applied", marker)
    monkeypatch.setattr(worker, "apply_change_set", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(worker.repo, "mark_neo4j_committed", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("mysql unavailable")))
    monkeypatch.setattr(worker.repo, "release_applying_lease", lambda *_args, **_kwargs: calls.__setitem__("released", calls["released"] + 1) or True)
    monkeypatch.setattr(worker.repo, "fail_apply", lambda *_args, **_kwargs: calls.__setitem__("failed", calls["failed"] + 1) or True)

    with app.app_context():
        assert worker.process_applying_one(worker_id="test", lease_seconds=60) is True

    assert calls["released"] == 1
    assert calls["failed"] == 0
