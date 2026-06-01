"""人岗匹配快照：match_runs / match_run_items 表管理与读写。"""

from __future__ import annotations

import json
from typing import Any

from app.db import db_cursor

_MATCH_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS match_runs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  resume_id BIGINT UNSIGNED NOT NULL,
  match_goal VARCHAR(16) NOT NULL DEFAULT 'fit',
  q VARCHAR(191) NULL,
  location_q VARCHAR(191) NULL,
  refine_with_llm TINYINT(1) NOT NULL DEFAULT 0,
  student_json LONGTEXT NULL,
  stats_json JSON NULL,
  llm_json LONGTEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_match_runs_user_resume_created (user_id, resume_id, created_at DESC),
  KEY idx_match_runs_user_goal_created (user_id, match_goal, created_at DESC),
  CONSTRAINT fk_match_runs_user_id
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_MATCH_RUN_ITEMS_DDL = """
CREATE TABLE IF NOT EXISTS match_run_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id BIGINT UNSIGNED NOT NULL,
  rank_index INT NOT NULL DEFAULT 0,
  job_id VARCHAR(191) NOT NULL,
  is_llm_top5 TINYINT(1) NOT NULL DEFAULT 0,
  job_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_match_run_items_run_rank (run_id, rank_index),
  KEY idx_match_run_items_run_id (run_id),
  KEY idx_match_run_items_job_id (job_id),
  CONSTRAINT fk_match_run_items_run_id
    FOREIGN KEY (run_id) REFERENCES match_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def ensure_match_snapshot_tables() -> None:
    with db_cursor() as (_, cur):
        cur.execute(_MATCH_RUNS_DDL)
        cur.execute(_MATCH_RUN_ITEMS_DDL)


def persist_match_snapshot(
    *,
    jwt_user_id: int | None,
    resume_id: int | None,
    data_out: dict[str, Any],
    refine_with_llm: bool,
) -> None:
    if jwt_user_id is None or resume_id is None:
        return
    jobs = data_out.get("jobs") or []
    if not isinstance(jobs, list) or not jobs:
        return

    ensure_match_snapshot_tables()
    filters = data_out.get("filters") or {}
    stats = data_out.get("stats") or {}
    llm = data_out.get("llm") or {}
    llm_top_ids: set[str] = set()
    if isinstance(llm, dict) and llm.get("ok"):
        for it in llm.get("top5") or []:
            if isinstance(it, dict) and it.get("job_id"):
                llm_top_ids.add(str(it.get("job_id")))

    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO match_runs (
              user_id, resume_id, match_goal, q, location_q, refine_with_llm, student_json, stats_json, llm_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                jwt_user_id,
                resume_id,
                str(filters.get("match_goal") or "fit")[:16],
                str(filters.get("q") or "")[:191] or None,
                str(filters.get("location_q") or "")[:191] or None,
                1 if refine_with_llm else 0,
                _json_dumps(data_out.get("student") or {}),
                _json_dumps(stats if isinstance(stats, dict) else {}),
                _json_dumps(llm if isinstance(llm, dict) else {}),
            ),
        )
        run_id = int(cur.lastrowid)
        for idx, card in enumerate(jobs):
            if not isinstance(card, dict):
                continue
            job_id = str(card.get("id") or "").strip()
            if not job_id:
                continue
            cur.execute(
                """
                INSERT INTO match_run_items (run_id, rank_index, job_id, is_llm_top5, job_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    idx + 1,
                    job_id[:191],
                    1 if job_id in llm_top_ids else 0,
                    _json_dumps(card),
                ),
            )


def load_recent_match_snapshot(
    *,
    user_id: int,
    resume_id: int,
    match_goal: str,
    limit: int,
) -> tuple[list[dict[str, Any]], str]:
    ensure_match_snapshot_tables()
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, llm_json
            FROM match_runs
            WHERE user_id = %s
              AND resume_id = %s
              AND match_goal = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, resume_id, match_goal),
        )
        run = cur.fetchone()
        if not run:
            return [], "none"
        run_id = int(run["id"])
        llm_json = run.get("llm_json")
        if isinstance(llm_json, str):
            try:
                llm_json = json.loads(llm_json)
            except Exception:  # noqa: BLE001
                llm_json = {}
        if not isinstance(llm_json, dict):
            llm_json = {}

        if llm_json.get("ok") and isinstance(llm_json.get("top5"), list):
            llm_targets: list[dict[str, Any]] = []
            for item in (llm_json.get("top5") or [])[:limit]:
                if not isinstance(item, dict):
                    continue
                llm_targets.append(
                    {
                        "job_id": item.get("job_id"),
                        "title": item.get("title"),
                        "company": item.get("company"),
                        "location": item.get("location"),
                        "salary": item.get("salary"),
                        "score_avg": item.get("coarse_match_score"),
                        "reason": item.get("one_line") or "",
                        "source": "match_snapshot_llm",
                    }
                )
            if llm_targets:
                return llm_targets, "match_snapshot_llm"

        cur.execute(
            """
            SELECT rank_index, job_json
            FROM match_run_items
            WHERE run_id = %s
            ORDER BY rank_index ASC
            LIMIT %s
            """,
            (run_id, limit),
        )
        rows = cur.fetchall()

    coarse_targets: list[dict[str, Any]] = []
    for row in rows:
        job_json = row.get("job_json")
        if isinstance(job_json, str):
            try:
                job_json = json.loads(job_json)
            except Exception:  # noqa: BLE001
                job_json = {}
        if not isinstance(job_json, dict):
            continue
        coarse_targets.append(
            {
                "job_id": job_json.get("id"),
                "title": job_json.get("title"),
                "company": job_json.get("company"),
                "location": job_json.get("location"),
                "salary": job_json.get("salary"),
                "score_avg": (job_json.get("match_preview") or {}).get("match_score"),
                "reason": "来自最近一次匹配快照",
                "source": "match_snapshot_coarse",
            }
        )
    return coarse_targets, ("match_snapshot_coarse" if coarse_targets else "none")
