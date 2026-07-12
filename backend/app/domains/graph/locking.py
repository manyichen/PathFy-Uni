"""Cross-process serialization for destructive or reconciling graph writes."""

from __future__ import annotations

from contextlib import contextmanager

from app.db import get_connection

LOCK_NAME = "pathfy:graph-write"


class GraphOperationBusy(RuntimeError):
    pass


@contextmanager
def graph_write_lock():
    """Use a MySQL named lock so multiple Gunicorn workers cannot reconcile concurrently."""
    connection = get_connection()
    acquired = False
    try:
        with connection.cursor() as cursor:
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
