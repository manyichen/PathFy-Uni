"""MySQL persistence and state transitions for graph update tasks."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.db import db_cursor

FINAL_STATUSES = {"succeeded", "partial_failed", "failed", "rejected", "cancelled"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode(row: dict[str, Any] | None, *, include_change_set: bool = False):
    if not row:
        return None
    item = dict(row)
    for key in ("options_json", "change_summary_json", "config_snapshot_json"):
        raw = item.pop(key, None)
        item[key.removesuffix("_json")] = json.loads(raw) if isinstance(raw, str) else raw
    raw_change = item.pop("change_set_json", None)
    if include_change_set:
        item["change_set"] = json.loads(raw_change) if isinstance(raw_change, str) else raw_change
    else:
        item.pop("input_file_path", None)
    return item


def create_task(*, task_uuid: str, task_type: str, requested_by: int,
                files: list[dict[str, Any]] | None = None,
                source_id: str | None, mode: str, options: dict[str, Any],
                file_name: str | None = None, file_path: str | None = None,
                file_size: int | None = None, sha256: str | None = None,
                settings_revision: int | None = None, config_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    files = list(files or [])
    if not files and file_name:
        files.append({"role": "file", "original_name": file_name, "private_path": file_path,
                      "size": file_size or 0, "sha256": sha256, "media_type": None})
    primary = next((item for item in files if item["role"] == "file"), files[0] if files else None)
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO graph_update_tasks
              (task_uuid, task_type, requested_by, input_file_name, input_file_path,
               input_file_size, input_sha256, source_id, mode, options_json,settings_revision,config_snapshot_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (task_uuid, task_type, requested_by,
             primary and primary["original_name"], primary and primary["private_path"],
             primary and primary["size"], primary and primary["sha256"],
             source_id, mode, _json(options), settings_revision, _json(config_snapshot or {})),
        )
        task_id = cur.lastrowid
        if files:
            cur.executemany(
                """INSERT INTO graph_update_task_files
                   (task_id,role,original_name,private_path,size,sha256,media_type)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                [(task_id, item["role"], item["original_name"], item.get("private_path"),
                  item["size"], item["sha256"], item.get("media_type")) for item in files],
            )
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json) VALUES (%s,'queued','queue','任务已进入队列',%s)",
            (task_id, _json({"task_type": task_type})),
        )
        cur.execute("SELECT * FROM graph_update_tasks WHERE id=%s", (task_id,))
        task = _decode(cur.fetchone())
        task["files"] = [{**{k: v for k, v in item.items() if k != "private_path"}, "available": bool(item.get("private_path"))} for item in files]
        return task


def _load_files(cur, task_id: int, *, include_paths: bool = False) -> list[dict[str, Any]]:
    columns = "id,role,original_name,size,sha256,media_type,created_at,(private_path IS NOT NULL) AS available"
    if include_paths:
        columns += ",private_path"
    cur.execute(f"SELECT {columns} FROM graph_update_task_files WHERE task_id=%s ORDER BY id", (task_id,))
    return [dict(row) for row in cur.fetchall()]


def add_event(task_id: int, event_type: str, message: str, *, stage: str | None = None,
              detail: dict[str, Any] | None = None) -> None:
    with db_cursor() as (_, cur):
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json) VALUES (%s,%s,%s,%s,%s)",
            (task_id, event_type, stage, message, _json(detail) if detail is not None else None),
        )


def get_guard(*, for_update: bool = False, cursor=None) -> dict[str, Any]:
    suffix = " FOR UPDATE" if for_update else ""
    if cursor is not None:
        cursor.execute("SELECT * FROM graph_write_guard WHERE id=1" + suffix)
        return dict(cursor.fetchone())
    with db_cursor() as (_, cur):
        cur.execute("SELECT * FROM graph_write_guard WHERE id=1")
        return dict(cur.fetchone())


def has_active_tasks() -> bool:
    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM graph_update_tasks WHERE status IN ('running','awaiting_confirmation','applying') LIMIT 1")
        return cur.fetchone() is not None


def claim_next_task(*, worker_id: str = "graph-worker", lease_seconds: int = 60) -> dict[str, Any] | None:
    """Claim one queued task only when no task is running or awaiting confirmation."""
    with db_cursor() as (_, cur):
        guard = get_guard(for_update=True, cursor=cur)
        if guard.get("locked_task_id"):
            return None
        cur.execute(
            "SELECT id FROM graph_update_tasks WHERE status='running' LIMIT 1 FOR UPDATE"
        )
        if cur.fetchone():
            return None
        cur.execute(
            """SELECT id FROM graph_update_tasks
               WHERE status='queued' AND (next_retry_at IS NULL OR next_retry_at<=NOW(6))
               ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"""
        )
        row = cur.fetchone()
        if not row:
            return None
        task_id = int(row["id"])
        lease_token = uuid4().hex
        cur.execute(
            """UPDATE graph_update_tasks SET status='running',started_at=COALESCE(started_at,NOW(6)),
               base_graph_revision=%s,worker_id=%s,lease_token=%s,heartbeat_at=NOW(6),
               lease_expires_at=DATE_ADD(NOW(6),INTERVAL %s SECOND),attempt_count=attempt_count+1,
               next_retry_at=NULL,last_error_code=NULL,last_error_retryable=NULL
               WHERE id=%s AND status='queued'""",
            (guard["graph_revision"], worker_id[:128], lease_token, max(15, int(lease_seconds)), task_id),
        )
        cur.execute("SELECT * FROM graph_update_tasks WHERE id=%s", (task_id,))
        task = _decode(cur.fetchone(), include_change_set=True)
        task["files"] = _load_files(cur, task_id, include_paths=True)
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'started','worker','Worker 开始生成变更集')",
            (task_id,),
        )
        return task


def renew_lease(task_id: int, lease_token: str, *, lease_seconds: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute(
            """UPDATE graph_update_tasks SET heartbeat_at=NOW(6),
               lease_expires_at=DATE_ADD(NOW(6),INTERVAL %s SECOND)
               WHERE id=%s AND status IN ('running','applying') AND lease_token=%s""",
            (max(15, int(lease_seconds)), task_id, lease_token),
        )
        return cur.rowcount == 1


def recover_expired_tasks() -> int:
    """Requeue only running work whose worker lease has expired."""
    with db_cursor() as (_, cur):
        cur.execute(
            """SELECT id FROM graph_update_tasks WHERE status='running'
               AND (lease_expires_at IS NULL OR lease_expires_at<=NOW(6)) FOR UPDATE"""
        )
        ids = [int(row["id"]) for row in cur.fetchall()]
        if ids:
            cur.execute(
                """UPDATE graph_update_tasks SET status='queued',worker_id=NULL,lease_token=NULL,
                   heartbeat_at=NULL,lease_expires_at=NULL,next_retry_at=NOW(6)
                   WHERE status='running' AND (lease_expires_at IS NULL OR lease_expires_at<=NOW(6))"""
            )
            cur.executemany(
                "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'recovered','worker','Worker 租约过期，任务已重新排队')",
                [(task_id,) for task_id in ids],
            )
        cur.execute(
            """SELECT id FROM graph_update_tasks WHERE status='applying' AND lease_token IS NOT NULL
               AND (lease_expires_at IS NULL OR lease_expires_at<=NOW(6)) FOR UPDATE"""
        )
        applying_ids = [int(row["id"]) for row in cur.fetchall()]
        if applying_ids:
            cur.execute(
                """UPDATE graph_update_tasks SET worker_id=NULL,lease_token=NULL,heartbeat_at=NULL,
                   lease_expires_at=NULL,
                   projection_next_retry_at=CASE WHEN neo4j_committed_at IS NOT NULL
                     AND projection_status='running' THEN NOW(6) ELSE projection_next_retry_at END,
                   projection_status=CASE WHEN neo4j_committed_at IS NOT NULL
                     AND projection_status='running' THEN 'retrying' ELSE projection_status END
                   WHERE status='applying' AND lease_token IS NOT NULL
                     AND (lease_expires_at IS NULL OR lease_expires_at<=NOW(6))"""
            )
            cur.executemany(
                "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'recovered','apply','提交或投影 worker 租约过期，任务等待重新处理')",
                [(task_id,) for task_id in applying_ids],
            )
        return len(ids) + len(applying_ids)


def recover_running_tasks() -> int:
    """Compatibility alias: recovery is lease-based rather than process-start based."""
    return recover_expired_tasks()


def claim_next_applying_task(*, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
    with db_cursor() as (_, cur):
        cur.execute(
            """SELECT * FROM graph_update_tasks WHERE status='applying'
               AND lease_token IS NULL
               AND (
                 neo4j_committed_at IS NULL
                 OR projection_status IN ('pending','running','retrying')
                    AND (projection_next_retry_at IS NULL OR projection_next_retry_at<=NOW(6))
               )
               ORDER BY confirm_requested_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"""
        )
        task = _decode(cur.fetchone(), include_change_set=True)
        if not task:
            return None
        lease_token = uuid4().hex
        cur.execute(
            """UPDATE graph_update_tasks SET worker_id=%s,lease_token=%s,heartbeat_at=NOW(6),
               lease_expires_at=DATE_ADD(NOW(6),INTERVAL %s SECOND)
               WHERE id=%s AND status='applying' AND lease_token IS NULL""",
            (worker_id[:128], lease_token, max(15, int(lease_seconds)), int(task["id"])),
        )
        if cur.rowcount != 1:
            return None
        task["worker_id"] = worker_id[:128]
        task["lease_token"] = lease_token
        task["files"] = _load_files(cur, int(task["id"]), include_paths=True)
        return task


def release_applying_lease(task_id: int, lease_token: str) -> bool:
    with db_cursor() as (_, cur):
        cur.execute(
            """UPDATE graph_update_tasks SET worker_id=NULL,lease_token=NULL,
               heartbeat_at=NULL,lease_expires_at=NULL
               WHERE id=%s AND status='applying' AND lease_token=%s""",
            (task_id, lease_token),
        )
        return cur.rowcount == 1


def prepare_task(task_id: int, *, base_revision: int, summary: dict[str, Any],
                 change_set_json: str, change_set_sha256: str,
                 lease_token: str | None = None) -> bool:
    with db_cursor() as (_, cur):
        guard = get_guard(for_update=True, cursor=cur)
        lease_clause = " AND lease_token=%s" if lease_token else ""
        lease_params = (lease_token,) if lease_token else ()
        if guard.get("locked_task_id") or int(guard["graph_revision"]) != int(base_revision):
            cur.execute(
                """UPDATE graph_update_tasks SET status='queued',worker_id=NULL,lease_token=NULL,
                   heartbeat_at=NULL,lease_expires_at=NULL,next_retry_at=NOW(6),
                   attempt_count=GREATEST(attempt_count-1,0)
                   WHERE id=%s AND status='running'""" + lease_clause,
                (task_id, *lease_params),
            )
            if cur.rowcount != 1:
                return False
            cur.execute(
                "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'requeued','revision','图谱版本变化，任务已重新排队')",
                (task_id,),
            )
            return False
        cur.execute(
            """UPDATE graph_update_tasks SET status='awaiting_confirmation',change_summary_json=%s,
               change_set_json=%s,change_set_sha256=%s,prepared_at=NOW(),worker_id=NULL,
               lease_token=NULL,heartbeat_at=NULL,lease_expires_at=NULL
               WHERE id=%s AND status='running'""" + lease_clause,
            (_json(summary), change_set_json, change_set_sha256, task_id, *lease_params),
        )
        if cur.rowcount != 1:
            return False
        cur.execute("UPDATE graph_write_guard SET locked_task_id=%s,locked_at=NOW() WHERE id=1", (task_id,))
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json) VALUES (%s,'prepared','confirmation','变更集已生成，等待管理员确认',%s)",
            (task_id, _json(summary)),
        )
        return True


def fail_or_retry_task(task_id: int, message: str, *, lease_token: str | None,
                       error_code: str, retryable: bool, max_attempts: int,
                       retry_delay_seconds: int) -> str:
    with db_cursor() as (_, cur):
        lease_clause = " AND lease_token=%s" if lease_token else ""
        lease_params = (lease_token,) if lease_token else ()
        cur.execute("SELECT attempt_count FROM graph_update_tasks WHERE id=%s AND status='running'" + lease_clause + " FOR UPDATE", (task_id, *lease_params))
        row = cur.fetchone()
        if not row:
            return "lost"
        should_retry = bool(retryable) and int(row.get("attempt_count") or 0) < max(1, int(max_attempts))
        status = "queued" if should_retry else "failed"
        cur.execute(
            """UPDATE graph_update_tasks SET status=%s,error_message=%s,last_error_code=%s,
               last_error_retryable=%s,worker_id=NULL,lease_token=NULL,heartbeat_at=NULL,
               lease_expires_at=NULL,finished_at=CASE WHEN %s THEN NULL ELSE NOW(6) END,
               next_retry_at=CASE WHEN %s THEN DATE_ADD(NOW(6),INTERVAL %s SECOND) ELSE NULL END
               WHERE id=%s AND status='running'""" + lease_clause,
            (status, message[:65000], error_code[:80], bool(retryable), should_retry,
             should_retry, max(1, int(retry_delay_seconds)), task_id, *lease_params),
        )
        if cur.rowcount != 1:
            return "lost"
        cur.execute("UPDATE graph_write_guard SET locked_task_id=NULL,locked_at=NULL WHERE id=1 AND locked_task_id=%s", (task_id,))
        event = "retry_scheduled" if should_retry else "failed"
        event_message = (f"临时错误，将在 {max(1, int(retry_delay_seconds))} 秒后重试: {message}" if should_retry else message)
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json) VALUES (%s,%s,'worker',%s,%s)",
                    (task_id, event, event_message[:500], _json({"error_code": error_code, "retryable": bool(retryable), "attempt_count": int(row.get("attempt_count") or 0)})))
        return status


def fail_task(task_id: int, message: str, *, lease_token: str | None = None) -> None:
    fail_or_retry_task(task_id, message, lease_token=lease_token, error_code="unclassified",
                       retryable=False, max_attempts=1, retry_delay_seconds=1)


def requeue_task(task_id: int, message: str, *, lease_token: str | None = None) -> None:
    with db_cursor() as (_, cur):
        lease_clause = " AND lease_token=%s" if lease_token else ""
        lease_params = (lease_token,) if lease_token else ()
        cur.execute(
            """UPDATE graph_update_tasks SET status='queued',worker_id=NULL,lease_token=NULL,
               heartbeat_at=NULL,lease_expires_at=NULL,next_retry_at=NOW(6),
               attempt_count=GREATEST(attempt_count-1,0)
               WHERE id=%s AND status='running'""" + lease_clause,
            (task_id, *lease_params),
        )
        if cur.rowcount != 1:
            return
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'requeued','lock',%s)", (task_id, message[:500]))


def list_tasks(*, page: int, page_size: int, status: str | None = None,
               task_type: str | None = None, requested_by: int | None = None,
               created_from: str | None = None, created_to: str | None = None) -> dict[str, Any]:
    clauses, params = [], []
    if status:
        clauses.append("status=%s"); params.append(status)
    if task_type:
        clauses.append("task_type=%s"); params.append(task_type)
    if requested_by is not None:
        clauses.append("requested_by=%s"); params.append(requested_by)
    if created_from:
        clauses.append("created_at>=%s"); params.append(created_from)
    if created_to:
        clauses.append("created_at<=%s"); params.append(created_to)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with db_cursor() as (_, cur):
        cur.execute("SELECT COUNT(*) AS total FROM graph_update_tasks" + where, params)
        total = int(cur.fetchone()["total"])
        cur.execute(
            "SELECT id,task_uuid,task_type,status,requested_by,handled_by,input_file_name,input_file_size,input_sha256,source_id,mode,options_json,settings_revision,base_graph_revision,change_summary_json,change_set_sha256,error_message,rejection_reason,worker_id,heartbeat_at,lease_expires_at,attempt_count,next_retry_at,last_error_code,last_error_retryable,confirm_requested_at,neo4j_committed_at,projection_status,projection_attempts,projection_error,projection_next_retry_at,created_at,started_at,prepared_at,handled_at,finished_at FROM graph_update_tasks" + where + " ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
            (*params, page_size, (page - 1) * page_size),
        )
        items = [_decode(r) for r in cur.fetchall()]
        for item in items:
            item["files"] = _load_files(cur, int(item["id"]))
        return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_task(task_id: int, *, include_change_set: bool = False) -> dict[str, Any] | None:
    with db_cursor() as (_, cur):
        columns = "*" if include_change_set else "id,task_uuid,task_type,status,requested_by,handled_by,input_file_name,input_file_size,input_sha256,source_id,mode,options_json,settings_revision,config_snapshot_json,base_graph_revision,change_summary_json,change_set_sha256,error_message,rejection_reason,worker_id,heartbeat_at,lease_expires_at,attempt_count,next_retry_at,last_error_code,last_error_retryable,confirm_requested_at,neo4j_committed_at,projection_status,projection_attempts,projection_error,projection_next_retry_at,created_at,started_at,prepared_at,handled_at,finished_at"
        cur.execute(f"SELECT {columns} FROM graph_update_tasks WHERE id=%s", (task_id,))
        task = _decode(cur.fetchone(), include_change_set=include_change_set)
        if not task:
            return None
        task["files"] = _load_files(cur, task_id, include_paths=include_change_set)
        cur.execute("SELECT id,event_type,stage,message,detail_json,created_at FROM graph_update_task_events WHERE task_id=%s ORDER BY id", (task_id,))
        events = []
        for row in cur.fetchall():
            event = dict(row); raw = event.pop("detail_json", None)
            event["detail"] = json.loads(raw) if isinstance(raw, str) else raw; events.append(event)
        task["events"] = events
        return task


def get_task_file(task_id: int, role: str) -> dict[str, Any] | None:
    """Return private file metadata for an authenticated download request."""
    with db_cursor() as (_, cur):
        cur.execute(
            """SELECT id,task_id,role,original_name,private_path,size,sha256,media_type,created_at
               FROM graph_update_task_files WHERE task_id=%s AND role=%s""",
            (task_id, role),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def task_changes(task_id: int, *, group: str | None, page: int, page_size: int) -> dict[str, Any] | None:
    task = get_task(task_id, include_change_set=True)
    if not task:
        return None
    change = task.get("change_set") or {}
    groups = {key: value for key, value in change.items() if isinstance(value, list)}
    for manifest_name in ("delete_manifest", "retained_manifest"):
        manifest = change.get(manifest_name)
        if not isinstance(manifest, dict):
            continue
        prefix = "delete" if manifest_name == "delete_manifest" else "retained"
        for key, value in manifest.items():
            if isinstance(value, list):
                groups[f"{prefix}.{key}"] = value
    selected = group if group in groups else (next(iter(groups), None) if not group else None)
    rows = groups.get(selected, []) if selected else []
    start = (page - 1) * page_size
    return {"group": selected, "groups": {key: len(value) for key, value in groups.items()},
            "items": rows[start:start + page_size], "total": len(rows),
            "page": page, "page_size": page_size}


def clear_task_file_paths(task_id: int) -> None:
    with db_cursor() as (_, cur):
        cur.execute("UPDATE graph_update_task_files SET private_path=NULL WHERE task_id=%s", (task_id,))


def set_applying(task_id: int, user_id: int, *, expected_sha256: str | None = None) -> dict[str, Any] | None:
    with db_cursor() as (_, cur):
        guard = get_guard(for_update=True, cursor=cur)
        if int(guard.get("locked_task_id") or 0) != task_id:
            return None
        cur.execute("SELECT * FROM graph_update_tasks WHERE id=%s FOR UPDATE", (task_id,))
        task = _decode(cur.fetchone(), include_change_set=True)
        if not task or task["status"] != "awaiting_confirmation":
            return None
        base_revision = task.get("base_graph_revision")
        if base_revision is None or int(base_revision) != int(guard.get("graph_revision") or 0):
            return None
        if expected_sha256 and task.get("change_set_sha256") != expected_sha256:
            return None
        cur.execute(
            """UPDATE graph_update_tasks SET status='applying',handled_by=%s,handled_at=NOW(6),
               confirm_requested_at=NOW(6),projection_status='waiting_for_graph',
               projection_attempts=0,projection_error=NULL,projection_next_retry_at=NULL
               WHERE id=%s AND status='awaiting_confirmation'""",
            (user_id, task_id),
        )
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'confirmation_requested','confirmation','管理员已确认，等待 worker 提交图谱')",
            (task_id,),
        )
        task["status"] = "applying"
        task["handled_by"] = user_id
        return task


def mark_neo4j_committed(task_id: int, *, lease_token: str) -> bool:
    """Record the cross-store commit fact and advance revision exactly once."""
    with db_cursor() as (_, cur):
        cur.execute("SELECT task_type,status,neo4j_committed_at FROM graph_update_tasks WHERE id=%s AND lease_token=%s FOR UPDATE", (task_id, lease_token))
        task = cur.fetchone()
        if not task or task["status"] != "applying":
            return False
        if task.get("neo4j_committed_at") is not None:
            return True
        guard = get_guard(for_update=True, cursor=cur)
        if int(guard.get("locked_task_id") or 0) != task_id:
            raise RuntimeError("Neo4j 已提交但 graph_write_guard 不属于当前任务")
        projection = "pending" if task["task_type"] == "job_import" else "not_required"
        cur.execute(
            """UPDATE graph_update_tasks SET neo4j_committed_at=NOW(6),projection_status=%s,
               projection_error=NULL,projection_next_retry_at=NULL WHERE id=%s AND neo4j_committed_at IS NULL""",
            (projection, task_id),
        )
        if cur.rowcount != 1:
            return False
        cur.execute(
            """UPDATE graph_write_guard SET graph_revision=graph_revision+1,
               locked_task_id=NULL,locked_at=NULL WHERE id=1 AND locked_task_id=%s""",
            (task_id,),
        )
        if cur.rowcount != 1:
            raise RuntimeError("提交图谱版本失败")
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'neo4j_committed','apply','Neo4j 事务已提交，图谱版本已递增')",
            (task_id,),
        )
        return True


def start_projection(task_id: int, *, lease_token: str) -> bool:
    with db_cursor() as (_, cur):
        cur.execute(
            """UPDATE graph_update_tasks SET projection_status='running',
               projection_attempts=projection_attempts+1,projection_next_retry_at=NULL
               WHERE id=%s AND status='applying' AND neo4j_committed_at IS NOT NULL
               AND projection_status IN ('pending','running','retrying') AND lease_token=%s""",
            (task_id, lease_token),
        )
        return cur.rowcount == 1


def schedule_projection_retry(task_id: int, error: str, *, lease_token: str,
                              retry_delay_seconds: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute(
            """UPDATE graph_update_tasks SET projection_status='retrying',projection_error=%s,
               projection_next_retry_at=DATE_ADD(NOW(6),INTERVAL %s SECOND),
               worker_id=NULL,lease_token=NULL,heartbeat_at=NULL,lease_expires_at=NULL
               WHERE id=%s AND status='applying' AND neo4j_committed_at IS NOT NULL
                 AND lease_token=%s""",
            (error[:65000], max(1, int(retry_delay_seconds)), task_id, lease_token),
        )
        if cur.rowcount != 1:
            return False
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'projection_retry','projection',%s)",
            (task_id, f"MySQL 投影同步失败，将自动重试: {error}"[:500]),
        )
        return True


def finish_projection(task_id: int, *, lease_token: str, required: bool) -> bool:
    with db_cursor() as (_, cur):
        final_projection = "succeeded" if required else "not_required"
        cur.execute(
            """UPDATE graph_update_tasks SET status='succeeded',projection_status=%s,
               projection_error=NULL,projection_next_retry_at=NULL,error_message=NULL,finished_at=NOW(6),
               worker_id=NULL,lease_token=NULL,heartbeat_at=NULL,lease_expires_at=NULL
               WHERE id=%s AND status='applying' AND neo4j_committed_at IS NOT NULL
                 AND lease_token=%s""",
            (final_projection, task_id, lease_token),
        )
        if cur.rowcount != 1:
            return False
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'succeeded','projection',%s)",
            (task_id, "MySQL 派生投影已同步" if required else "图谱变更已提交"),
        )
        return True


def fail_apply(task_id: int, error: str, *, lease_token: str) -> bool:
    """Fail an apply attempt only when no Neo4j commit marker has been recorded."""
    with db_cursor() as (_, cur):
        cur.execute(
            """UPDATE graph_update_tasks SET status='failed',error_message=%s,finished_at=NOW(6),
               worker_id=NULL,lease_token=NULL,heartbeat_at=NULL,lease_expires_at=NULL
               WHERE id=%s AND status='applying' AND neo4j_committed_at IS NULL
                 AND lease_token=%s""",
            (error[:65000], task_id, lease_token),
        )
        if cur.rowcount != 1:
            return False
        cur.execute("UPDATE graph_write_guard SET locked_task_id=NULL,locked_at=NULL WHERE id=1 AND locked_task_id=%s", (task_id,))
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'failed','apply',%s)", (task_id, error[:500]))
        return True


def reject_task(task_id: int, user_id: int, reason: str) -> bool:
    with db_cursor() as (_, cur):
        guard = get_guard(for_update=True, cursor=cur)
        if int(guard.get("locked_task_id") or 0) != task_id:
            return False
        cur.execute("UPDATE graph_update_tasks SET status='rejected',handled_by=%s,rejection_reason=%s,change_set_json=NULL,input_file_path=NULL,handled_at=NOW(),finished_at=NOW() WHERE id=%s AND status='awaiting_confirmation'", (user_id, reason, task_id))
        if cur.rowcount != 1:
            return False
        cur.execute("UPDATE graph_write_guard SET locked_task_id=NULL,locked_at=NULL WHERE id=1")
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'rejected','confirmation',%s)", (task_id, reason[:500]))
        return True


def cancel_task(task_id: int, user_id: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute("UPDATE graph_update_tasks SET status='cancelled',handled_by=%s,handled_at=NOW(),finished_at=NOW(),input_file_path=NULL WHERE id=%s AND status='queued'", (user_id, task_id))
        if cur.rowcount != 1:
            return False
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'cancelled','queue','排队任务已取消')", (task_id,))
        return True
