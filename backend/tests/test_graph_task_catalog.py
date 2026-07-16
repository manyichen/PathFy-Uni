from __future__ import annotations

import pytest

from app.domains.graph import capability_service, services, task_planner, task_registry, task_service
from app.domains.graph.inverse import build_inverse_change_set


def test_task_catalog_covers_all_queue_operations():
    assert task_registry.TASK_TYPES == {
        "job_import", "job_capability_evaluation", "job_capability_result_import",
        "learning_resource_import", "competition_import", "job_promotion_import",
        "job_lateral_import", "promotion_recommendation_import", "salary_normalization",
        "inferred_job_cleanup", "graph_inverse", "emergency_clear",
    }
    recommendation = task_registry.task_spec("promotion_recommendation_import")
    assert [item.role for item in recommendation.files] == ["learning_file", "competition_file"]
    assert task_registry.task_spec("inferred_job_cleanup").dangerous is True
    assert task_registry.normalize_options("job_capability_evaluation", {"scope": "all", "capability_batch_size": 999})["capability_batch_size"] == 50


def test_capability_normalization_requires_all_eight_dimensions():
    raw = {
        "scores": {dim: 60 for dim in capability_service.DIMENSIONS},
        "confidence": {dim: 0.8 for dim in capability_service.DIMENSIONS},
        "evidence": ["岗位描述"], "risk_flags": [],
    }
    normalized = capability_service.normalize_imported_result(raw)
    assert normalized["cap_req_teamwork"] == 60
    assert normalized["cap_conf_growth"] == 0.8
    broken = {**raw, "scores": {"theory": 50}}
    with pytest.raises(ValueError, match="缺少合法维度"):
        capability_service.normalize_imported_result(broken)


def test_capability_review_fusion_is_stable():
    primary = {**{field: 50 for field in capability_service.REQ_FIELDS}, **{field: 0.4 for field in capability_service.CONF_FIELDS}, "cap_evidence": ["p"], "cap_risk_flags": []}
    review = {**{field: 100 for field in capability_service.REQ_FIELDS}, **{field: 0.9 for field in capability_service.CONF_FIELDS}, "cap_evidence": ["r"], "cap_risk_flags": ["low evidence"]}
    merged = capability_service.merge_results(primary, review)
    assert merged["cap_req_theory"] == 80
    assert merged["cap_conf_theory"] == 0.7
    assert merged["cap_fusion"] == "0.4_primary_0.6_review"


def test_capability_batch_requires_one_result_per_job(monkeypatch):
    scores = {dim: 60 for dim in capability_service.DIMENSIONS}
    confidence = {dim: 0.8 for dim in capability_service.DIMENSIONS}
    monkeypatch.setattr(capability_service, "_call_provider", lambda *_args, **_kwargs: {"records": [
        {"job_key": "j1", "scores": scores, "confidence": confidence},
        {"job_key": "j2", "scores": scores, "confidence": confidence},
    ]})
    results = capability_service.evaluate_jobs([{"job_key": "j1"}, {"job_key": "j2"}])
    assert len(results) == 2
    assert all(item["cap_fusion"] == "primary_only" for item in results)

    monkeypatch.setattr(capability_service, "_call_provider", lambda *_args, **_kwargs: {"records": [{"job_key": "j1", "scores": scores, "confidence": confidence}]})
    with pytest.raises(ValueError, match="缺少岗位结果"):
        capability_service.evaluate_jobs([{"job_key": "j1"}, {"job_key": "j2"}])


def test_capability_cache_key_tracks_model_version_and_prompt(monkeypatch):
    scores = {dim: 60 for dim in capability_service.DIMENSIONS}
    confidence = {dim: 0.8 for dim in capability_service.DIMENSIONS}
    cache: dict[tuple, dict] = {}
    identity = ["deepseek+qwen", "v4-flash+qwen", "cap-v2"]
    calls = []

    def load(fingerprint, **kwargs):
        return dict(cache[(fingerprint, *kwargs.values())]) if (fingerprint, *kwargs.values()) in cache else None

    def store(fingerprint, result, _metadata, **kwargs):
        cache[(fingerprint, *kwargs.values())] = dict(result)

    def provider(_provider, payload, **_kwargs):
        calls.append([item["job_key"] for item in payload["jobs"]])
        return {"records": [{"job_key": item["job_key"], "scores": scores, "confidence": confidence} for item in payload["jobs"]]}

    monkeypatch.setattr(capability_service, "_cache_identity", lambda: tuple(identity))
    prompt_version = [capability_service.PROMPT_VERSION + ":test"]
    monkeypatch.setattr(capability_service, "_cache_prompt_version", lambda: prompt_version[0])
    monkeypatch.setattr(capability_service.capability_cache, "load", load)
    monkeypatch.setattr(capability_service.capability_cache, "store", store)
    monkeypatch.setattr(capability_service.capability_cache, "record_metric", lambda **_kwargs: None)
    monkeypatch.setattr(capability_service, "_call_provider", provider)
    payload = {"job_key": "j1", "title": "工程师"}
    first = capability_service.evaluate_jobs([payload])[0]
    second = capability_service.evaluate_jobs([payload])[0]
    assert first["cap_cache_hit"] is False
    assert second["cap_cache_hit"] is True
    assert calls == [["j1"]]
    identity[1] = "v4-pro+qwen"
    capability_service.evaluate_jobs([payload])
    assert calls == [["j1"], ["j1"]]
    assert all(key[-1] == prompt_version[0] for key in cache)
    prompt_version[0] = capability_service.PROMPT_VERSION + ":changed"
    capability_service.evaluate_jobs([payload])
    assert calls == [["j1"], ["j1"], ["j1"]]


def test_capability_missing_batch_records_retry_only_missing_jobs(monkeypatch):
    scores = {dim: 60 for dim in capability_service.DIMENSIONS}
    confidence = {dim: 0.8 for dim in capability_service.DIMENSIONS}
    calls = []

    def provider(_provider, payload, **_kwargs):
        jobs = payload["jobs"]
        calls.append([item["job_key"] for item in jobs])
        selected = jobs[:1]
        return {"records": [{"job_key": item["job_key"], "scores": scores, "confidence": confidence} for item in selected]}

    monkeypatch.setattr(capability_service.capability_cache, "load", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(capability_service.capability_cache, "store", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(capability_service, "_call_provider", provider)
    results = capability_service.evaluate_jobs([{"job_key": "j1"}, {"job_key": "j2"}])
    assert len(results) == 2
    assert calls == [["j1", "j2"], ["j2"]]


def test_property_inverse_restores_all_captured_old_values():
    change = {
        "kind": "salary_normalization",
        "jobs": [{"job_key": "j1", "old": {"salary_norm": "10k", "salary_monthly_min": None}, "new": {"salary_norm": "20k"}}],
    }
    inverse = build_inverse_change_set(change)
    assert inverse == {
        "version": 2, "kind": "graph_inverse", "inverse_of_kind": "salary_normalization",
        "jobs": [{"job_key": "j1", "properties": {"salary_norm": "10k", "salary_monthly_min": None}}],
    }
    assert build_inverse_change_set({"kind": "job_import", "jobs": []}) is None
    assert build_inverse_change_set({"kind": "salary_normalization", "jobs": []}) is None


def test_catalog_exposes_formats_without_secrets():
    items = task_registry.task_catalog()
    job = next(item for item in items if item["task_type"] == "job_import")
    assert job["input_format"].startswith("Excel")
    assert "岗位名称" in job["columns"]
    assert job["files"][0]["extensions"] == [".xls", ".xlsx"]
    assert not any("api_key" in str(item).lower() or "base_url" in str(item).lower() for item in items)


def test_dashboard_quality_query_checks_every_score_confidence_and_fingerprint():
    import inspect

    source = inspect.getsource(services.get_stats)
    for field in (*capability_service.REQ_FIELDS, *capability_service.CONF_FIELDS):
        assert field in source
    assert "cap_input_fingerprint" in source
    assert "GRAPH_CAP_REVIEW_CONFIDENCE_THRESHOLD" in source
    assert "SALARY_PARSE_VERSION" in source


def test_downloadable_task_file_must_stay_in_private_root(app, tmp_path, monkeypatch):
    root = tmp_path / "graph_tasks"
    root.mkdir()
    dataset = root / "task-file.csv"
    dataset.write_text("job_key\n1\n", encoding="utf-8")
    app.config["GRAPH_TASK_UPLOAD_DIR"] = str(root)
    with app.app_context():
        monkeypatch.setattr(task_service.repo, "get_task_file", lambda *_args: {
            "private_path": str(dataset), "original_name": "jobs.csv", "role": "file",
        })
        assert task_service.downloadable_task_file(1, "file")["path"] == str(dataset)

        outside = tmp_path / "outside.csv"
        outside.write_text("secret", encoding="utf-8")
        monkeypatch.setattr(task_service.repo, "get_task_file", lambda *_args: {
            "private_path": str(outside), "original_name": "outside.csv", "role": "file",
        })
        with pytest.raises(task_service.GraphTaskError, match="路径无效"):
            task_service.downloadable_task_file(1, "file")


def test_auto_lateral_planning_covers_more_than_fifty_titles(monkeypatch):
    requested: list[str] = []

    def fake_call(_system, payload, **_kwargs):
        import json

        titles = json.loads(payload)["job_titles"]
        requested.extend(titles)
        return {"pairs": []}

    monkeypatch.setattr(task_planner, "_call_llm_json", fake_call)
    titles = [f"岗位-{index:02d}" for index in range(55)]
    assert task_planner._plan_lateral(titles) == []
    assert requested == titles
