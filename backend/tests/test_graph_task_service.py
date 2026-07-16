from __future__ import annotations

import hashlib
import json

import pytest

from app.domains.graph import task_service
from app.domains.graph import task_repository


def _prepared_task(change=None):
    change = change or {"version": 1, "kind": "competition_import", "items": []}
    encoded = json.dumps(change, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "id": 3, "task_uuid": "a" * 32, "status": "awaiting_confirmation",
        "change_set": change, "change_set_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "input_file_path": None,
    }


def test_confirm_only_verifies_and_enqueues_async_apply(monkeypatch):
    task = _prepared_task(); calls = []
    monkeypatch.setattr(task_service.repo, "get_task", lambda *_args, **_kwargs: task)
    monkeypatch.setattr(task_service.repo, "set_applying", lambda task_id, user_id, **kwargs: calls.append((task_id, user_id, kwargs)) or task)
    result = task_service.confirm_task(3, 9)
    assert result == {"task_id": 3, "status": "applying", "accepted": True}
    assert calls == [(3, 9, {"expected_sha256": task["change_set_sha256"]})]


def test_confirm_rejects_tampered_change_set(monkeypatch):
    task = _prepared_task(); task["change_set"]["items"].append({"changed": True})
    monkeypatch.setattr(task_service.repo, "get_task", lambda *_args, **_kwargs: task)
    monkeypatch.setattr(task_service.repo, "set_applying", lambda *_args, **_kwargs: pytest.fail("tampered task must not be accepted"))
    with pytest.raises(task_service.GraphTaskError, match="校验失败"):
        task_service.confirm_task(3, 9)


def test_reject_requires_reason_and_never_applies(monkeypatch):
    monkeypatch.setattr(task_service.repo, "get_task", lambda *_args, **_kwargs: _prepared_task())
    with pytest.raises(task_service.GraphTaskError, match="拒绝原因"):
        task_service.reject_task(3, 9, "")
    monkeypatch.setattr(task_service.repo, "reject_task", lambda task_id, user_id, reason: True)
    assert task_service.reject_task(3, 9, "数据不完整")["status"] == "rejected"


def test_change_preview_exposes_delete_and_retained_manifests(monkeypatch):
    monkeypatch.setattr(task_repository, "get_task", lambda *_args, **_kwargs: {
        "change_set": {
            "version": 2,
            "jobs": [{"job_key": "new"}],
            "delete_manifest": {"jobs": [{"job_key": "old"}]},
            "retained_manifest": {"job_titles": [{"name": "策展岗位"}]},
        }
    })
    result = task_repository.task_changes(1, group="delete.jobs", page=1, page_size=20)
    assert result["groups"] == {"jobs": 1, "delete.jobs": 1, "retained.job_titles": 1}
    assert result["items"] == [{"job_key": "old"}]
