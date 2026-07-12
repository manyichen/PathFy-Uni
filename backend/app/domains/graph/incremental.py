"""Pure planning helpers for deterministic, source-scoped graph imports."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, Iterable, Tuple

import pandas as pd

from app.domains.graph.constants import normalize_text, normalize_title

FINGERPRINT_VERSION = "job-import-v1"
FINGERPRINT_COLUMNS = (
    "name",
    "company",
    "location",
    "salary",
    "industry",
    "company_size",
    "company_type",
    "job_code",
    "demand",
    "updated_date",
    "company_detail",
    "source_url",
)


def job_key_for_row(row: Any) -> str:
    title = normalize_text(row["name"])
    company = normalize_text(row["company"])
    return f"{normalize_title(title)}::{company.lower()}"


def fingerprint_for_row(row: Any, *, extraction_version: str) -> str:
    payload = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "extraction_version": str(extraction_version or "").strip(),
        "fields": {column: normalize_text(row.get(column)) for column in FINGERPRINT_COLUMNS},
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def deduplicate_jobs(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Keep the last occurrence of each existing business key, deterministically."""
    if df.empty:
        return df.copy(), 0
    work = df.copy()
    work["_import_job_key"] = [job_key_for_row(row) for _, row in work.iterrows()]
    before = len(work)
    work = work.drop_duplicates(subset=["_import_job_key"], keep="last")
    duplicates = before - len(work)
    return work.drop(columns=["_import_job_key"]).reset_index(drop=True), duplicates


def plan_incremental_rows(
    df: pd.DataFrame,
    existing_fingerprints: Dict[str, str],
    *,
    extraction_version: str,
) -> tuple[pd.DataFrame, list[str], Dict[str, str]]:
    """Return changed rows, unchanged keys, and fingerprints for all input rows."""
    fingerprints: Dict[str, str] = {}
    changed_indexes = []
    unchanged_keys = []
    for index, row in df.iterrows():
        key = job_key_for_row(row)
        fingerprint = fingerprint_for_row(row, extraction_version=extraction_version)
        fingerprints[key] = fingerprint
        if existing_fingerprints.get(key) == fingerprint:
            unchanged_keys.append(key)
        else:
            changed_indexes.append(index)
    return df.loc[changed_indexes].reset_index(drop=True), unchanged_keys, fingerprints


def normalize_source_id(value: str | None) -> str:
    raw = os.path.basename(str(value or "manual").strip()) or "manual"
    normalized = re.sub(r"[^\w.-]+", "-", raw).strip("-.")
    return (normalized or "manual")[:120]


def import_keys(df: pd.DataFrame) -> list[str]:
    return [job_key_for_row(row) for _, row in df.iterrows()]
