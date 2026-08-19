"""Correctness contracts for evidence-aware and scoped career reviews."""
from __future__ import annotations

import pytest

from app.domains.report import router, services
from app.domains.report.review import (
    _evaluate_review_metrics,
    _heuristic_extract_metrics_from_text,
    _llm_extract_metrics_from_text,
)


def test_legacy_confirmed_review_recovers_missing_next_month_plan(monkeypatch):
    report = {
        "plans_by_target": [{"job_id": "j1", "current_plan_month": 1, "next_month_plan": {"plan_month": 1}}],
        "development_lines": {"lines": [{"line_id": "line-1", "target_job_id": "j1", "timeline": []}], "adjustments": []},
        "evaluation": {},
    }
    reviews = [{"review_id": 8, "review_cycle": "monthly", "scope": "target", "job_id": "j1", "metrics": {"submitted": {}, "evaluation": {}}}]
    saved = {}

    monkeypatch.setattr(services, "list_plan_version_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(services, "_build_auto_adjustment", lambda *_args, **_kwargs: {"triggered": True, "replan_mode": "continue"})

    def fake_apply(candidate, _adjustment, **kwargs):
        plan = candidate["plans_by_target"][0]
        plan["current_plan_month"] = 2
        plan["next_month_plan"] = {"plan_month": 2, "review_anchor_month": int(kwargs["review_anchor_month"]), "items": []}

    monkeypatch.setattr(services, "_apply_auto_adjustment_to_report", fake_apply)

    def fake_update(**kwargs):
        saved.update(kwargs)
        return True

    monkeypatch.setattr(services, "update_report_json_if_version", fake_update)
    repaired = services._repair_missing_monthly_follow_up(
        user_id=3,
        report_id=9,
        report_version=4,
        report_obj=report,
        reviews_asc=reviews,
    )

    assert repaired["plans_by_target"][0]["next_month_plan"]["plan_month"] == 2
    assert repaired["plans_by_target"][0]["next_month_plan"]["review_anchor_month"] == 1
    assert saved["expected_version"] == 4


def test_missing_metric_is_not_zero_or_failed():
    result = _evaluate_review_metrics(
        [
            {"code": "project_completion", "label": "项目完成率", "target": ">= 80"},
            {"code": "delivery_output", "label": "成果数量", "target": ">= 2"},
        ],
        {"project_completion": 90},
    )

    missing = next(row for row in result["rows"] if row["code"] == "delivery_output")
    assert missing["actual_value"] is None
    assert missing["passed"] is None
    assert missing["status"] == "missing"
    assert "delivery_output" not in result["failed_codes"]
    assert result["pass_rate"] == 1.0
    assert result["evaluated_count"] == 1
    assert result["evidence_complete"] is False
    assert result["all_passed"] is False


def test_qualitative_review_does_not_invent_zero_metrics():
    metrics = _heuristic_extract_metrics_from_text("本月完成了学习，但还没有整理量化记录。")
    assert metrics == {}


def test_review_metric_parser_keeps_output_count_bound_to_its_phrase():
    metrics = _heuristic_extract_metrics_from_text(
        "本月项目完成率达到70%，新增1个可展示成果，投入28小时。"
    )
    assert metrics["project_completion"] == 70
    assert metrics["delivery_output"] == 1


def test_numeric_review_uses_fast_local_extraction(monkeypatch):
    def unexpected_call(**_kwargs):
        raise AssertionError("numeric review should not call the external model")

    monkeypatch.setattr("app.domains.report.review._call_openai_compatible", unexpected_call)
    result = _llm_extract_metrics_from_text(
        report_obj={"evaluation": {"metrics": []}},
        review_text="项目完成率 75%，交付 2 个成果。",
        review_cycle="monthly",
    )
    assert result["source"] == "heuristic"
    assert result["metrics"] == {"project_completion": 75.0, "delivery_output": 2.0}


def test_review_uses_saved_job_snapshot_without_graph(monkeypatch):
    def graph_unavailable(_job_ids):
        raise AssertionError("saved target snapshots should avoid Neo4j")

    monkeypatch.setattr(services, "_query_jobs_by_ids", graph_unavailable)
    report = {
        "targets": [
            {
                "id": "job-1",
                "scores": {"cap_req_practice": 80},
                "confidences": {"cap_req_practice": 0.9},
            }
        ]
    }
    cards = services._review_job_cards(report, ["job-1"])
    assert cards == report["targets"]


def test_review_graph_failure_degrades_to_available_snapshots(app, monkeypatch):
    monkeypatch.setattr(
        services,
        "_query_jobs_by_ids",
        lambda _job_ids: (_ for _ in ()).throw(RuntimeError("graph offline")),
    )
    with app.app_context():
        cards = services._review_job_cards(
            {"targets": [{"id": "job-1", "scores": {}, "confidences": {}}]},
            ["job-1", "job-2"],
        )
    assert [card["id"] for card in cards] == ["job-1"]


def test_primary_target_must_belong_to_target_set(monkeypatch):
    monkeypatch.setattr(services, "_load_profile", lambda *_args: {})

    with pytest.raises(services.ReportServiceError, match="primary_job_id") as error:
        services.generate_career_report(
            7,
            {
                "resume_id": 1,
                "target_job_ids": ["job-1"],
                "primary_job_id": "job-2",
                "skip_llm_enrich": True,
            },
        )

    assert error.value.status == 400


def test_target_discovery_requires_authentication(client):
    assert client.post("/api/report/targets/manual-search", json={"q": "数据"}).status_code == 401
    assert client.get("/api/report/targets/random-browse").status_code == 401


def test_unexpected_report_error_does_not_leak_details(client, monkeypatch):
    monkeypatch.setattr(router, "_require_user", lambda: (7, None))
    monkeypatch.setattr(router, "_rate_limited", lambda *_args, **_kwargs: None)

    def fail(_body):
        raise RuntimeError("mysql password=super-secret")

    monkeypatch.setattr(router, "manual_search_targets", fail)
    response = client.post("/api/report/targets/manual-search", json={"q": "数据"})

    assert response.status_code == 500
    assert "super-secret" not in response.get_json()["message"]
