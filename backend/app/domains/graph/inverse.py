"""Generate exact property-only inverse changes from planner-captured old values."""

from __future__ import annotations

from typing import Any


def build_inverse_change_set(change: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(change.get("kind") or "")
    if kind not in {
        "job_capability_evaluation",
        "job_capability_result_import",
        "salary_normalization",
    }:
        return None
    rows: list[dict[str, Any]] = []
    for item in change.get("jobs", []):
        if not isinstance(item, dict) or not item.get("job_key") or not isinstance(item.get("old"), dict):
            return None
        rows.append({"job_key": str(item["job_key"]), "properties": dict(item["old"])})
    if not rows:
        return None
    return {
        "version": 2,
        "kind": "graph_inverse",
        "inverse_of_kind": kind,
        "jobs": rows,
    }
