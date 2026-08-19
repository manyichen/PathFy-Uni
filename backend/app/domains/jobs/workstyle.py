"""Auditable Job/JobTitle work-environment profile normalization."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Mapping

WORKSTYLE_SNAPSHOT_VERSION = "workstyle-v1"
WORKSTYLE_SCORING_VERSION = "workstyle-evidence-v1"

WORKSTYLE_AXES = (
    ("interaction_intensity", "workstyle_interaction", "workstyle_conf_interaction", "独立产出", "高频互动"),
    ("abstraction_preference", "workstyle_abstraction", "workstyle_conf_abstraction", "具体流程", "开放问题"),
    ("analytical_decision", "workstyle_analytical", "workstyle_conf_analytical", "关系权衡", "规则分析"),
    ("structure_preference", "workstyle_structure", "workstyle_conf_structure", "灵活探索", "计划确定"),
)

WORKSTYLE_PROPERTY_KEYS = tuple(
    key for _code, value_key, confidence_key, _low, _high in WORKSTYLE_AXES
    for key in (value_key, confidence_key)
) + (
    "workstyle_scoring_version",
    "workstyle_evidence_json",
    "workstyle_source",
    "workstyle_updated_at",
)


def _number(value: Any, *, low: float, high: float) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not low <= parsed <= high:
        return None
    return parsed


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, Mapping) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return {}


def _evidence_items(value: Any) -> list[dict[str, str]]:
    raw_items = value if isinstance(value, list) else [value]
    items: list[dict[str, str]] = []
    for raw in raw_items:
        if isinstance(raw, Mapping):
            text = str(raw.get("text") or raw.get("evidence") or "").strip()
            source = str(raw.get("source") or "").strip()
        else:
            text = str(raw or "").strip()
            source = ""
        if text:
            items.append({"text": text[:500], "source": source[:120]})
    return items[:8]


def _display_time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def build_job_workstyle(
    job_properties: Mapping[str, Any] | None,
    job_title_properties: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize axes, inheriting only missing Job axes from its JobTitle."""
    job = dict(job_properties or {})
    title = dict(job_title_properties or {})
    job_evidence = _json_object(job.get("workstyle_evidence_json"))
    title_evidence = _json_object(title.get("workstyle_evidence_json"))
    axes: list[dict[str, Any]] = []

    for code, value_key, confidence_key, low_label, high_label in WORKSTYLE_AXES:
        value = _number(job.get(value_key), low=0, high=100)
        confidence = _number(job.get(confidence_key), low=0, high=1)
        source_record = job
        evidence_map = job_evidence
        evidence = _evidence_items(evidence_map.get(code) or evidence_map.get(value_key))
        inherited = False
        if value is None or confidence is None or not evidence:
            value = _number(title.get(value_key), low=0, high=100)
            confidence = _number(title.get(confidence_key), low=0, high=1)
            source_record = title
            evidence_map = title_evidence
            evidence = _evidence_items(evidence_map.get(code) or evidence_map.get(value_key))
            inherited = value is not None and confidence is not None and bool(evidence)
        if value is None or confidence is None or not evidence:
            continue
        axes.append(
            {
                "code": code,
                "value": round(value, 2),
                "confidence": round(confidence, 4),
                "low_label": low_label,
                "high_label": high_label,
                "evidence": evidence,
                "source": str(source_record.get("workstyle_source") or "").strip(),
                "inherited_from_job_title": inherited,
            }
        )

    versions = {
        str(record.get("workstyle_scoring_version") or "").strip()
        for record in (job, title)
        if str(record.get("workstyle_scoring_version") or "").strip()
    }
    updated_values = [_display_time(record.get("workstyle_updated_at")) for record in (job, title)]
    return {
        "status": "available" if any(axis["evidence"] for axis in axes) else "insufficient_evidence",
        "axes": axes,
        "axis_count": len(axes),
        "evidenced_axis_count": sum(1 for axis in axes if axis["evidence"]),
        "inherited_from_job_title": any(axis["inherited_from_job_title"] for axis in axes),
        "scoring_version": ",".join(sorted(versions)) or None,
        "snapshot_version": WORKSTYLE_SNAPSHOT_VERSION,
        "updated_at": next((value for value in updated_values if value), None),
    }
