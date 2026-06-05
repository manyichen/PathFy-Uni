"""分岗动态规划：阶段月份与下月计划写回。"""
from app.domains.report.replan_by_target import (
    build_next_month_plan_for_job,
    ensure_next_month_plans_for_report,
    phase_key_for_plan_month,
    pick_items_for_plan_month,
    resolve_replan_mode,
    seed_month_zero_from_plans,
)


def _sample_plan():
    return {
        "job_id": "j1",
        "phases": {
            "early": {
                "items": [
                    {
                        "order": 1,
                        "focus_dimension": "cap_req_digital",
                        "focus_label": "数字",
                        "milestone": "完成入门",
                        "learning_path_refs": [{"id": "r1", "label": "课A", "url": "http://a"}],
                    },
                    {
                        "order": 2,
                        "focus_dimension": "cap_req_practice",
                        "focus_label": "实践",
                        "milestone": "小项目",
                    },
                ]
            },
            "mid": {
                "items": [
                    {
                        "focus_dimension": "cap_req_practice",
                        "focus_label": "实践",
                        "milestone": "岗位项目",
                    }
                ]
            },
            "late": {"items": []},
        },
        "recommendations": {"learning_resources": [], "competitions": []},
    }


def test_phase_key_for_plan_month():
    assert phase_key_for_plan_month(1) == "early"
    assert phase_key_for_plan_month(3) == "early"
    assert phase_key_for_plan_month(4) == "mid"
    assert phase_key_for_plan_month(10) == "late"


def test_resolve_replan_mode():
    assert resolve_replan_mode(all_passed=True, failed_codes=[], consecutive_fail_months=0) == "continue"
    assert resolve_replan_mode(all_passed=False, failed_codes=["x"], consecutive_fail_months=1) == "light"
    assert resolve_replan_mode(all_passed=False, failed_codes=["x"], consecutive_fail_months=2) == "strong"


def test_build_next_month_plan_uses_mid_phase():
    plan = _sample_plan()
    nmp = build_next_month_plan_for_job(plan, plan_month=5, replan_mode="continue", global_actions=[])
    assert nmp["phase_key"] == "mid"
    assert nmp["items"][0]["milestone"] == "岗位项目"
    assert nmp["items"][0].get("custom_actions")
    assert len(nmp["items"][0]["custom_actions"]) >= 3
    assert nmp["items"][0].get("growth_rationale")


def test_build_next_month_plan_light_includes_remediation():
    plan = _sample_plan()
    failed = [{"code": "delivery_output", "label": "成果", "passed": False}]
    nmp = build_next_month_plan_for_job(
        plan,
        plan_month=2,
        replan_mode="light",
        global_actions=[],
        failed_rows=failed,
    )
    primary = nmp["items"][0]
    assert primary.get("metric_target_labels") or not any(
        "delivery_output" in str(a.get("text", "")) for a in (primary.get("custom_actions") or [])
    )
    assert len(primary.get("custom_actions") or []) >= 3


def test_ensure_next_month_plans_for_report_fills_missing():
    report = {"plans_by_target": [_sample_plan()]}
    ensure_next_month_plans_for_report(report, stamp="t2")
    plan = report["plans_by_target"][0]
    assert plan.get("next_month_plan", {}).get("items")
    assert plan["next_month_plan"]["plan_month"] == 1


def test_seed_month_zero_writes_per_line():
    report = {
        "plans_by_target": [_sample_plan()],
        "development_lines": {
            "lines": [
                {
                    "line_id": "line_1",
                    "target_job_id": "j1",
                    "line_name": "Java · 甲公司",
                }
            ],
            "adjustments": [],
        },
    }
    seed_month_zero_from_plans(report, stamp="t1")
    plan = report["plans_by_target"][0]
    assert plan.get("next_month_plan")
    assert plan["next_month_plan"]["plan_month"] == 1
    adjs = report["development_lines"]["adjustments"]
    assert len(adjs) == 1
    assert adjs[0]["target_job_id"] == "j1"
    assert adjs[0]["kind"] == "initial_plan"
    assert adjs[0]["month"] == 0.0
    assert len(adjs[0].get("plan_items") or []) >= 1
