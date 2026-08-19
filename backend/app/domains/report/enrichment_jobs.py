"""Non-blocking in-process runner for report AI enrichment.

Job state is persisted in MySQL so every Gunicorn worker can report the same
status. The executor keeps long external-model calls outside the HTTP request;
failed or interrupted jobs remain retryable through the same start endpoint.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Dict

from flask import Flask

from app.domains.report.repository import (
    claim_report_enrichment,
    get_report_config_snapshot,
    get_report_enrichment_status,
    update_report_enrichment_status,
)
from app.domains.report.services import enrich_career_report
from app.domains.settings.service import active_system_settings, use_settings

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="report-enrichment")
_LOCAL_RUNNING: set[tuple[int, int]] = set()
_LOCK = Lock()


def _run_enrichment(app: Flask, user_id: int, report_id: int, attempt: int, scope: str = "full") -> None:
    with app.app_context():
        started = update_report_enrichment_status(
            report_id,
            "running",
            stage="loading_snapshot",
            progress=3,
            expected_attempt=attempt,
        )
        if started.get("superseded"):
            with _LOCK:
                _LOCAL_RUNNING.discard((report_id, attempt))
            return
        try:
            stored = get_report_config_snapshot(user_id, report_id)
            settings = (stored or {}).get("settings") or active_system_settings()["settings"]

            def report_progress(stage: str, progress: int) -> None:
                update_report_enrichment_status(
                    report_id,
                    "running",
                    stage=stage,
                    progress=progress,
                    expected_attempt=attempt,
                )

            with use_settings(settings):
                result = enrich_career_report(
                    user_id,
                    report_id,
                    expected_attempt=attempt,
                    on_progress=report_progress,
                    refresh_scope=scope,
                )
            if result.get("superseded"):
                return
            update_report_enrichment_status(
                report_id,
                "completed",
                timing_ms=result.get("enrichment_timing_ms") or {},
                stage="completed",
                progress=100,
                quality=result.get("quality") or {},
                expected_attempt=attempt,
            )
        except Exception:  # noqa: BLE001
            app.logger.exception("career_report_background_enrich_failed", extra={"report_id": report_id})
            update_report_enrichment_status(
                report_id,
                "failed",
                error="AI 增强失败，请稍后重试",
                stage="failed",
                expected_attempt=attempt,
            )
        finally:
            with _LOCK:
                _LOCAL_RUNNING.discard((report_id, attempt))


def enqueue_report_enrichment(app: Flask, user_id: int, report_id: int, *, scope: str = "full") -> Dict[str, Any] | None:
    if scope not in ("full", "narrative", "resources", "plan"):
        raise ValueError("invalid_enrichment_scope")
    claimed, job = claim_report_enrichment(user_id, report_id, scope=scope)
    if job.get("status") == "missing":
        return None
    if not claimed:
        return job
    attempt = int(job.get("attempt") or 0)
    job_key = (report_id, attempt)
    with _LOCK:
        if job_key in _LOCAL_RUNNING:
            return job
        _LOCAL_RUNNING.add(job_key)
    try:
        _EXECUTOR.submit(_run_enrichment, app, user_id, report_id, attempt, scope)
    except Exception:  # noqa: BLE001
        with _LOCK:
            _LOCAL_RUNNING.discard(job_key)
        update_report_enrichment_status(
            report_id,
            "failed",
            error="AI 增强任务启动失败，请稍后重试",
            expected_attempt=attempt,
        )
        raise
    return job


def report_enrichment_status(user_id: int, report_id: int) -> Dict[str, Any] | None:
    return get_report_enrichment_status(user_id, report_id)
