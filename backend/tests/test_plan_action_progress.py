"""下月计划行动项完成状态写回 report_json。"""
from app.domains.report.plan_action_progress import (
    PlanActionProgressError,
    apply_plan_action_done,
    build_stable_action_ref,
    find_plan_action,
    locate_plan_action,
    summarize_plan_action_completion,
    sync_action_progress_to_plans,
)
from app.domains.report.repository import _merge_user_action_state
from app.domains.report import repository
from contextlib import contextmanager


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


def test_review_action_snapshot_counts_persisted_completion():
    report = _sample_report()
    apply_plan_action_done(
        report, job_id="j1", item_index=0, action_index=0, done=True, stamp="2026-08-19 10:00:00"
    )
    snapshot = summarize_plan_action_completion(report, target_job_ids=["j1"])
    assert snapshot["done_count"] == 1
    assert snapshot["total_count"] == 2
    assert snapshot["completion_rate"] == 0.5
    assert snapshot["has_completed_actions"] is True
    assert snapshot["by_target"][0]["plan_month"] == 2


def test_stable_action_ref_uses_action_semantics_instead_of_position():
    action = {"kind": "deliverable", "text": "完成岗位分析报告", "deliverable": "一份 PDF"}
    assert build_stable_action_ref("j1", action) == build_stable_action_ref("j1", dict(action))
    assert build_stable_action_ref("j1", action) != build_stable_action_ref("j2", action)


def test_action_uid_survives_reordering():
    report = _sample_report()
    apply_plan_action_done(report, job_id="j1", item_index=0, action_index=0, done=True)
    uid = report["plans_by_target"][0]["next_month_plan"]["items"][0]["custom_actions"][0]["action_uid"]
    actions = report["plans_by_target"][0]["next_month_plan"]["items"][0]["custom_actions"]
    actions.reverse()
    _, _, action, _, action_index = locate_plan_action(report, job_id="j1", action_uid=uid)
    assert action_index == 1
    assert action["done"] is True


def test_enrichment_merge_keeps_user_edits_and_completion_but_accepts_new_ai_copy():
    previous = {
        "next_month_plan": {"items": [{"focus_dimension": "practice", "custom_actions": [
            {"action_uid": "action:stable", "kind": "practice", "text": "用户修改标题", "deliverable": "旧交付", "done": True,
             "done_at": "2026-08-19 10:00:00", "user_edited_fields": ["text"]}
        ]}]}
    }
    enriched = {
        "next_month_plan": {"items": [{"focus_dimension": "practice", "custom_actions": [
            {"kind": "practice", "text": "AI 新标题", "deliverable": "更具体的新交付"}
        ]}]}
    }
    merged = _merge_user_action_state(previous, enriched, job_id="j1", tombstones=[])
    action = merged["items"][0]["custom_actions"][0]
    assert action["action_uid"] == "action:stable"
    assert action["text"] == "用户修改标题"
    assert action["deliverable"] == "更具体的新交付"
    assert action["done"] is True


def test_action_done_commit_uses_small_json_patch(monkeypatch):
    calls = []

    class Cursor:
        rowcount = 1

        def execute(self, sql, params):
            calls.append((sql, params))

    @contextmanager
    def fake_db_cursor():
        yield object(), Cursor()

    monkeypatch.setattr(repository, "db_cursor", fake_db_cursor)
    saved = repository.commit_action_done_patch(
        user_id=7,
        report_id=12,
        expected_version=3,
        plan_index=1,
        item_index=2,
        action_index=4,
        action_uid='action:v1:abc"quoted',
        progress_key="job|1|2|4",
        done=True,
        done_at="2026-08-19 10:00:00",
        event_type="action_completed",
        action_ref="action:v1:abc",
        payload={"done": True},
    )

    assert saved is True
    update_sql, update_params = calls[0]
    assert "JSON_SET" in update_sql
    assert "report_json=%s" not in update_sql
    assert "$.plans_by_target[1].next_month_plan.items[2].custom_actions[4].done" in update_params
    assert '$.action_progress."action:v1:abc\\"quoted"' in update_params
    assert calls[1][1][1] == "action_completed"


def test_action_done_commit_removes_done_at_when_reopened(monkeypatch):
    calls = []

    class Cursor:
        rowcount = 1

        def execute(self, sql, params):
            calls.append((sql, params))

    @contextmanager
    def fake_db_cursor():
        yield object(), Cursor()

    monkeypatch.setattr(repository, "db_cursor", fake_db_cursor)
    assert repository.commit_action_done_patch(
        user_id=7,
        report_id=12,
        expected_version=4,
        plan_index=0,
        item_index=0,
        action_index=0,
        action_uid="action:v1:abc",
        progress_key="job|1|0|0",
        done=False,
        done_at=None,
        event_type="action_reopened",
        action_ref="action:v1:abc",
        payload={"done": False},
    )
    assert "JSON_REMOVE" in calls[0][0]
    assert calls[0][1][-4] == "$.plans_by_target[0].next_month_plan.items[0].custom_actions[0].done_at"
