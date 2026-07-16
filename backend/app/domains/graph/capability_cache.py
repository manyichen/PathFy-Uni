"""Persistent cache and telemetry for graph capability evaluation calls."""

from __future__ import annotations

import json
from typing import Any

from app.db import db_cursor


def load(
    fingerprint: str, *, cap_version: str, provider: str, model: str, prompt_version: str,
) -> dict[str, Any] | None:
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                """SELECT id,result_json,metadata_json FROM graph_capability_evaluation_cache
                   WHERE cap_input_fingerprint=%s AND cap_version=%s AND provider=%s
                     AND model=%s AND prompt_version=%s""",
                (fingerprint, cap_version, provider, model, prompt_version),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                """UPDATE graph_capability_evaluation_cache
                   SET hit_count=hit_count+1,last_used_at=NOW(6) WHERE id=%s""",
                (row["id"],),
            )
            raw = row.get("result_json")
            result = json.loads(raw) if isinstance(raw, str) else raw
            return dict(result) if isinstance(result, dict) else None
    except Exception:
        return None


def store(
    fingerprint: str, result: dict[str, Any], metadata: dict[str, Any], *,
    cap_version: str, provider: str, model: str, prompt_version: str,
) -> None:
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                """INSERT INTO graph_capability_evaluation_cache
                   (cap_input_fingerprint,cap_version,provider,model,prompt_version,result_json,metadata_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE result_json=VALUES(result_json),
                     metadata_json=VALUES(metadata_json),last_used_at=NOW(6)""",
                (fingerprint, cap_version, provider, model, prompt_version,
                 json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                 json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))),
            )
    except Exception:
        return


def record_metric(
    *, task_id: int | None, stage: str, provider: str, model: str,
    request_id: str | None = None, duration_ms: int = 0,
    prompt_tokens: int = 0, completion_tokens: int = 0,
    retry_count: int = 0, cache_hit: bool = False, error_code: str | None = None,
) -> None:
    """Telemetry is best-effort and must never invalidate a valid model result."""
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                """INSERT INTO graph_llm_call_metrics
                   (task_id,stage,provider,model,request_id,duration_ms,prompt_tokens,
                    completion_tokens,retry_count,cache_hit,error_code)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (task_id, stage[:80], provider[:80], model[:160],
                 (request_id or "")[:160] or None, max(0, int(duration_ms)),
                 max(0, int(prompt_tokens)), max(0, int(completion_tokens)),
                 max(0, int(retry_count)), bool(cache_hit),
                 (error_code or "")[:80] or None),
            )
    except Exception:
        return
