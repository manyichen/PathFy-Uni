"""Pure helpers for deterministic job listing, sorting, and pagination."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from app.infrastructure.neo4j import CONF_KEYS, DIM_KEYS, serialize_job_row
from app.domains.jobs.workstyle import WORKSTYLE_PROPERTY_KEYS, build_job_workstyle


def job_row_from_properties(
    properties: Any,
    element_id: Any,
    job_title_properties: Any = None,
) -> Dict[str, Any]:
    """Convert a Neo4j Job property map to the shared flat job-row contract."""
    props = dict(properties or {})
    fallback_id = str(element_id or "")
    row: Dict[str, Any] = {
        "id": (
            props.get("job_key")
            or props.get("job_code")
            or props.get("name")
            or props.get("title")
            or fallback_id
        ),
        "title": props.get("title") or props.get("name") or "未命名岗位",
        "salary": props.get("salary_norm") or props.get("salary") or "薪资面议",
        "salary_raw": props.get("salary") or "",
        "company": props.get("company") or "未知公司",
        "location": props.get("location") or "未知地点",
        "risk_flags": props.get("cap_risk_flags") or [],
    }
    for key in (*DIM_KEYS, *CONF_KEYS):
        row[key] = props.get(key) or 0.0
    for key in WORKSTYLE_PROPERTY_KEYS:
        row[key] = props.get(key)
    row["workstyle"] = build_job_workstyle(props, dict(job_title_properties or {}))
    return row


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
