from __future__ import annotations

import pytest

from app.domains.graph import capability_service, task_registry


def test_task_catalog_covers_all_queue_operations():
    assert task_registry.TASK_TYPES == {
        "job_import", "job_capability_evaluation", "job_capability_result_import",
        "learning_resource_import", "competition_import", "job_promotion_import",
        "job_lateral_import", "promotion_recommendation_import", "salary_normalization",
        "inferred_job_cleanup", "emergency_clear",
    }
    recommendation = task_registry.task_spec("promotion_recommendation_import")
    assert [item.role for item in recommendation.files] == ["learning_file", "competition_file"]
    assert task_registry.task_spec("inferred_job_cleanup").dangerous is True


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
