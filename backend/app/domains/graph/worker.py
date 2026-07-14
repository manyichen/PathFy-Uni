"""Durable MySQL-backed graph task worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import time

from app import create_app
from app.domains.graph import task_repository as repo
from app.domains.graph.task_planner import build_change_set
from app.domains.graph.task_apply import is_task_applied
from app.domains.graph.locking import GraphOperationBusy, graph_write_lock
from app.domains.settings.service import use_settings


def process_one() -> bool:
    task = repo.claim_next_task()
    if not task: return False
    try:
        repo.add_event(task["id"], "planning", "正在解析输入并生成变更集", stage="planning")
        emit = lambda stage, message, detail=None: repo.add_event(task["id"], "progress", message, stage=stage, detail=detail)
        with use_settings(task.get("config_snapshot") or {}):
            change_set, summary = build_change_set(task, emit)
        encoded = json.dumps(change_set, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        try:
            with graph_write_lock():
                repo.prepare_task(task["id"], base_revision=int(task["base_graph_revision"]), summary=summary, change_set_json=encoded, change_set_sha256=digest)
        except GraphOperationBusy:
            repo.requeue_task(task["id"], "其他图谱写操作正在提交，任务已重新排队")
    except Exception as exc:
        repo.fail_task(task["id"], str(exc))
        return True
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="PathFy graph update queue worker")
    parser.add_argument("--once", action="store_true", help="process at most one task and exit")
    args = parser.parse_args(); app = create_app()
    with app.app_context():
        repo.recover_running_tasks()
        for task in repo.get_applying_tasks():
            if is_task_applied(task["task_uuid"]):
                repo.finish_apply(task["id"], success=True, error="Worker 重启后根据 Neo4j 提交标记完成恢复")
            else:
                repo.reset_applying_task(task["id"])
        while True:
            worked = process_one()
            if args.once: return
            if not worked: time.sleep(float(app.config["GRAPH_WORKER_POLL_SECONDS"]))


if __name__ == "__main__": main()
