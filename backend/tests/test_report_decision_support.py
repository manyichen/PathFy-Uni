"""Career Report V2 deterministic decision/evidence contract."""
from __future__ import annotations

from app.domains.report.decision_support import build_decision_support


def _report() -> dict:
    scores = {
        "cap_req_practice": 55,
        "cap_req_digital": 82,
        "cap_req_teamwork": 70,
    }
    confidences = {
        "cap_conf_practice": 0.8,
        "cap_conf_digital": 0.9,
        "cap_conf_teamwork": 0.7,
    }
    return {
        "generated_at": "2026-08-19 10:00:00",
        "student": {"scores": scores, "confidences": confidences},
        "targets": [
            {
                "id": "job-1",
                "title": "数据分析师",
                "company": "示例科技",
                "match_preview": {
                    "match_score": 78,
                    "student_scores": scores,
                    "job_requirement_scores": {
                        "cap_req_practice": 80,
                        "cap_req_digital": 75,
                        "cap_req_teamwork": 65,
                    },
                    "dimension_gaps": {"cap_req_practice": 19, "cap_req_digital": 0, "cap_req_teamwork": 0},
                },
            },
            {
                "id": "job-2",
                "title": "商业分析师",
                "company": "未来零售",
                "match_preview": {
                    "match_score": 73,
                    "student_scores": scores,
                    "job_requirement_scores": {
                        "cap_req_practice": 78,
                        "cap_req_digital": 70,
                        "cap_req_teamwork": 76,
                    },
                    "dimension_gaps": {"cap_req_practice": 17, "cap_req_teamwork": 6},
                },
            },
        ],
        "plans_by_target": [
            {
                "job_id": "job-1",
                "next_month_plan": {
                    "plan_month": 1,
                    "items": [
                        {
                            "focus_dimension": "cap_req_practice",
                            "focus_label": "实践技能",
                            "milestone": "完成端到端分析作品",
                            "custom_actions": [
                                {"kind": "practice", "text": "完成一次真实数据清洗与分析"},
                                {"kind": "deliverable", "text": "提交项目 README 和结果截图"},
                            ],
                        }
                    ],
                },
            },
            {
                "job_id": "job-2",
                "next_month_plan": {
                    "plan_month": 1,
                    "items": [
                        {
                            "focus_dimension": "cap_req_practice",
                            "focus_label": "实践技能",
                            "milestone": "完成业务复盘",
                            "custom_actions": [{"kind": "deliverable", "text": "输出一页业务结论"}],
                        }
                    ],
                },
            },
        ],
    }


def test_builds_grounded_claim_action_and_acceptance_chain():
    support = build_decision_support(_report(), primary_job_id="job-1")
    primary = support["target_decisions"][0]

    assert support["schema_version"] == 2
    assert primary["role"] == "primary"
    assert primary["claims"][0]["fact_refs"]
    assert primary["claims"][0]["facts"][0]["evidence_grade"] == "B"
    assert primary["actions"][0]["deliverable"] == "提交项目 README 和结果截图"
    assert len(primary["actions"][0]["acceptance_criteria"]) == 3
    assert primary["actions"][0]["effort_hours"] > 0


def test_builds_target_roles_comparison_and_shared_focus():
    support = build_decision_support(_report(), primary_job_id="job-1")

    assert [item["role"] for item in support["target_decisions"]] == ["primary", "alternative"]
    assert len(support["target_comparison"]) == 2
    assert support["shared_actions"][0]["dimension"] == "cap_req_practice"
    assert support["shared_actions"][0]["target_count"] == 2


def test_action_completion_survives_decision_model_refresh():
    report = _report()
    report["plans_by_target"][0]["next_month_plan"]["items"][0]["custom_actions"][0]["done"] = True

    support = build_decision_support(report, primary_job_id="job-1")

    assert support["target_decisions"][0]["actions"][0]["status"] == "done"
    assert support["target_decisions"][0]["actions"][0]["done"] is True


def test_only_positive_gaps_and_actual_strengths_are_claimed():
    report = _report()
    support = build_decision_support(report, primary_job_id="job-1")
    claims = support["target_decisions"][0]["claims"]

    gap_dimensions = {claim["dimension"] for claim in claims if claim["kind"] == "gap"}
    strength_dimensions = {claim["dimension"] for claim in claims if claim["kind"] == "strength"}

    assert gap_dimensions == {"cap_req_practice"}
    assert strength_dimensions == {"cap_req_digital", "cap_req_teamwork"}


def test_all_decision_references_resolve_inside_the_target_unit():
    support = build_decision_support(_report(), primary_job_id="job-1")

    for decision in support["target_decisions"]:
        claim_ids = {claim["id"] for claim in decision["claims"]}
        for claim in decision["claims"]:
            fact_ids = {fact["id"] for fact in claim["facts"]}
            assert set(claim["fact_refs"]) <= fact_ids
        for action in decision["actions"]:
            assert set(action["source_claim_ids"]) <= claim_ids


def test_raw_delta_inside_soft_margin_is_exposed_as_risk_not_hidden():
    report = _report()
    report["student"]["scores"] = {"cap_req_digital": 70}
    report["student"]["confidences"] = {"cap_conf_digital": 0.9}
    report["targets"] = [report["targets"][0]]
    report["targets"][0]["match_preview"].update(
        {
            "student_scores": {"cap_req_digital": 70},
            "job_requirement_scores": {"cap_req_digital": 78},
            "dimension_raw_delta": {"cap_req_digital": 8},
            "dimension_gaps": {"cap_req_digital": 0},
        }
    )
    report["plans_by_target"] = [report["plans_by_target"][0]]
    report["plans_by_target"][0]["next_month_plan"]["items"][0]["focus_dimension"] = "cap_req_digital"
    report["plans_by_target"][0]["next_month_plan"]["items"][0]["focus_label"] = "数字素养"

    support = build_decision_support(report, primary_job_id="job-1")
    decision = support["target_decisions"][0]
    risk = next(claim for claim in decision["claims"] if claim["kind"] == "risk")

    assert risk["dimension"] == "cap_req_digital"
    assert "低于岗位标尺" in risk["title"]
    assert support["target_comparison"][0]["top_gap"] != "数据不足"
    assert not any(claim["kind"] == "strength" for claim in decision["claims"])


def test_evidence_coverage_penalizes_actions_without_resolvable_claims():
    report = _report()
    item = report["plans_by_target"][0]["next_month_plan"]["items"][0]
    item["focus_dimension"] = "cap_req_cross"
    item["focus_label"] = "交叉能力"

    decision = build_decision_support(report, primary_job_id="job-1")["target_decisions"][0]
    metrics = decision["evidence_metrics"]

    assert metrics["unlinked_action_count"] == len(decision["actions"])
    assert metrics["action_traceability"] == 0
    assert metrics["coverage"] < 1
