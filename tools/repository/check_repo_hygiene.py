#!/usr/bin/env python3
"""Fail when forbidden runtime/private artifacts are tracked by Git."""

from __future__ import annotations

import subprocess
import sys
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MAX_TRACKED_BYTES = 10 * 1024 * 1024
FORBIDDEN_PREFIXES = (
    "backend/app/static/uploads/",
    "backend/private_uploads/",
    "datasets/snapshots/",
    "generate_graph/promotion_backups/",
)
FORBIDDEN_NAMES = ("job_eval_results_", "IMG_")
FORBIDDEN_SUFFIXES = (".env", ".xls", ".xlsx", ".dump", ".sql.gz")
NEO4J_WRITER_PATTERN = re.compile(r"\b(?:execute_write|DETACH\s+DELETE|DELETE\s+[a-zA-Z]|\bSET\s+[a-zA-Z]|\bMERGE\s*\()", re.IGNORECASE)
NEO4J_READ_ONLY_ALLOWLIST = {
    "tools/neo4j/check_neo4j_duplicates.py",
    "tools/repository/check_repo_hygiene.py",
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def violations(paths: list[str]) -> list[str]:
    problems: list[str] = []
    for relative in paths:
        path = PurePosixPath(relative)
        filename = path.name
        if relative.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"forbidden path: {relative}")
            continue
        if any(filename.startswith(prefix) for prefix in FORBIDDEN_NAMES):
            problems.append(f"generated/private result: {relative}")
            continue
        if filename != ".env.example" and relative.endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"raw or secret file: {relative}")
            continue
        absolute = ROOT / relative
        if absolute.is_file() and absolute.stat().st_size > MAX_TRACKED_BYTES:
            problems.append(f"tracked file exceeds 10 MiB: {relative}")
    return problems


def graph_writer_violations() -> list[str]:
    problems = []
    for absolute in (ROOT / "tools").rglob("*.py"):
        relative = absolute.relative_to(ROOT).as_posix()
        if relative in NEO4J_READ_ONLY_ALLOWLIST:
            continue
        source = absolute.read_text(encoding="utf-8", errors="ignore")
        if ("GraphDatabase" in source or "neo4j_driver" in source) and NEO4J_WRITER_PATTERN.search(source):
            problems.append(f"direct Neo4j writer outside backend queue: {relative}")
    return problems


def main() -> int:
    problems = violations(tracked_files()) + graph_writer_violations()
    if problems:
        print("Repository hygiene check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
