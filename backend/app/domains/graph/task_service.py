"""Application service for graph update queue APIs and confirmation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage

from app.domains.graph import task_repository as repo
from app.domains.graph.incremental import normalize_source_id
from app.domains.graph.task_registry import TASK_TYPES, normalize_options, task_spec
from app.domains.settings.service import active_system_settings


class GraphTaskError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message); self.message = message; self.status = status


def _remove(path: str | None) -> None:
    if path:
        try: Path(path).unlink(missing_ok=True)
        except OSError: pass


def _save_upload(root: Path, task_uuid: str, role: str, upload: FileStorage, allowed: frozenset[str], max_bytes: int) -> dict:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed:
        raise GraphTaskError(f"{role} 文件格式必须是 {', '.join(sorted(allowed))}")
    target = root / f"{task_uuid}-{role}{suffix}"
    upload.save(target)
    target.chmod(0o600)
    size = target.stat().st_size
    if size > max_bytes:
        target.unlink(missing_ok=True)
        raise GraphTaskError(f"{role} 文件超过 {max_bytes // (1024 * 1024)} MiB 限制", 413)
    hasher = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return {"role": role, "original_name": Path(upload.filename or "").name,
            "private_path": str(target), "size": size,
            "sha256": hasher.hexdigest(), "media_type": upload.mimetype}


def enqueue_task(*, user_id: int, task_type: str, uploaded_file: FileStorage | None = None,
                 uploaded_files: dict[str, FileStorage] | None = None,
                 source_id: str | None = None, mode: str | None = None,
                 batch_size: int | None = None, generate_promotions: bool = True,
                 generate_lateral: bool = True, options: dict | None = None):
    if task_type not in TASK_TYPES: raise GraphTaskError("不支持的任务类型")
    if task_type == "emergency_clear": raise GraphTaskError("紧急清空只能使用 /api/graph/clear 并二次确认")
    spec = task_spec(task_type); system = active_system_settings(); runtime = system["settings"]
    mode = str(mode or spec.default_mode).lower()
    if mode not in {"merge", "snapshot"}: raise GraphTaskError("mode 仅支持 merge 或 snapshot")
    if mode == "snapshot" and spec.supports_source and not str(source_id or "").strip(): raise GraphTaskError("snapshot 模式必须填写 source_id")
    uploads = dict(uploaded_files or {})
    if uploaded_file is not None:
        uploads.setdefault("file", uploaded_file)
    for file_spec in spec.files:
        if file_spec.required and (file_spec.role not in uploads or not uploads[file_spec.role].filename):
            raise GraphTaskError(f"请选择 {file_spec.role} 文件")
    root = Path(current_app.config["GRAPH_TASK_UPLOAD_DIR"]); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    task_uuid = uuid4().hex
    saved: list[dict] = []
    try:
        for file_spec in spec.files:
            upload = uploads.get(file_spec.role)
            if upload and upload.filename:
                saved.append(_save_upload(root, task_uuid, file_spec.role, upload, file_spec.extensions, file_spec.max_bytes))
        values = dict(options or {})
        values.update(batch_size=batch_size or int(runtime["GRAPH_BATCH_SIZE"]), generate_promotions=generate_promotions, generate_lateral=generate_lateral)
        values.setdefault("capability_batch_size", int(runtime["GRAPH_CAPABILITY_BATCH_SIZE"]))
        try:
            normalized_options = normalize_options(task_type, values)
        except ValueError as exc:
            raise GraphTaskError(str(exc)) from exc
        primary_name = saved[0]["original_name"] if saved else task_type
        resolved_source = str(source_id or "").strip() or (normalize_source_id(primary_name) if spec.supports_source else None)
        return repo.create_task(task_uuid=task_uuid, task_type=task_type, requested_by=user_id,
            files=saved, source_id=resolved_source, mode=mode, options=normalized_options,
            settings_revision=system.get("revision"), config_snapshot=runtime)
    except Exception:
        for item in saved: _remove(item.get("private_path"))
        raise


def list_tasks(**kwargs): return repo.list_tasks(**kwargs)


def task_detail(task_id: int):
    task = repo.get_task(task_id)
    if not task: raise GraphTaskError("任务不存在", 404)
    return task


def downloadable_task_file(task_id: int, role: str) -> dict:
    item = repo.get_task_file(task_id, role)
    if not item:
        raise GraphTaskError("任务文件不存在", 404)
    if not item.get("private_path"):
        raise GraphTaskError("该历史任务的原始文件已按旧保留策略删除", 410)
    root = Path(current_app.config["GRAPH_TASK_UPLOAD_DIR"]).resolve()
    path = Path(str(item["private_path"])).resolve()
    if path.parent != root or not path.is_file():
        raise GraphTaskError("任务文件已丢失或路径无效", 404)
    return {**item, "path": str(path)}


def task_changes(task_id: int, *, group: str | None, page: int, page_size: int):
    result = repo.task_changes(task_id, group=group, page=page, page_size=page_size)
    if result is None: raise GraphTaskError("任务不存在", 404)
    return result


def guard_status():
    guard = repo.get_guard(); locked = guard.get("locked_task_id")
    return {"graph_revision": int(guard["graph_revision"]), "locked": bool(locked), "locked_task_id": locked, "locked_at": guard.get("locked_at")}


def _verify_change_set(task):
    change = task.get("change_set")
    if not change: raise GraphTaskError("任务没有可应用的变更集", 409)
    if not repo.verify_task_change_set(int(task["id"]), expected_sha256=task.get("change_set_sha256")):
        raise GraphTaskError("变更集校验失败，已拒绝提交", 409)
    return change


def confirm_task(task_id: int, user_id: int):
    task = repo.get_task(task_id, include_change_set=True)
    if not task:
        raise GraphTaskError("任务不存在", 404)
    _verify_change_set(task)
    applying = repo.set_applying(task_id, user_id, expected_sha256=task["change_set_sha256"])
    if not applying:
        raise GraphTaskError("任务不在待确认状态、图谱版本已变化或未持有写锁", 409)
    return {"task_id": task_id, "status": "applying", "accepted": True}


def reject_task(task_id: int, user_id: int, reason: str):
    task = repo.get_task(task_id, include_change_set=True)
    if not task: raise GraphTaskError("任务不存在", 404)
    if not reason.strip(): raise GraphTaskError("请填写拒绝原因")
    if not repo.reject_task(task_id, user_id, reason.strip()): raise GraphTaskError("任务不在待确认状态", 409)
    return {"task_id": task_id, "status": "rejected"}


def cancel_task(task_id: int, user_id: int):
    task = repo.get_task(task_id, include_change_set=True)
    if not task: raise GraphTaskError("任务不存在", 404)
    if not repo.cancel_task(task_id, user_id): raise GraphTaskError("只能取消 queued 任务", 409)
    return {"task_id": task_id, "status": "cancelled"}
