"""MySQL persistence and state transitions for graph update tasks."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from app.db import db_cursor
from app.domains.graph.change_storage import ChangeChunk, verify_chunk_rows

FINAL_STATUSES = {"succeeded", "partial_failed", "failed", "rejected", "cancelled"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode(row: dict[str, Any] | None, *, include_change_set: bool = False):
    if not row:
        return None
    item = dict(row)
    for key in ("options_json", "change_summary_json", "config_snapshot_json", "change_manifest_json"):
        if key not in item:
            continue
        raw = item.pop(key, None)
        item[key.removesuffix("_json")] = json.loads(raw) if isinstance(raw, str) else raw
    raw_inverse = item.pop("inverse_manifest_json", None)
    item["inverse_available"] = bool(item.get("inverse_available") or (raw_inverse and item.get("inverse_sha256")))
    raw_change = item.pop("change_set_json", None)
    if include_change_set:
        if int(item.get("change_storage_version") or 1) >= 2:
            item["change_set"] = item.get("change_manifest") or {}
        else:
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
                 change_set_sha256: str, change_manifest: dict[str, Any] | None = None,
                 change_chunks: tuple[ChangeChunk, ...] = (), change_set_json: str | None = None,
                 inverse_manifest: dict[str, Any] | None = None,
                 inverse_chunks: tuple[ChangeChunk, ...] = (), inverse_sha256: str | None = None,
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
        storage_version = 2 if change_manifest is not None else 1
        cur.execute(
            """UPDATE graph_update_tasks SET status='awaiting_confirmation',change_summary_json=%s,
               change_set_json=%s,change_manifest_json=%s,change_storage_version=%s,
               change_set_sha256=%s,inverse_manifest_json=%s,inverse_sha256=%s,
               prepared_at=NOW(),worker_id=NULL,
               lease_token=NULL,heartbeat_at=NULL,lease_expires_at=NULL
               WHERE id=%s AND status='running'""" + lease_clause,
            (_json(summary), change_set_json, _json(change_manifest) if change_manifest is not None else None,
             storage_version, change_set_sha256,
             _json(inverse_manifest) if inverse_manifest is not None else None,
             inverse_sha256, task_id, *lease_params),
        )
        if cur.rowcount != 1:
            return False
        cur.execute("DELETE FROM graph_update_task_change_chunks WHERE task_id=%s", (task_id,))
        if change_chunks:
            cur.executemany(
                """INSERT INTO graph_update_task_change_chunks
                   (task_id,group_name,chunk_no,item_count,chunk_sha256,payload_json)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                [(task_id, chunk.group_name, chunk.chunk_no, chunk.item_count,
                  chunk.sha256, chunk.payload_json) for chunk in change_chunks],
            )
        cur.execute("DELETE FROM graph_update_task_inverse_chunks WHERE task_id=%s", (task_id,))
        if inverse_chunks:
            cur.executemany(
                """INSERT INTO graph_update_task_inverse_chunks
                   (task_id,group_name,chunk_no,item_count,chunk_sha256,payload_json)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                [(task_id, chunk.group_name, chunk.chunk_no, chunk.item_count,
                  chunk.sha256, chunk.payload_json) for chunk in inverse_chunks],
            )
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
            "SELECT id,task_uuid,task_type,status,requested_by,handled_by,input_file_name,input_file_size,input_sha256,source_id,mode,options_json,settings_revision,base_graph_revision,change_summary_json,change_set_sha256,change_storage_version,inverse_sha256,inverse_of_task_id,(inverse_manifest_json IS NOT NULL) AS inverse_available,error_message,rejection_reason,worker_id,heartbeat_at,lease_expires_at,attempt_count,next_retry_at,last_error_code,last_error_retryable,confirm_requested_at,neo4j_committed_at,projection_status,projection_attempts,projection_error,projection_next_retry_at,created_at,started_at,prepared_at,handled_at,finished_at FROM graph_update_tasks" + where + " ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
            (*params, page_size, (page - 1) * page_size),
        )
        items = [_decode(r) for r in cur.fetchall()]
        for item in items:
            item["files"] = _load_files(cur, int(item["id"]))
        return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_task(task_id: int, *, include_change_set: bool = False) -> dict[str, Any] | None:
    with db_cursor() as (_, cur):
        # Public task details intentionally omit the frozen settings document.  The
        # revision is enough for audit display; only worker/confirm internals may
        # load the complete snapshot via include_change_set=True.
        columns = "*" if include_change_set else "id,task_uuid,task_type,status,requested_by,handled_by,input_file_name,input_file_size,input_sha256,source_id,mode,options_json,settings_revision,base_graph_revision,change_summary_json,change_set_sha256,change_storage_version,inverse_sha256,inverse_of_task_id,(inverse_manifest_json IS NOT NULL) AS inverse_available,error_message,rejection_reason,worker_id,heartbeat_at,lease_expires_at,attempt_count,next_retry_at,last_error_code,last_error_retryable,confirm_requested_at,neo4j_committed_at,projection_status,projection_attempts,projection_error,projection_next_retry_at,created_at,started_at,prepared_at,handled_at,finished_at"
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
    with db_cursor() as (_, cur):
        cur.execute("SELECT change_storage_version FROM graph_update_tasks WHERE id=%s", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            return None
        if int(task_row.get("change_storage_version") or 1) < 2:
            return _legacy_task_changes(task_id, group=group, page=page, page_size=page_size)
        cur.execute(
            """SELECT group_name,SUM(item_count) AS total,MIN(id) AS first_id
               FROM graph_update_task_change_chunks WHERE task_id=%s
               GROUP BY group_name ORDER BY first_id""",
            (task_id,),
        )
        group_rows = list(cur.fetchall())
        groups = {str(row["group_name"]): int(row["total"] or 0) for row in group_rows}
        selected = group if group in groups else (next(iter(groups), None) if not group else None)
        total = groups.get(selected, 0) if selected else 0
        items: list[Any] = []
        start = (page - 1) * page_size
        end = min(start + page_size, total)
        if selected and start < total:
            cur.execute(
                """SELECT payload_json,item_count,offset_before FROM (
                     SELECT payload_json,item_count,chunk_no,
                       COALESCE(SUM(item_count) OVER (
                         ORDER BY chunk_no ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                       ),0) AS offset_before
                     FROM graph_update_task_change_chunks
                     WHERE task_id=%s AND group_name=%s
                   ) AS chunks
                   WHERE offset_before < %s AND offset_before + item_count > %s
                   ORDER BY chunk_no""",
                (task_id, selected, end, start),
            )
            for row in cur.fetchall():
                chunk = json.loads(row["payload_json"])
                offset = int(row["offset_before"])
                items.extend(chunk[max(0, start - offset):max(0, end - offset)])
        return {"group": selected, "groups": groups, "items": items, "total": total,
                "page": page, "page_size": page_size}


def _legacy_task_changes(task_id: int, *, group: str | None, page: int, page_size: int) -> dict[str, Any] | None:
    task = get_task(task_id, include_change_set=True)
    if not task:
        return None
    change = task.get("change_set") or {}
    groups = {key: value for key, value in change.items() if isinstance(value, list)}
    for manifest_name, prefix in (("delete_manifest", "delete"), ("retained_manifest", "retained")):
        manifest = change.get(manifest_name)
        if isinstance(manifest, dict):
            groups.update({f"{prefix}.{key}": value for key, value in manifest.items() if isinstance(value, list)})
    selected = group if group in groups else (next(iter(groups), None) if not group else None)
    rows = groups.get(selected, []) if selected else []
    start = (page - 1) * page_size
    return {"group": selected, "groups": {key: len(value) for key, value in groups.items()},
            "items": rows[start:start + page_size], "total": len(rows),
            "page": page, "page_size": page_size}


def verify_task_change_set(task_id: int, *, expected_sha256: str | None = None) -> bool:
    """Verify either a legacy LONGTEXT document or every stored chunk without rebuilding it."""
    with db_cursor() as (_, cur):
        cur.execute(
            """SELECT change_storage_version,change_manifest_json,change_set_json,change_set_sha256
               FROM graph_update_tasks WHERE id=%s""",
            (task_id,),
        )
        row = cur.fetchone()
        if not row:
            return False
        stored_sha = str(row.get("change_set_sha256") or "")
        if expected_sha256 and stored_sha != expected_sha256:
            return False
        if int(row.get("change_storage_version") or 1) < 2:
            raw = row.get("change_set_json")
            if not isinstance(raw, str):
                return False
            try:
                canonical = _json(json.loads(raw))
                # Legacy digests were generated with sorted keys.
                canonical = json.dumps(json.loads(canonical), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            except (TypeError, json.JSONDecodeError):
                return False
            import hashlib
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest() == stored_sha
        raw_manifest = row.get("change_manifest_json")
        try:
            manifest = json.loads(raw_manifest) if isinstance(raw_manifest, str) else None
        except json.JSONDecodeError:
            return False
        if not isinstance(manifest, dict):
            return False
        cur.execute(
            """SELECT group_name,chunk_no,item_count,chunk_sha256,payload_json
               FROM graph_update_task_change_chunks WHERE task_id=%s
               ORDER BY group_name,chunk_no""",
            (task_id,),
        )
        return verify_chunk_rows(manifest, cur, stored_sha)


def iter_change_group_chunks(task_id: int, group_name: str) -> Iterator[list[Any]]:
    with db_cursor() as (_, cur):
        cur.execute(
            """SELECT payload_json FROM graph_update_task_change_chunks
               WHERE task_id=%s AND group_name=%s ORDER BY chunk_no""",
            (task_id, group_name),
        )
        while True:
            row = cur.fetchone()
            if not row:
                break
            items = json.loads(row["payload_json"])
            if not isinstance(items, list):
                raise RuntimeError(f"变更分块 {group_name} 格式无效")
            yield items


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
        cur.execute("""UPDATE graph_update_tasks SET status='rejected',handled_by=%s,
          rejection_reason=%s,change_set_json=NULL,change_manifest_json=NULL,input_file_path=NULL,
          handled_at=NOW(),finished_at=NOW() WHERE id=%s AND status='awaiting_confirmation'""",
          (user_id, reason, task_id))
        if cur.rowcount != 1:
            return False
        cur.execute("DELETE FROM graph_update_task_change_chunks WHERE task_id=%s", (task_id,))
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


def touch_worker(worker_id: str, *, current_task_id: int | None = None) -> None:
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                """INSERT INTO graph_worker_heartbeats (worker_id,current_task_id)
                   VALUES (%s,%s) ON DUPLICATE KEY UPDATE current_task_id=VALUES(current_task_id),
                     last_heartbeat_at=NOW(6)""",
                (worker_id[:128], current_task_id),
            )
    except Exception:
        return


def operational_metrics() -> dict[str, Any]:
    """Return bounded aggregate metrics; never expose prompts, keys, or snapshots."""
    with db_cursor() as (_, cur):
        cur.execute(
            """SELECT
              SUM(status='queued') AS queue_depth,
              COALESCE(MAX(CASE WHEN status='queued' THEN TIMESTAMPDIFF(SECOND,created_at,NOW(6)) END),0) AS oldest_queue_seconds,
              COALESCE(AVG(CASE WHEN started_at IS NOT NULL THEN TIMESTAMPDIFF(SECOND,created_at,started_at) END),0) AS queue_wait_avg_seconds,
              SUM(status='applying' AND projection_status IN ('pending','running','retrying')) AS projection_backlog,
              SUM(status='failed' AND created_at>=DATE_SUB(NOW(6),INTERVAL 7 DAY)) AS failed_7d,
              SUM(status IN ('succeeded','failed','partial_failed') AND created_at>=DATE_SUB(NOW(6),INTERVAL 7 DAY)) AS completed_7d
            FROM graph_update_tasks"""
        )
        task = dict(cur.fetchone() or {})
        cur.execute(
            """SELECT COUNT(*) AS active_workers,
              COALESCE(MAX(TIMESTAMPDIFF(SECOND,last_heartbeat_at,NOW(6))),0) AS worker_heartbeat_age_seconds
              FROM graph_worker_heartbeats
              WHERE last_heartbeat_at>=DATE_SUB(NOW(6),INTERVAL 5 MINUTE)"""
        )
        workers = dict(cur.fetchone() or {})
        cur.execute(
            """SELECT COUNT(*) AS llm_calls,
              COALESCE(SUM(prompt_tokens+completion_tokens),0) AS llm_total_tokens,
              COALESCE(SUM(duration_ms),0) AS llm_duration_ms,
              COALESCE(SUM(cache_hit),0) AS llm_cache_hits,
              COALESCE(SUM(retry_count),0) AS llm_retries
              FROM graph_llm_call_metrics
              WHERE created_at>=DATE_SUB(NOW(6),INTERVAL 7 DAY)"""
        )
        llm = dict(cur.fetchone() or {})
        cur.execute(
            """SELECT COALESCE(TIMESTAMPDIFF(SECOND,locked_at,NOW(6)),0) AS graph_lock_seconds
               FROM graph_write_guard WHERE id=1"""
        )
        lock = dict(cur.fetchone() or {})
    completed = int(task.get("completed_7d") or 0)
    failed = int(task.get("failed_7d") or 0)
    values = {**task, **workers, **llm, **lock, "failure_rate_7d": round(failed / completed, 4) if completed else 0.0}
    return {key: float(value) if key in {"queue_wait_avg_seconds", "failure_rate_7d"} else int(value or 0) for key, value in values.items()}


def create_inverse_task(
    source_task_id: int, *, requested_by: int, settings_revision: int | None,
    config_snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    """Copy a stored inverse into a new reviewed task and acquire the guard."""
    with db_cursor() as (_, cur):
        guard = get_guard(for_update=True, cursor=cur)
        if guard.get("locked_task_id"):
            return None
        cur.execute(
            """SELECT id,status,task_type,base_graph_revision,inverse_manifest_json,inverse_sha256
               FROM graph_update_tasks WHERE id=%s FOR UPDATE""",
            (source_task_id,),
        )
        source = cur.fetchone()
        if not source or source.get("status") != "succeeded" or not source.get("inverse_manifest_json") or not source.get("inverse_sha256"):
            return None
        if int(guard.get("graph_revision") or 0) != int(source.get("base_graph_revision") or -2) + 1:
            return None
        cur.execute(
            """SELECT 1 FROM graph_update_tasks WHERE inverse_of_task_id=%s
               AND status NOT IN ('rejected','cancelled','failed') LIMIT 1 FOR UPDATE""",
            (source_task_id,),
        )
        if cur.fetchone():
            return None
        cur.execute(
            """SELECT 1 FROM graph_update_tasks
               WHERE status IN ('running','awaiting_confirmation','applying') LIMIT 1 FOR UPDATE"""
        )
        if cur.fetchone():
            return None
        try:
            manifest = json.loads(source["inverse_manifest_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        cur.execute(
            """SELECT group_name,chunk_no,item_count,chunk_sha256,payload_json
               FROM graph_update_task_inverse_chunks WHERE task_id=%s
               ORDER BY group_name,chunk_no""",
            (source_task_id,),
        )
        inverse_rows = [dict(row) for row in cur.fetchall()]
        if not verify_chunk_rows(manifest, inverse_rows, str(source["inverse_sha256"])):
            return None
        restored = sum(int(row["item_count"]) for row in inverse_rows if row["group_name"] == "jobs")
        summary = {"inverse_of_task_id": source_task_id, "inverse_of_type": source["task_type"], "restored_jobs": restored}
        task_uuid = uuid4().hex
        cur.execute(
            """INSERT INTO graph_update_tasks
               (task_uuid,task_type,status,requested_by,mode,options_json,settings_revision,
                config_snapshot_json,base_graph_revision,change_summary_json,change_manifest_json,
                change_storage_version,change_set_sha256,inverse_of_task_id,prepared_at)
               VALUES (%s,'graph_inverse','awaiting_confirmation',%s,'merge',%s,%s,%s,%s,%s,%s,2,%s,%s,NOW(6))""",
            (task_uuid, requested_by, _json({"inverse_of_task_id": source_task_id}),
             settings_revision, _json(config_snapshot), int(guard["graph_revision"]),
             _json(summary), _json(manifest), source["inverse_sha256"], source_task_id),
        )
        task_id = int(cur.lastrowid)
        if inverse_rows:
            cur.executemany(
                """INSERT INTO graph_update_task_change_chunks
                   (task_id,group_name,chunk_no,item_count,chunk_sha256,payload_json)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                [(task_id, row["group_name"], row["chunk_no"], row["item_count"],
                  row["chunk_sha256"], row["payload_json"]) for row in inverse_rows],
            )
        cur.execute("UPDATE graph_write_guard SET locked_task_id=%s,locked_at=NOW(6) WHERE id=1", (task_id,))
        cur.execute(
            """INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json)
               VALUES (%s,'prepared','inverse','已从历史任务生成反向变更，等待管理员确认',%s)""",
            (task_id, _json(summary)),
        )
        cur.execute("SELECT * FROM graph_update_tasks WHERE id=%s", (task_id,))
        return _decode(cur.fetchone())
