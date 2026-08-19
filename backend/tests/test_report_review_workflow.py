from __future__ import annotations

from app.domains.report.review import _evaluate_review_metrics
from app.domains.report.review_workflow import (
    apply_plan_changes,
    apply_change_overrides,
    build_metric_candidates,
    build_plan_diff,
    classify_review_status,
    confirmed_metrics_from_decisions,
)


def test_extracted_values_remain_pending_until_confirmed():
    candidates = build_metric_candidates(
        review_text="项目完成率 75%，交付 2 个成果。",
        metric_definitions=[{"code": "project_completion", "label": "项目完成率", "target": ">=80"}],
        extracted_metrics={"project_completion": 75, "delivery_output": 2},
        extraction_source="deepseek",
    )
    assert all(item["decision"] == "pending" for item in candidates)
    assert candidates[0]["source_text"]
    metrics, audited = confirmed_metrics_from_decisions(
        candidates,
        [{"code": "project_completion", "decision": "confirm", "value": 78}],
    )
    assert metrics == {"project_completion": 78.0}
    assert next(item for item in audited if item["code"] == "delivery_output")["decision"] == "ignore"


def test_unconfirmed_candidates_do_not_enter_evaluation():
    expected = [
        {"code": "project_completion", "target": ">=80"},
        {"code": "delivery_output", "target": ">=2"},
    ]
    result = _evaluate_review_metrics(expected, {"project_completion": 90})
    assert result["evaluated_count"] == 1
    assert result["missing_count"] == 1
    assert result["failed_codes"] == []


def test_review_statuses_cover_real_world_exceptions():
    empty = {"has_evidence": False}
    partial = {"has_evidence": True, "evaluated_count": 2, "pass_rate": 0.5, "all_passed": False}
    assert classify_review_status(empty) == "data_insufficient"
    assert classify_review_status(partial) == "partial"
    assert classify_review_status(partial, signals={"goal_changed": True}) == "goal_changed"
    assert classify_review_status(partial, signals={"planned_hours": 5, "actual_hours": 8}) == "overloaded"
    assert classify_review_status(partial, signals={"evidence_missing": True}) == "evidence_missing"
    action_only = {
        "has_evidence": False,
        "has_action_evidence": True,
        "action_completion_rate": 0.5,
        "evaluated_count": 0,
    }
    assert classify_review_status(action_only) == "partial"
    assert classify_review_status({**action_only, "action_completion_rate": 1.0}) == "on_track"


def test_plan_diff_can_be_partially_applied():
    current = {
        "plans_by_target": [
            {"job_id": "a", "current_plan_month": 1, "next_month_plan": {"items": ["old-a"]}},
            {"job_id": "b", "current_plan_month": 1, "next_month_plan": {"items": ["old-b"]}},
        ],
        "development_lines": {"adjustments": []},
    }
    proposed = {
        "plans_by_target": [
            {"job_id": "a", "current_plan_month": 2, "next_month_plan": {"items": ["new-a"]}},
            {"job_id": "b", "current_plan_month": 2, "next_month_plan": {"items": ["new-b"]}},
        ],
        "development_lines": {"adjustments": [{"id": "adj-a", "target_job_id": "a"}]},
    }
    changes = build_plan_diff(current, proposed, scope="all", job_id=None)
    target_a = next(item for item in changes if item["kind"] == "replace_target_plan" and item["job_id"] == "a")
    applied = apply_plan_changes(current, changes, {target_a["id"]})
    assert applied == [target_a["id"]]
    assert current["plans_by_target"][0]["current_plan_month"] == 2
    assert current["plans_by_target"][1]["current_plan_month"] == 1
    assert current["development_lines"]["adjustments"] == []


def test_user_can_edit_after_payload_without_changing_diff_identity():
    changes = [{"id": "chg_1", "kind": "replace_target_plan", "job_id": "a", "after": {"current_plan_month": 2}}]
    edited = apply_change_overrides(
        changes,
        [{"id": "chg_1", "after": {"current_plan_month": 3}}],
        {"chg_1"},
    )
    assert edited[0]["id"] == "chg_1"
    assert edited[0]["after"]["current_plan_month"] == 3
    assert changes[0]["after"]["current_plan_month"] == 2
