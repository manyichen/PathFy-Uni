"""Regression coverage for the non-blocking report generation contract."""
from __future__ import annotations

from app.domains.report import router
from app.domains.report import enrichment_jobs


def _authenticated(monkeypatch):
    monkeypatch.setattr(router, "_require_user", lambda: (7, None))


def test_generate_always_returns_a_fast_skeleton(client, monkeypatch):
    _authenticated(monkeypatch)
    monkeypatch.setattr(
        router,
        "active_system_settings",
        lambda: {"revision": 3, "settings": {}},
    )
    monkeypatch.setattr(
        router,
        "effective_preferences",
        lambda *_args, **_kwargs: {
            "effective": {
                "allow_external_llm": True,
                "report_copywriter": True,
                "report_auto_replan": True,
                "report_public_info": True,
                "report_graph_recommendations": True,
                "report_recommendation_llm": True,
                "learning_resource_count": 6,
                "competition_count": 3,
            }
        },
    )
    captured = {}

    def fake_generate(user_id, body):
        captured.update(body)
        return {"report_id": 91, "report": {"llm_enrich_pending": True}, "llm_enrich_pending": True}

    monkeypatch.setattr(router, "generate_career_report", fake_generate)
    response = client.post(
        "/api/report/generate",
        json={"resume_id": 1, "target_job_ids": ["job-1"], "primary_job_id": "job-1"},
    )

    assert response.status_code == 200
    assert captured["skip_llm_enrich"] is True
    assert response.get_json()["data"]["llm_enrich_pending"] is True


def test_enrichment_start_returns_without_waiting_for_model(client, monkeypatch):
    _authenticated(monkeypatch)
    monkeypatch.setattr(
        router,
        "enqueue_report_enrichment",
        lambda _app, user_id, report_id, **_kwargs: {"status": "queued", "attempt": 1},
    )

    response = client.post("/api/report/91/enrichment", json={})

    assert response.status_code == 202
    assert response.get_json()["data"] == {"report_id": 91, "status": "queued", "attempt": 1}


def test_enrichment_start_passes_a_valid_partition_scope(client, monkeypatch):
    _authenticated(monkeypatch)
    captured = {}

    def fake_enqueue(_app, _user_id, _report_id, *, scope):
        captured["scope"] = scope
        return {"status": "queued", "attempt": 2, "scope": scope}

    monkeypatch.setattr(router, "enqueue_report_enrichment", fake_enqueue)
    response = client.post("/api/report/91/enrichment", json={"scope": "resources"})

    assert response.status_code == 202
    assert captured["scope"] == "resources"
    assert response.get_json()["data"]["scope"] == "resources"


def test_enrichment_start_rejects_an_unknown_partition(client, monkeypatch):
    _authenticated(monkeypatch)
    response = client.post("/api/report/91/enrichment", json={"scope": "everything"})
    assert response.status_code == 400


def test_enrichment_status_is_pollable(client, monkeypatch):
    _authenticated(monkeypatch)
    monkeypatch.setattr(
        router,
        "report_enrichment_status",
        lambda user_id, report_id: {"status": "running", "attempt": 1},
    )

    response = client.get("/api/report/91/enrichment")

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "running"


def test_background_runner_persists_running_and_completed(app, monkeypatch):
    states = []
    monkeypatch.setattr(
        enrichment_jobs,
        "update_report_enrichment_status",
        lambda report_id, status, **kwargs: states.append((status, kwargs)) or {"status": status},
    )
    monkeypatch.setattr(
        enrichment_jobs,
        "get_report_config_snapshot",
        lambda user_id, report_id: {"settings": {"CAREER_ENABLE_COPYWRITER": False}},
    )
    monkeypatch.setattr(
        enrichment_jobs,
        "enrich_career_report",
        lambda user_id, report_id, **_kwargs: {"enrichment_timing_ms": {"total": 12.5}},
    )

    enrichment_jobs._run_enrichment(app, 7, 91, 2)

    assert [state for state, _ in states] == ["running", "completed"]
    assert states[-1][1]["timing_ms"] == {"total": 12.5}
    assert states[0][1]["stage"] == "loading_snapshot"
    assert states[-1][1]["stage"] == "completed"
    assert states[-1][1]["progress"] == 100
    assert all(kwargs["expected_attempt"] == 2 for _, kwargs in states)


def test_background_runner_persists_pipeline_progress_and_quality(app, monkeypatch):
    states = []
    monkeypatch.setattr(
        enrichment_jobs,
        "update_report_enrichment_status",
        lambda report_id, status, **kwargs: states.append((status, kwargs)) or {"status": status},
    )
    monkeypatch.setattr(enrichment_jobs, "get_report_config_snapshot", lambda *_: {"settings": {}})

    def fake_enrich(_user_id, _report_id, **kwargs):
        kwargs["on_progress"]("evidence_retrieved", 30)
        kwargs["on_progress"]("quality_gate_completed", 92)
        return {"enrichment_timing_ms": {"total": 15}, "quality": {"status": "accepted", "score": 96}}

    monkeypatch.setattr(enrichment_jobs, "enrich_career_report", fake_enrich)

    enrichment_jobs._run_enrichment(app, 7, 91, 3)

    assert [(kwargs.get("stage"), kwargs.get("progress")) for _, kwargs in states] == [
        ("loading_snapshot", 3),
        ("evidence_retrieved", 30),
        ("quality_gate_completed", 92),
        ("completed", 100),
    ]
    assert states[-1][1]["quality"] == {"status": "accepted", "score": 96}


def test_background_runner_stops_when_attempt_is_superseded(app, monkeypatch):
    enriched = []
    monkeypatch.setattr(
        enrichment_jobs,
        "update_report_enrichment_status",
        lambda *_args, **_kwargs: {"status": "queued", "superseded": True},
    )
    monkeypatch.setattr(
        enrichment_jobs,
        "enrich_career_report",
        lambda *_args, **_kwargs: enriched.append(True),
    )

    enrichment_jobs._run_enrichment(app, 7, 91, 1)

    assert enriched == []
