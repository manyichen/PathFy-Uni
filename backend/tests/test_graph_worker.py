from __future__ import annotations

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
