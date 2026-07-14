"""Administrative CLI that enqueues graph work without writing Neo4j."""

from __future__ import annotations

import argparse
from pathlib import Path

from werkzeug.datastructures import FileStorage

from app import create_app
from app.domains.graph.task_registry import TASK_SPECS
from app.domains.graph.task_service import enqueue_task


def main() -> None:
    parser = argparse.ArgumentParser(description="创建 MySQL 图谱更新任务；不会直接写 Neo4j")
    sub = parser.add_subparsers(dest="command", required=True)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("task_type", choices=sorted(k for k in TASK_SPECS if k != "emergency_clear"))
    enqueue.add_argument("--user-id", type=int, required=True)
    enqueue.add_argument("--file", type=Path)
    enqueue.add_argument("--learning-file", type=Path)
    enqueue.add_argument("--competition-file", type=Path)
    enqueue.add_argument("--source-id")
    enqueue.add_argument("--mode", choices=("merge", "snapshot"))
    enqueue.add_argument("--scope", choices=("missing", "stale", "all"), default="missing")
    enqueue.add_argument("--force", action="store_true")
    enqueue.add_argument("--batch-size", type=int, default=128)
    enqueue.add_argument("--capability-batch-size", type=int, default=8)
    enqueue.add_argument("--no-promotions", action="store_true")
    enqueue.add_argument("--no-lateral", action="store_true")
    args = parser.parse_args()
    streams = []
    try:
        uploads = {}
        for role, path in (("file", args.file), ("learning_file", args.learning_file), ("competition_file", args.competition_file)):
            if path:
                stream = path.open("rb"); streams.append(stream)
                uploads[role] = FileStorage(stream=stream, filename=path.name)
        app = create_app()
        with app.app_context():
            task = enqueue_task(user_id=args.user_id, task_type=args.task_type, uploaded_files=uploads,
                                source_id=args.source_id, mode=args.mode,
                                batch_size=args.batch_size,
                                generate_promotions=not args.no_promotions,
                                generate_lateral=not args.no_lateral,
                                options={"scope": args.scope, "force": args.force, "capability_batch_size": args.capability_batch_size})
        print(f"queued graph task #{task['id']} ({task['task_type']})")
    finally:
        for stream in streams: stream.close()


if __name__ == "__main__":
    main()
