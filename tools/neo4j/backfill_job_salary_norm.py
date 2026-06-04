"""
将 Neo4j Job.salary 归一化为 salary_norm（X-Y元 / 面议 / 未知 / 待定）及数值字段。

读取 backend/.env 的 NEO4J_*。

用法：
  python tools/neo4j/backfill_job_salary_norm.py --dry-run
  python tools/neo4j/backfill_job_salary_norm.py
  python tools/neo4j/backfill_job_salary_norm.py --force   # 忽略 salary_parse_version 重算
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.infrastructure.salary import SALARY_PARSE_VERSION, neo4j_salary_properties  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")


def _connect():
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not password:
        raise SystemExit("ERROR: 未设置 NEO4J_PASSWORD（请在 backend/.env 配置）")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver, database


def main() -> int:
    parser = argparse.ArgumentParser(description="回填 Job 薪资归一化字段")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    parser.add_argument("--force", action="store_true", help="重算已有 salary_parse_version 的节点")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()

    driver, database = _connect()
    norm_counter: Counter[str] = Counter()
    updated = 0
    skipped = 0
    failed = 0

    fetch_q = """
    MATCH (j:Job)
    WHERE j.salary IS NOT NULL
    RETURN j.job_key AS job_key, j.salary AS salary, j.salary_parse_version AS ver
    """

    set_q = """
    UNWIND $rows AS row
    MATCH (j:Job {job_key: row.job_key})
    SET j.salary_norm = row.salary_norm,
        j.salary_negotiable = row.salary_negotiable,
        j.salary_parse_version = row.salary_parse_version
    SET j.salary_monthly_min = row.salary_monthly_min,
        j.salary_monthly_max = row.salary_monthly_max
    SET j.salary_bonus_months = row.salary_bonus_months
    """

    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(fetch_q)]
        batch: list[dict] = []

        for rec in rows:
            job_key = str(rec.get("job_key") or "").strip()
            raw = str(rec.get("salary") or "").strip()
            ver = str(rec.get("ver") or "").strip()
            if not job_key or not raw:
                skipped += 1
                continue
            if ver == SALARY_PARSE_VERSION and not args.force:
                skipped += 1
                continue
            try:
                props = neo4j_salary_properties(raw)
            except Exception:
                failed += 1
                continue

            norm_counter[props["salary_norm"]] += 1
            row = {
                "job_key": job_key,
                "salary_norm": props["salary_norm"],
                "salary_negotiable": props["salary_negotiable"],
                "salary_parse_version": props["salary_parse_version"],
                "salary_monthly_min": props.get("salary_monthly_min"),
                "salary_monthly_max": props.get("salary_monthly_max"),
                "salary_bonus_months": props.get("salary_bonus_months"),
            }
            batch.append(row)
            updated += 1

            if len(batch) >= args.batch_size:
                if not args.dry_run:
                    session.run(set_q, {"rows": batch})
                batch = []

        if batch and not args.dry_run:
            session.run(set_q, {"rows": batch})

    driver.close()

    print(f"version={SALARY_PARSE_VERSION} dry_run={args.dry_run} force={args.force}")
    print(f"updated={updated} skipped={skipped} failed={failed}")
    print("top salary_norm:")
    for norm, c in norm_counter.most_common(15):
        print(f"  {norm}: {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
