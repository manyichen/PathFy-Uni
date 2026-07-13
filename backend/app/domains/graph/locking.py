"""Cross-process serialization for destructive or reconciling graph writes."""

from __future__ import annotations

from contextlib import contextmanager

from app.db import get_connection

LOCK_NAME = "pathfy:graph-write"


class GraphOperationBusy(RuntimeError):
    pass


@contextmanager
def graph_write_lock(*, allowed_task_id: int | None = None):
    """Use a MySQL named lock so multiple Gunicorn workers cannot reconcile concurrently."""
    connection = get_connection()
    acquired = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT locked_task_id FROM graph_write_guard WHERE id = 1")
            guard = cursor.fetchone() or {}
            if guard.get("locked_task_id") and int(guard["locked_task_id"]) != int(allowed_task_id or 0):
                raise GraphOperationBusy(
                    f"图谱被待确认任务 #{guard['locked_task_id']} 锁定"
                )
            cursor.execute("SELECT GET_LOCK(%s, 0) AS acquired", (LOCK_NAME,))
            row = cursor.fetchone() or {}
            acquired = int(row.get("acquired") or 0) == 1
        if not acquired:
            raise GraphOperationBusy("已有图谱更新任务正在执行，请稍后重试")
        yield
    finally:
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
            finally:
                connection.close()
        else:
            connection.close()
