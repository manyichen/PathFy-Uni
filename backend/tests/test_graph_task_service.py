from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext

import pytest

from app.domains.graph import task_service


def _prepared_task(change=None):
    change = change or {"version": 1, "kind": "competition_import", "items": []}
    encoded = json.dumps(change, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "id": 3, "task_uuid": "a" * 32, "status": "awaiting_confirmation",
        "change_set": change, "change_set_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "input_file_path": None,
    }


def test_confirm_verifies_and_applies_whole_change_set(monkeypatch):
    task = _prepared_task(); calls = []
    monkeypatch.setattr(task_service.repo, "set_applying", lambda task_id, user_id: task)
    monkeypatch.setattr(task_service, "apply_change_set", lambda change, **kwargs: calls.append((change, kwargs)) or {"run_id": "r1"})
    monkeypatch.setattr(task_service.repo, "finish_apply", lambda task_id, **kwargs: calls.append((task_id, kwargs)))
    monkeypatch.setattr(task_service, "graph_write_lock", lambda **_kwargs: nullcontext())
    result = task_service.confirm_task(3, 9)
    assert result["run_id"] == "r1"
    assert calls[0][1]["task_uuid"] == "a" * 32
    assert calls[1] == (3, {"success": True, "error": None, "partial": False})


def test_confirm_rejects_tampered_change_set(monkeypatch):
    task = _prepared_task(); task["change_set"]["items"].append({"changed": True})
    monkeypatch.setattr(task_service.repo, "set_applying", lambda task_id, user_id: task)
    monkeypatch.setattr(task_service.repo, "finish_apply", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(task_service, "is_task_applied", lambda _uuid: False)
    monkeypatch.setattr(task_service, "graph_write_lock", lambda **_kwargs: nullcontext())
    with pytest.raises(task_service.GraphTaskError, match="校验失败"):
        task_service.confirm_task(3, 9)


def test_reject_requires_reason_and_never_applies(monkeypatch):
    monkeypatch.setattr(task_service.repo, "get_task", lambda *_args, **_kwargs: _prepared_task())
    with pytest.raises(task_service.GraphTaskError, match="拒绝原因"):
        task_service.reject_task(3, 9, "")
    monkeypatch.setattr(task_service.repo, "reject_task", lambda task_id, user_id, reason: True)
    assert task_service.reject_task(3, 9, "数据不完整")["status"] == "rejected"
