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

TASK_TYPES = {"job_import", "learning_resource_import", "competition_import"}


class GraphTaskError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message); self.message = message; self.status = status


def _remove(path: str | None) -> None:
    if path:
        try: Path(path).unlink(missing_ok=True)
        except OSError: pass


def enqueue_task(*, user_id: int, task_type: str, uploaded_file: FileStorage,
                 source_id: str | None, mode: str, batch_size: int,
                 generate_promotions: bool, generate_lateral: bool):
    if task_type not in TASK_TYPES: raise GraphTaskError("不支持的任务类型")
    if not uploaded_file or not uploaded_file.filename: raise GraphTaskError("请选择导入文件")
    mode = str(mode or "merge").lower()
    if mode not in {"merge", "snapshot"}: raise GraphTaskError("mode 仅支持 merge 或 snapshot")
    if mode == "snapshot" and not str(source_id or "").strip(): raise GraphTaskError("snapshot 模式必须填写 source_id")
    suffix = Path(uploaded_file.filename).suffix.lower()
    allowed = {".xls", ".xlsx"} if task_type == "job_import" else {".csv"}
    if suffix not in allowed: raise GraphTaskError(f"文件格式必须是 {', '.join(sorted(allowed))}")
    root = Path(current_app.config["GRAPH_TASK_UPLOAD_DIR"]); root.mkdir(parents=True, exist_ok=True)
    task_uuid = uuid4().hex; target = root / f"{task_uuid}{suffix}"
    uploaded_file.save(target)
    size = target.stat().st_size
    hasher = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): hasher.update(chunk)
    digest = hasher.hexdigest()
    resolved_source = str(source_id or "").strip() or normalize_source_id(uploaded_file.filename)
    options = {"batch_size": max(1, min(int(batch_size), 1000)), "generate_promotions": bool(generate_promotions), "generate_lateral": bool(generate_lateral)}
    try:
        return repo.create_task(task_uuid=task_uuid, task_type=task_type, requested_by=user_id,
            file_name=Path(uploaded_file.filename).name, file_path=str(target), file_size=size,
            sha256=digest, source_id=resolved_source, mode=mode, options=options)
    except Exception:
        _remove(str(target)); raise


def list_tasks(**kwargs): return repo.list_tasks(**kwargs)


def task_detail(task_id: int):
    task = repo.get_task(task_id)
    if not task: raise GraphTaskError("任务不存在", 404)
    return task


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


def confirm_task(task_id: int, user_id: int):
    task = repo.set_applying(task_id, user_id)
    if not task: raise GraphTaskError("任务不在待确认状态或未持有写锁", 409)
    path = task.get("input_file_path")
    try:
        with graph_write_lock(allowed_task_id=task_id):
            change = _verify_change_set(task)
            result = apply_change_set(change, task_uuid=task["task_uuid"], change_sha256=task["change_set_sha256"])
            sync_error = None
            if change.get("kind") == "job_import":
                try: _sync_mysql_titles()
                except Exception as exc: sync_error = f"Neo4j 已提交，但 MySQL job_titles 同步失败: {exc}"
            repo.finish_apply(task_id, success=True, error=sync_error, partial=bool(sync_error))
        _remove(path)
        return {**result, "warning": sync_error}
    except Exception as exc:
        try: applied = is_task_applied(task["task_uuid"])
        except Exception: applied = False
        if applied:
            repo.finish_apply(task_id, success=True, partial=True, error=f"Neo4j 已提交，任务元数据或 MySQL 同步异常: {exc}"[:65000])
            _remove(path)
            raise GraphTaskError(f"Neo4j 已提交，但后续同步异常: {exc}", 500) from exc
        repo.finish_apply(task_id, success=False, error=str(exc)[:65000])
        raise GraphTaskError(f"应用变更失败，Neo4j 事务已回滚: {exc}", 500) from exc


def reject_task(task_id: int, user_id: int, reason: str):
    task = repo.get_task(task_id, include_change_set=True)
    if not task: raise GraphTaskError("任务不存在", 404)
    if not reason.strip(): raise GraphTaskError("请填写拒绝原因")
    if not repo.reject_task(task_id, user_id, reason.strip()): raise GraphTaskError("任务不在待确认状态", 409)
    _remove(task.get("input_file_path")); return {"task_id": task_id, "status": "rejected"}


def cancel_task(task_id: int, user_id: int):
    task = repo.get_task(task_id, include_change_set=True)
    if not task: raise GraphTaskError("任务不存在", 404)
    if not repo.cancel_task(task_id, user_id): raise GraphTaskError("只能取消 queued 任务", 409)
    _remove(task.get("input_file_path")); return {"task_id": task_id, "status": "cancelled"}
