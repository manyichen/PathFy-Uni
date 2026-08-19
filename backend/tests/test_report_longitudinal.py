from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.domains.report import services as report_services
from app.domains.report.longitudinal import (
    build_execution_profile,
    build_layered_freshness,
    build_longitudinal_insights,
    build_longitudinal_trends,
    build_personalization,
)


NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)


def test_profile_change_after_snapshot_is_outdated_not_silently_fresh():
    result = build_layered_freshness(
        {"input_snapshot": {"captured_at": "2026-08-01T00:00:00Z"}},
        report_created_at="2026-08-01T00:00:00Z",
        report_updated_at="2026-08-10T00:00:00Z",
        profile_updated_at="2026-08-15T00:00:00Z",
        latest_review_at="2026-08-18T00:00:00Z",
        latest_plan_at="2026-08-18T00:00:00Z",
        now=NOW,
    )
    assert result["domains"]["profile"]["status"] == "outdated"
    assert "profile" in result["stale_domains"]


def test_execution_profile_uses_confirmed_reviews_and_action_events_only():
    report = {"plans_by_target": [{"next_month_plan": {"items": [{"custom_actions": [{"text": "交付作品", "done": True}, {"text": "模拟面试", "done": False}]}]}}]}
    reviews = [{"id": 1, "metrics_json": {"review_status": "overloaded"}, "adjustment_json": {}}]
    events = [{"event_type": "action_completed", "payload_json": {"title": "交付作品"}}]
    result = build_execution_profile(report, reviews, events)
    assert result["diagnosis"] == "time_capacity"
    assert result["confirmed_review_count"] == 1
    assert result["current_completion_rate"] == 0.5
    assert result["evidence_points"] == 2


def test_plan_stability_and_acceptance_use_decided_proposals():
    versions = [
        {"status": "accepted", "diff_json": [{"id": "a"}, {"id": "b"}], "decision_json": {"accepted_change_ids": ["a"]}},
        {"status": "rejected", "diff_json": [{"id": "c"}], "decision_json": {}},
        {"status": "proposed", "diff_json": [{"id": "d"}], "decision_json": {}},
    ]
    result = build_longitudinal_trends([], versions)
    assert result["proposal_acceptance_rate"] == 0.5
    assert result["partial_accept_count"] == 1
    assert result["decided_proposal_count"] == 2


def test_personalization_is_conservative_with_low_completion():
    result = build_personalization(
        {"diagnosis": "execution_stalled", "current_completion_rate": 0.2, "evidence_points": 5, "confidence": "medium", "confirmed_review_count": 2, "action_event_count": 3},
        {"decided_proposal_count": 1},
        enabled=True,
        variant="personalized_v1",
        weekly_hours_hint=10,
    )
    assert result["recommendation_active"] is True
    assert result["suggested_weekly_action_limit"] == 2
    assert result["suggested_weekly_hours"] == 7.0
    assert "未确认候选指标" in result["learned_from"]["excluded"]


def test_longitudinal_output_declares_learning_boundary():
    result = build_longitudinal_insights(
        {"plans_by_target": []},
        report_created_at="2026-08-01T00:00:00Z",
        report_updated_at="2026-08-02T00:00:00Z",
        profile_updated_at="2026-08-01T00:00:00Z",
        review_rows=[],
        plan_version_rows=[],
        action_event_rows=[],
        personalization_enabled=True,
        experiment_variant="baseline",
        now=NOW,
    )
    assert result["schema_version"] == 1
    assert result["personalization"]["recommendation_active"] is False
    assert result["privacy"]["unconfirmed_draft_retention_days"] == 90


def test_operations_metrics_normalizes_variant_counts_and_rates(monkeypatch):
    monkeypatch.setattr(
        report_services,
        "report_operations_metrics",
        lambda: {
            "draft_count": 4,
            "confirmed_draft_count": 3,
            "proposal_count": 2,
            "accepted_proposal_count": 1,
            "experiments": [{
                "experiment_key": "career_pacing_v1",
                "variant": "personalized_v1",
                "assignments": 4,
                "activated_reports": Decimal("3"),
                "review_count": Decimal("5"),
                "proposal_count": Decimal("2"),
                "accepted_proposal_count": Decimal("1"),
                "completion_event_count": Decimal("6"),
            }],
        },
    )
    result = report_services.get_career_report_operations_metrics()
    variant = result["experiments"][0]
    assert variant["activation_rate"] == 0.75
    assert variant["proposal_acceptance_rate"] == 0.5
    assert variant["completion_events_per_assignment"] == 1.5
    assert isinstance(variant["review_count"], int)


def test_delete_report_requires_matching_explicit_confirmation(monkeypatch):
    calls = []
    monkeypatch.setattr(report_services, "delete_user_report", lambda user_id, report_id: calls.append((user_id, report_id)) or True)

    try:
        report_services.delete_career_report(7, 42, {"confirm_report_id": 41})
        assert False, "expected confirmation mismatch"
    except report_services.ReportServiceError as exc:
        assert exc.status == 400
    assert calls == []

    result = report_services.delete_career_report(7, 42, {"confirm_report_id": 42})
    assert calls == [(7, 42)]
    assert result == {"report_id": 42, "deleted": True, "recoverable": False}
