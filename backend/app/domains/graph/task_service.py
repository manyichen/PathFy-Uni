"""Application service for graph update queue APIs and confirmation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage

from app.domains.graph import task_repository as repo
from app.domains.graph.services import _sync_job_titles_from_graph
from app.domains.graph.task_apply import apply_change_set, is_task_applied
from app.domains.graph.incremental import normalize_source_id
from app.domains.graph.locking import graph_write_lock
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings
from app.domains.graph.task_registry import TASK_TYPES, normalize_options, task_spec


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
                 batch_size: int = 128, generate_promotions: bool = True,
                 generate_lateral: bool = True, options: dict | None = None):
    if task_type not in TASK_TYPES: raise GraphTaskError("不支持的任务类型")
    if task_type == "emergency_clear": raise GraphTaskError("紧急清空只能使用 /api/graph/clear 并二次确认")
    spec = task_spec(task_type)
    mode = str(mode or spec.default_mode).lower()
    if mode not in {"merge", "snapshot"}: raise GraphTaskError("mode 仅支持 merge 或 snapshot")
    if mode == "snapshot" and spec.supports_source and not str(source_id or "").strip(): raise GraphTaskError("snapshot 模式必须填写 source_id")
    uploads = dict(uploaded_files or {})
    if uploaded_file is not None:
        uploads.setdefault("file", uploaded_file)
    for file_spec in spec.files:
        if file_spec.required and (file_spec.role not in uploads or not uploads[file_spec.role].filename):
            raise GraphTaskError(f"请选择 {file_spec.role} 文件")
    root = Path(current_app.config["GRAPH_TASK_UPLOAD_DIR"]); root.mkdir(parents=True, exist_ok=True)
    task_uuid = uuid4().hex
    saved: list[dict] = []
    try:
        for file_spec in spec.files:
            upload = uploads.get(file_spec.role)
            if upload and upload.filename:
                saved.append(_save_upload(root, task_uuid, file_spec.role, upload, file_spec.extensions, file_spec.max_bytes))
        values = dict(options or {})
        values.update(batch_size=batch_size, generate_promotions=generate_promotions, generate_lateral=generate_lateral)
        try:
            normalized_options = normalize_options(task_type, values)
        except ValueError as exc:
            raise GraphTaskError(str(exc)) from exc
        primary_name = saved[0]["original_name"] if saved else task_type
        resolved_source = str(source_id or "").strip() or (normalize_source_id(primary_name) if spec.supports_source else None)
        return repo.create_task(task_uuid=task_uuid, task_type=task_type, requested_by=user_id,
            files=saved, source_id=resolved_source, mode=mode, options=normalized_options)
    except Exception:
        for item in saved: _remove(item.get("private_path"))
        raise


def list_tasks(**kwargs): return repo.list_tasks(**kwargs)


def task_detail(task_id: int):
    task = repo.get_task(task_id)
    if not task: raise GraphTaskError("任务不存在", 404)
    return task


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
    encoded = json.dumps(change, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(encoded.encode()).hexdigest() != task.get("change_set_sha256"):
        raise GraphTaskError("变更集校验失败，已拒绝提交", 409)
    return change


def _sync_mysql_titles() -> None:
    uri, user, password, database = neo4j_settings(); driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = session.run("MATCH (jt:JobTitle) RETURN jt.name AS name,coalesce(jt.job_count,0) AS count,coalesce(jt.company_count,0) AS company_count,coalesce(jt.job_code_count,0) AS job_code_count")
        data = [dict(r) for r in rows]
    _sync_job_titles_from_graph(data)


def _task_paths(task: dict) -> list[str]:
    paths = [str(item.get("private_path")) for item in task.get("files", []) if item.get("private_path")]
    if task.get("input_file_path") and task["input_file_path"] not in paths:
        paths.append(task["input_file_path"])
    return paths


def _purge_task_files(task: dict) -> None:
    paths = _task_paths(task)
    for path in paths: _remove(path)
    if task.get("files") or paths:
        repo.clear_task_file_paths(int(task["id"]))


def confirm_task(task_id: int, user_id: int):
    task = repo.set_applying(task_id, user_id)
    if not task: raise GraphTaskError("任务不在待确认状态或未持有写锁", 409)
    try:
        change = _verify_change_set(task)
        with graph_write_lock(allowed_task_id=task_id):
            result = apply_change_set(change, task_uuid=task["task_uuid"], change_sha256=task["change_set_sha256"])
            sync_error = None
            if change.get("kind") == "job_import":
                try: _sync_mysql_titles()
                except Exception as exc: sync_error = f"Neo4j 已提交，但 MySQL job_titles 同步失败: {exc}"
            repo.finish_apply(task_id, success=True, error=sync_error, partial=bool(sync_error))
        _purge_task_files(task)
        return {**result, "warning": sync_error}
    except Exception as exc:
        try: applied = is_task_applied(task["task_uuid"])
        except Exception: applied = False
        if applied:
            repo.finish_apply(task_id, success=True, partial=True, error=f"Neo4j 已提交，任务元数据或 MySQL 同步异常: {exc}"[:65000])
            _purge_task_files(task)
            raise GraphTaskError(f"Neo4j 已提交，但后续同步异常: {exc}", 500) from exc
        repo.finish_apply(task_id, success=False, error=str(exc)[:65000])
        _purge_task_files(task)
        raise GraphTaskError(f"应用变更失败，Neo4j 事务已回滚: {exc}", 500) from exc


def reject_task(task_id: int, user_id: int, reason: str):
    task = repo.get_task(task_id, include_change_set=True)
    if not task: raise GraphTaskError("任务不存在", 404)
    if not reason.strip(): raise GraphTaskError("请填写拒绝原因")
    if not repo.reject_task(task_id, user_id, reason.strip()): raise GraphTaskError("任务不在待确认状态", 409)
    _purge_task_files(task); return {"task_id": task_id, "status": "rejected"}


def cancel_task(task_id: int, user_id: int):
    task = repo.get_task(task_id, include_change_set=True)
    if not task: raise GraphTaskError("任务不存在", 404)
    if not repo.cancel_task(task_id, user_id): raise GraphTaskError("只能取消 queued 任务", 409)
    _purge_task_files(task); return {"task_id": task_id, "status": "cancelled"}
