"""Durable MySQL-backed graph task worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import threading
import time

from flask import current_app

from app import create_app
from app.domains.graph import task_repository as repo
from app.domains.graph.task_planner import TaskPlanningError, build_change_set
from app.domains.graph.task_apply import apply_change_set, is_task_applied
from app.domains.graph.locking import GraphOperationBusy, graph_write_lock
from app.domains.graph.task_projection import project_task, projection_required
from app.domains.settings.service import use_settings


class TaskLeaseLost(RuntimeError):
    pass


class _LeaseHeartbeat:
    def __init__(self, app, task_id: int, lease_token: str, lease_seconds: int):
        self.app = app
        self.task_id = task_id
        self.lease_token = lease_token
        self.lease_seconds = max(15, int(lease_seconds))
        self.stop = threading.Event()
        self.lost = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"graph-lease-{task_id}", daemon=True)

    def _run(self) -> None:
        interval = max(5, self.lease_seconds // 3)
        with self.app.app_context():
            while not self.stop.wait(interval):
                try:
                    if not repo.renew_lease(self.task_id, self.lease_token, lease_seconds=self.lease_seconds):
                        self.lost.set()
                        return
                except Exception:
                    # A temporary DB outage may recover before the lease expires.  The
                    # final compare-and-set still prevents a stale worker from committing.
                    continue

    def __enter__(self):
        self.thread.start()
        return self

    def ensure_owned(self) -> None:
        if self.lost.is_set():
            raise TaskLeaseLost("任务租约已被其他 worker 接管")

    def __exit__(self, *_args):
        self.stop.set()
        self.thread.join(timeout=2)


def _error_policy(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, TaskPlanningError):
        return "invalid_input", False
    if isinstance(exc, TaskLeaseLost):
        return "lease_lost", False
    message = str(exc).lower()
    if any(token in message for token in ("api key", "未配置", "不支持的", "字段", "重复", "不存在的岗位")):
        return "configuration_or_validation", False
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return "transient_io", True
    if any(token in message for token in ("timeout", "timed out", "429", "rate limit", "temporar", "connection", "service unavailable", "llm", "provider")):
        return "transient_provider", True
    return "worker_error", False


def _retry_delay(attempt_count: int, base_seconds: int, task_id: int) -> int:
    base = max(1, int(base_seconds))
    exponential = min(base * (2 ** max(0, int(attempt_count) - 1)), 300)
    return exponential + (int(task_id) % (base + 1))


def process_one(*, worker_id: str | None = None, lease_seconds: int | None = None,
                max_attempts: int | None = None, retry_base_seconds: int | None = None) -> bool:
    app = current_app._get_current_object()
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    lease_seconds = int(lease_seconds or app.config["GRAPH_WORKER_LEASE_SECONDS"])
    max_attempts = int(max_attempts or app.config["GRAPH_WORKER_MAX_ATTEMPTS"])
    retry_base_seconds = int(retry_base_seconds or app.config["GRAPH_WORKER_RETRY_BASE_SECONDS"])
    task = repo.claim_next_task(worker_id=worker_id, lease_seconds=lease_seconds)
    if not task: return False
    lease_token = str(task.get("lease_token") or "")
    try:
        with _LeaseHeartbeat(app, int(task["id"]), lease_token, lease_seconds) as heartbeat:
            heartbeat.ensure_owned()
            repo.add_event(task["id"], "planning", "正在解析输入并生成变更集", stage="planning")

            def emit(stage, message, detail=None):
                heartbeat.ensure_owned()
                repo.add_event(task["id"], "progress", message, stage=stage, detail=detail)

            with use_settings(task.get("config_snapshot") or {}):
                change_set, summary = build_change_set(task, emit)
            heartbeat.ensure_owned()
            encoded = json.dumps(change_set, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            try:
                with graph_write_lock():
                    prepared = repo.prepare_task(
                        task["id"], base_revision=int(task["base_graph_revision"]), summary=summary,
                        change_set_json=encoded, change_set_sha256=digest, lease_token=lease_token,
                    )
                    if not prepared:
                        heartbeat.lost.set()
            except GraphOperationBusy:
                repo.requeue_task(task["id"], "其他图谱写操作正在提交，任务已重新排队", lease_token=lease_token)
    except TaskLeaseLost:
        return True
    except Exception as exc:
        error_code, retryable = _error_policy(exc)
        repo.fail_or_retry_task(
            task["id"], str(exc), lease_token=lease_token, error_code=error_code,
            retryable=retryable, max_attempts=max_attempts,
            retry_delay_seconds=_retry_delay(int(task.get("attempt_count") or 1), retry_base_seconds, int(task["id"])),
        )
        return True
    return True


def _verify_task_change_set(task: dict) -> dict:
    change = task.get("change_set")
    if not isinstance(change, dict) or not change:
        raise RuntimeError("任务没有可应用的变更集")
    encoded = json.dumps(change, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    if digest != task.get("change_set_sha256"):
        raise RuntimeError("变更集 SHA-256 校验失败")
    return change


def process_applying_one(*, worker_id: str | None = None, lease_seconds: int | None = None,
                         retry_base_seconds: int | None = None) -> bool:
    """Commit one confirmed graph task and finish its idempotent MySQL projection."""
    app = current_app._get_current_object()
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    lease_seconds = int(lease_seconds or app.config["GRAPH_WORKER_LEASE_SECONDS"])
    retry_base_seconds = int(retry_base_seconds or app.config["GRAPH_WORKER_RETRY_BASE_SECONDS"])
    task = repo.claim_next_applying_task(worker_id=worker_id, lease_seconds=lease_seconds)
    if not task:
        return False
    task_id = int(task["id"])
    lease_token = str(task.get("lease_token") or "")
    committed = bool(task.get("neo4j_committed_at"))
    commit_recorded = committed
    try:
        with _LeaseHeartbeat(app, task_id, lease_token, lease_seconds) as heartbeat:
            heartbeat.ensure_owned()
            change = _verify_task_change_set(task)
            if not committed:
                try:
                    with graph_write_lock(allowed_task_id=task_id):
                        heartbeat.ensure_owned()
                        if not is_task_applied(task["task_uuid"]):
                            apply_change_set(
                                change,
                                task_uuid=task["task_uuid"],
                                change_sha256=task["change_set_sha256"],
                            )
                        committed = True
                        heartbeat.ensure_owned()
                        if not repo.mark_neo4j_committed(task_id, lease_token=lease_token):
                            raise TaskLeaseLost("Neo4j 提交结果失去任务租约")
                        commit_recorded = True
                    committed = True
                except GraphOperationBusy:
                    repo.release_applying_lease(task_id, lease_token)
                    return True
                except Exception as exc:
                    try:
                        graph_has_commit = is_task_applied(task["task_uuid"])
                    except Exception:
                        graph_has_commit = False
                    if graph_has_commit:
                        committed = True
                        if not repo.mark_neo4j_committed(task_id, lease_token=lease_token):
                            raise TaskLeaseLost("恢复 Neo4j 提交结果时失去任务租约") from exc
                        commit_recorded = True
                    else:
                        repo.fail_apply(task_id, str(exc), lease_token=lease_token)
                        return True

            required = projection_required(task)
            if not required:
                if not repo.finish_projection(task_id, lease_token=lease_token, required=False):
                    raise TaskLeaseLost("完成图谱任务时失去任务租约")
                return True

            if not repo.start_projection(task_id, lease_token=lease_token):
                raise TaskLeaseLost("领取 MySQL 投影时失去任务租约")
            try:
                project_task(task)
            except Exception as exc:
                attempts = int(task.get("projection_attempts") or 0) + 1
                repo.schedule_projection_retry(
                    task_id,
                    str(exc),
                    lease_token=lease_token,
                    retry_delay_seconds=_retry_delay(attempts, retry_base_seconds, task_id),
                )
                return True
            if not repo.finish_projection(task_id, lease_token=lease_token, required=True):
                raise TaskLeaseLost("完成 MySQL 投影时失去任务租约")
            return True
    except TaskLeaseLost:
        return True
    except Exception as exc:
        if commit_recorded:
            repo.schedule_projection_retry(
                task_id,
                str(exc),
                lease_token=lease_token,
                retry_delay_seconds=_retry_delay(int(task.get("projection_attempts") or 0) + 1, retry_base_seconds, task_id),
            )
        elif committed:
            # Neo4j already contains the commit marker.  Never mark the task
            # failed merely because recording the cross-store fact in MySQL
            # was temporarily unavailable; the next worker will reconcile it.
            repo.release_applying_lease(task_id, lease_token)
        else:
            repo.fail_apply(task_id, str(exc), lease_token=lease_token)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="PathFy graph update queue worker")
    parser.add_argument("--once", action="store_true", help="process at most one task and exit")
    args = parser.parse_args(); app = create_app()
    with app.app_context():
        repo.recover_expired_tasks()
        while True:
            repo.recover_expired_tasks()
            worked = process_applying_one() or process_one()
            if args.once: return
            if not worked: time.sleep(float(app.config["GRAPH_WORKER_POLL_SECONDS"]))


if __name__ == "__main__": main()
