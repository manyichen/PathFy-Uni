"""MySQL persistence and state transitions for graph update tasks."""

from __future__ import annotations

import json
from typing import Any

from app.db import db_cursor

FINAL_STATUSES = {"succeeded", "partial_failed", "failed", "rejected", "cancelled"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode(row: dict[str, Any] | None, *, include_change_set: bool = False):
    if not row:
        return None
    item = dict(row)
    for key in ("options_json", "change_summary_json"):
        raw = item.pop(key, None)
        item[key.removesuffix("_json")] = json.loads(raw) if isinstance(raw, str) else raw
    raw_change = item.pop("change_set_json", None)
    if include_change_set:
        item["change_set"] = json.loads(raw_change) if isinstance(raw_change, str) else raw_change
    return item


def create_task(*, task_uuid: str, task_type: str, requested_by: int, file_name: str,
                file_path: str, file_size: int, sha256: str, source_id: str | None,
                mode: str, options: dict[str, Any]) -> dict[str, Any]:
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO graph_update_tasks
              (task_uuid, task_type, requested_by, input_file_name, input_file_path,
               input_file_size, input_sha256, source_id, mode, options_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (task_uuid, task_type, requested_by, file_name, file_path, file_size,
             sha256, source_id, mode, _json(options)),
        )
        task_id = cur.lastrowid
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json) VALUES (%s,'queued','queue','任务已进入队列',%s)",
            (task_id, _json({"task_type": task_type})),
        )
        cur.execute("SELECT * FROM graph_update_tasks WHERE id=%s", (task_id,))
        return _decode(cur.fetchone())


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


def claim_next_task() -> dict[str, Any] | None:
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
            "SELECT id FROM graph_update_tasks WHERE status='queued' ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
        row = cur.fetchone()
        if not row:
            return None
        task_id = int(row["id"])
        cur.execute(
            "UPDATE graph_update_tasks SET status='running',started_at=NOW(),base_graph_revision=%s WHERE id=%s AND status='queued'",
            (guard["graph_revision"], task_id),
        )
        cur.execute("SELECT * FROM graph_update_tasks WHERE id=%s", (task_id,))
        task = _decode(cur.fetchone(), include_change_set=True)
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'started','worker','Worker 开始生成变更集')",
            (task_id,),
        )
        return task


def recover_running_tasks() -> int:
    """Requeue work left running by a terminated single worker process."""
    with db_cursor() as (_, cur):
        cur.execute("SELECT id FROM graph_update_tasks WHERE status='running' FOR UPDATE")
        ids = [int(row["id"]) for row in cur.fetchall()]
        if ids:
            cur.execute("UPDATE graph_update_tasks SET status='queued',started_at=NULL WHERE status='running'")
            cur.executemany(
                "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'recovered','worker','Worker 重启，遗留任务已重新排队')",
                [(task_id,) for task_id in ids],
            )
        return len(ids)


def get_applying_tasks() -> list[dict[str, Any]]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT * FROM graph_update_tasks WHERE status='applying'")
        return [_decode(row, include_change_set=True) for row in cur.fetchall()]


def reset_applying_task(task_id: int) -> None:
    with db_cursor() as (_, cur):
        cur.execute("UPDATE graph_update_tasks SET status='awaiting_confirmation',handled_by=NULL,handled_at=NULL WHERE id=%s AND status='applying'", (task_id,))
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'recovered','confirmation','未发现 Neo4j 提交标记，任务已恢复为待确认')", (task_id,))


def prepare_task(task_id: int, *, base_revision: int, summary: dict[str, Any],
                 change_set_json: str, change_set_sha256: str) -> bool:
    with db_cursor() as (_, cur):
        guard = get_guard(for_update=True, cursor=cur)
        if guard.get("locked_task_id") or int(guard["graph_revision"]) != int(base_revision):
            cur.execute("UPDATE graph_update_tasks SET status='queued',started_at=NULL WHERE id=%s AND status='running'", (task_id,))
            cur.execute(
                "INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'requeued','revision','图谱版本变化，任务已重新排队')",
                (task_id,),
            )
            return False
        cur.execute(
            """UPDATE graph_update_tasks SET status='awaiting_confirmation',change_summary_json=%s,
               change_set_json=%s,change_set_sha256=%s,prepared_at=NOW() WHERE id=%s AND status='running'""",
            (_json(summary), change_set_json, change_set_sha256, task_id),
        )
        if cur.rowcount != 1:
            return False
        cur.execute("UPDATE graph_write_guard SET locked_task_id=%s,locked_at=NOW() WHERE id=1", (task_id,))
        cur.execute(
            "INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json) VALUES (%s,'prepared','confirmation','变更集已生成，等待管理员确认',%s)",
            (task_id, _json(summary)),
        )
        return True


def fail_task(task_id: int, message: str) -> None:
    with db_cursor() as (_, cur):
        cur.execute("UPDATE graph_update_tasks SET status='failed',error_message=%s,finished_at=NOW() WHERE id=%s", (message[:65000], task_id))
        cur.execute("UPDATE graph_write_guard SET locked_task_id=NULL,locked_at=NULL WHERE id=1 AND locked_task_id=%s", (task_id,))
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'failed','worker',%s)", (task_id, message[:500]))


def requeue_task(task_id: int, message: str) -> None:
    with db_cursor() as (_, cur):
        cur.execute("UPDATE graph_update_tasks SET status='queued',started_at=NULL WHERE id=%s AND status='running'", (task_id,))
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,'requeued','lock',%s)", (task_id, message[:500]))


def list_tasks(*, page: int, page_size: int, status: str | None = None,
               task_type: str | None = None) -> dict[str, Any]:
    clauses, params = [], []
    if status:
        clauses.append("status=%s"); params.append(status)
    if task_type:
        clauses.append("task_type=%s"); params.append(task_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with db_cursor() as (_, cur):
        cur.execute("SELECT COUNT(*) AS total FROM graph_update_tasks" + where, params)
        total = int(cur.fetchone()["total"])
        cur.execute(
            "SELECT * FROM graph_update_tasks" + where + " ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
            (*params, page_size, (page - 1) * page_size),
        )
        return {"items": [_decode(r) for r in cur.fetchall()], "total": total, "page": page, "page_size": page_size}


def get_task(task_id: int, *, include_change_set: bool = False) -> dict[str, Any] | None:
    with db_cursor() as (_, cur):
        columns = "*" if include_change_set else "id,task_uuid,task_type,status,requested_by,handled_by,input_file_name,input_file_size,input_sha256,source_id,mode,options_json,base_graph_revision,change_summary_json,change_set_sha256,error_message,rejection_reason,created_at,started_at,prepared_at,handled_at,finished_at"
        cur.execute(f"SELECT {columns} FROM graph_update_tasks WHERE id=%s", (task_id,))
        task = _decode(cur.fetchone(), include_change_set=include_change_set)
        if not task:
            return None
        cur.execute("SELECT id,event_type,stage,message,detail_json,created_at FROM graph_update_task_events WHERE task_id=%s ORDER BY id", (task_id,))
        events = []
        for row in cur.fetchall():
            event = dict(row); raw = event.pop("detail_json", None)
            event["detail"] = json.loads(raw) if isinstance(raw, str) else raw; events.append(event)
        task["events"] = events
        return task


def set_applying(task_id: int, user_id: int) -> dict[str, Any] | None:
    with db_cursor() as (_, cur):
        guard = get_guard(for_update=True, cursor=cur)
        if int(guard.get("locked_task_id") or 0) != task_id:
            return None
        cur.execute("SELECT * FROM graph_update_tasks WHERE id=%s FOR UPDATE", (task_id,))
        task = _decode(cur.fetchone(), include_change_set=True)
        if not task or task["status"] != "awaiting_confirmation":
            return None
        cur.execute("UPDATE graph_update_tasks SET status='applying',handled_by=%s,handled_at=NOW() WHERE id=%s", (user_id, task_id))
        return task


def finish_apply(task_id: int, *, success: bool, error: str | None = None, partial: bool = False) -> None:
    with db_cursor() as (_, cur):
        status = "partial_failed" if partial else ("succeeded" if success else "failed")
        cur.execute("UPDATE graph_update_tasks SET status=%s,error_message=%s,input_file_path=NULL,finished_at=NOW() WHERE id=%s", (status, error, task_id))
        if success:
            cur.execute("UPDATE graph_write_guard SET graph_revision=graph_revision+1,locked_task_id=NULL,locked_at=NULL WHERE id=1 AND locked_task_id=%s", (task_id,))
        else:
            cur.execute("UPDATE graph_write_guard SET locked_task_id=NULL,locked_at=NULL WHERE id=1 AND locked_task_id=%s", (task_id,))
        cur.execute("INSERT INTO graph_update_task_events (task_id,event_type,stage,message) VALUES (%s,%s,'apply',%s)", (task_id, status, (error or "变更已提交")[:500] if success else (error or "应用失败")[:500]))


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
