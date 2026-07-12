"""Pure helpers for deterministic job listing, sorting, and pagination."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from app.infrastructure.neo4j import serialize_job_row


def normalize_jobs_sort(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if value in {"random", "score_asc", "score_desc"}:
        return value
    return "default"


def jobs_order_clause(sort_mode: str) -> str:
    if sort_mode == "score_asc":
        return "ORDER BY total_score ASC, title ASC"
    return "ORDER BY total_score DESC, title ASC"


def jobs_shuffle_key(job_id: str, seed: str) -> str:
    return hashlib.md5(f"{seed}:{job_id}".encode("utf-8")).hexdigest()


def jobs_page_payload(
    rows: List[Dict[str, Any]],
    *,
    page: int,
    page_size: int,
    sort_mode: str,
    seed: str = "",
) -> Dict[str, Any]:
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page_num = min(max(1, page), total_pages)
    start = (page_num - 1) * page_size
    page_rows = rows[start : start + page_size]
    data = [serialize_job_row(row) for row in page_rows]
    payload: Dict[str, Any] = {
        "jobs": data,
        "total": total,
        "page": page_num,
        "page_size": page_size,
        "total_pages": total_pages,
        "sort": sort_mode,
    }
    if sort_mode == "random" and seed:
        payload["seed"] = seed
    return payload
