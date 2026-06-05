"""下月计划行动项完成状态写回 report_json。"""
from app.domains.report.plan_action_progress import (
    PlanActionProgressError,
    apply_plan_action_done,
    find_plan_action,
    sync_action_progress_to_plans,
)


def _sample_report():
    return {
        "plans_by_target": [
            {
                "job_id": "j1",
                "next_month_plan": {
                    "plan_month": 2,
                    "items": [
                        {
                            "focus_dimension": "cap_req_digital",
                            "custom_actions": [
                                {"kind": "learn", "text": "学 Java"},
                                {"kind": "practice", "text": "做小项目"},
                            ],
                        }
                    ],
                },
            }
        ]
    }


def test_apply_plan_action_done_marks_complete():
    report = _sample_report()
    out = apply_plan_action_done(
        report,
        job_id="j1",
        item_index=0,
        action_index=0,
        done=True,
        stamp="2026-06-05 10:00:00",
    )
    assert out["done"] is True
    assert out["done_at"] == "2026-06-05 10:00:00"
    _, act = find_plan_action(report, job_id="j1", item_index=0, action_index=0)
    assert act["done"] is True


def test_apply_plan_action_done_uncheck_clears_done_at():
    report = _sample_report()
    apply_plan_action_done(
        report, job_id="j1", item_index=0, action_index=1, done=True, stamp="2026-06-05 10:00:00"
    )
    apply_plan_action_done(report, job_id="j1", item_index=0, action_index=1, done=False)
    _, act = find_plan_action(report, job_id="j1", item_index=0, action_index=1)
    assert act.get("done") is False
    assert "done_at" not in act


def test_apply_plan_action_done_unknown_job():
    report = _sample_report()
    try:
        apply_plan_action_done(report, job_id="missing", item_index=0, action_index=0, done=True)
        assert False, "expected error"
    except PlanActionProgressError as exc:
        assert "不存在" in str(exc)


def test_sync_action_progress_to_plans():
    report = _sample_report()
    report["action_progress"] = {
        "j1|2|0|1": {"done": True, "done_at": "2026-06-05 12:00:00"},
    }
    sync_action_progress_to_plans(report)
    _, act = find_plan_action(report, job_id="j1", item_index=0, action_index=1)
    assert act["done"] is True
    assert act["done_at"] == "2026-06-05 12:00:00"


def test_apply_plan_action_done_writes_action_progress():
    report = _sample_report()
    out = apply_plan_action_done(
        report, job_id="j1", item_index=0, action_index=0, done=True, stamp="2026-06-05 10:00:00"
    )
    assert out["progress_key"] == "j1|2|0|0"
    assert report["action_progress"]["j1|2|0|0"]["done"] is True
