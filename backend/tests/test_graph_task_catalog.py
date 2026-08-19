from __future__ import annotations

import pytest

from app.domains.graph import capability_service, task_registry, task_service


def test_task_catalog_covers_all_queue_operations():
    assert task_registry.TASK_TYPES == {
        "job_import", "job_capability_evaluation", "job_capability_result_import", "job_workstyle_import", "job_workstyle_evaluation",
        "learning_resource_import", "competition_import", "job_promotion_import",
        "job_lateral_import", "promotion_recommendation_import", "salary_normalization",
        "inferred_job_cleanup", "emergency_clear",
    }
    recommendation = task_registry.task_spec("promotion_recommendation_import")
    assert [item.role for item in recommendation.files] == ["learning_file", "competition_file"]
    assert task_registry.task_spec("inferred_job_cleanup").dangerous is True
    assert task_registry.normalize_options("job_capability_evaluation", {"scope": "all", "capability_batch_size": 999})["capability_batch_size"] == 50
    assert task_registry.normalize_options("job_workstyle_evaluation", {"scope": "stale"})["scope"] == "stale"


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
