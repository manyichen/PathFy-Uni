"""Fixed-sample regression tests for the Phase 2 report quality gate."""
from __future__ import annotations

import copy

from app.domains.report import services
from app.domains.report.enrichment_quality import (
    create_evidence_packet,
    create_input_snapshot,
    gate_enrichment,
    profile_from_snapshot,
    verify_input_snapshot,
)


def _report() -> dict:
    target = {
        "id": "job-1",
        "title": "数据分析师",
        "company": "示例科技",
        "match_preview": {
            "match_score": 78,
            "student_scores": {"cap_req_practice": 55},
            "job_requirement_scores": {"cap_req_practice": 80},
            "dimension_gaps": {"cap_req_practice": 19},
        },
    }
    item = {
        "focus_dimension": "cap_req_practice",
        "focus_label": "实践技能",
        "milestone": "完成一份端到端分析作品并提交 README",
        "learning_path_refs": [{"id": "course-1", "label": "SQL 实战"}],
        "practice_plan_refs": [],
        "custom_actions": [
            {"kind": "learn", "text": "完成 SQL 实战课程 3 个章节并提交一页笔记"},
            {"kind": "practice", "text": "使用真实数据完成一次清洗并记录 3 个问题"},
            {"kind": "deliverable", "text": "提交项目 README、结果截图和可访问链接"},
        ],
    }
    return {
        "generated_at": "2026-08-19 10:00:00",
        "match_goal": "fit",
        "student": {
            "id": 3,
            "display_name": "候选人",
            "scores": {"cap_req_practice": 55},
            "confidences": {"cap_conf_practice": 0.8},
        },
        "targets": [target],
        "recommendations": {
            "by_target": [{
                "job_id": "job-1",
                "learning_resources": [{"resource_id": "course-1", "resource_name": "SQL 实战"}],
                "competitions": [],
            }]
        },
        "plans_by_target": [{
            "job_id": "job-1",
            "display_title": "数据分析师",
            "match_score": 78,
            "phases": {
                "early": {"items": [copy.deepcopy(item)]},
                "mid": {"items": [copy.deepcopy(item)]},
                "late": {"items": [copy.deepcopy(item)]},
            },
            "narrative": {"path_advice": "先完成分析作品，再用 README 和截图验证实践能力。"},
        }],
        "narrative": {"provider": "rules", "text": "先补齐实践能力并完成可核验作品。"},
    }


def _snapshot(report: dict) -> dict:
    return create_input_snapshot(
        report,
        resume_id=3,
        primary_job_id="job-1",
        target_job_ids=["job-1"],
        match_goal="fit",
        settings_revision=8,
        captured_at="2026-08-19 10:00:00",
        constraints={"weekly_hours": 8},
    )


def test_input_snapshot_hash_detects_any_evidence_change():
    report = _report()
    snapshot = _snapshot(report)

    assert verify_input_snapshot(snapshot) is True
    assert profile_from_snapshot(snapshot)["scores"]["cap_req_practice"] == 55

    snapshot["profile"]["scores"]["cap_req_practice"] = 99
    assert verify_input_snapshot(snapshot) is False


def test_retrieved_evidence_packet_is_bound_to_the_input_snapshot():
    report = _report()
    snapshot = _snapshot(report)
    packet = create_evidence_packet(
        report,
        input_snapshot_sha256=snapshot["sha256"],
        collected_at="2026-08-19 10:05:00",
    )

    assert packet["input_snapshot_sha256"] == snapshot["sha256"]
    assert packet["target_facts"][0]["dimension_gaps"]["cap_req_practice"] == 19
    assert packet["resources_by_target"][0]["resources"][0]["id"] == "course-1"
    assert len(packet["sha256"]) == 64


def test_grounded_specific_candidate_passes_without_repair():
    base = _report()
    candidate = copy.deepcopy(base)

    safe, quality = gate_enrichment(base, candidate, _snapshot(base))

    assert quality["status"] == "accepted"
    assert quality["score"] >= 85
    assert safe["plans_by_target"][0]["job_id"] == "job-1"


def test_gate_repairs_vague_actions_unknown_dimensions_and_resource_refs():
    base = _report()
    candidate = copy.deepcopy(base)
    plan = candidate["plans_by_target"][0]
    plan["match_score"] = 999
    plan["phases"]["early"]["items"].append({
        "focus_dimension": "invented_dimension",
        "milestone": "持续提升",
        "custom_actions": [{"kind": "other", "text": "持续提升综合能力"}],
        "learning_path_refs": [{"id": "invented-course", "label": "虚构课程"}],
    })
    valid_item = plan["phases"]["early"]["items"][0]
    valid_item["custom_actions"] = [
        {"kind": "practice", "text": "持续提升综合能力"},
        {"kind": "deliverable", "text": "提交项目 README 和结果截图"},
        {"kind": "deliverable", "text": "提交项目 README 和结果截图"},
    ]
    valid_item["learning_path_refs"].append({"id": "invented-course", "label": "虚构课程"})

    safe, quality = gate_enrichment(base, candidate, _snapshot(base))
    repaired_plan = safe["plans_by_target"][0]
    repaired_item = repaired_plan["phases"]["early"]["items"][0]

    assert quality["status"] == "repaired"
    assert repaired_plan["match_score"] == 78
    assert all(item["focus_dimension"] != "invented_dimension" for item in repaired_plan["phases"]["early"]["items"])
    assert [action["text"] for action in repaired_item["custom_actions"]] == ["提交项目 README 和结果截图"]
    assert {ref["id"] for ref in repaired_item["learning_path_refs"]} == {"course-1"}


def test_gate_rejects_copy_pasted_narratives_across_targets():
    base = _report()
    second_target = copy.deepcopy(base["targets"][0])
    second_target.update({"id": "job-2", "title": "商业分析师", "company": "未来零售"})
    second_target["match_preview"]["match_score"] = 72
    second_plan = copy.deepcopy(base["plans_by_target"][0])
    second_plan.update({"job_id": "job-2", "display_title": "商业分析师", "match_score": 72})
    second_plan["narrative"]["path_advice"] = "面向商业分析岗位，提交一份业务复盘报告和结论页。"
    base["targets"].append(second_target)
    base["plans_by_target"].append(second_plan)
    candidate = copy.deepcopy(base)
    duplicated = "完成一个项目并提交 README、截图和复盘记录。"
    for plan in candidate["plans_by_target"]:
        plan["narrative"]["path_advice"] = duplicated
    snapshot = create_input_snapshot(
        base, resume_id=3, primary_job_id="job-1", target_job_ids=["job-1", "job-2"],
        match_goal="fit", settings_revision=8, captured_at="2026-08-19 10:00:00",
    )

    safe, quality = gate_enrichment(base, candidate, snapshot)

    assert quality["status"] == "repaired"
    assert quality["initial_score"] <= 84
    assert safe["plans_by_target"][0]["narrative"]["path_advice"] != safe["plans_by_target"][1]["narrative"]["path_advice"]


def test_gate_falls_back_to_rules_when_even_repair_has_no_usable_content():
    base = {
        "student": {"id": 3},
        "targets": [{"id": "job-1", "match_preview": {"match_score": 0}}],
        "plans_by_target": [],
    }
    snapshot = _snapshot(_report())

    safe, quality = gate_enrichment(base, {}, snapshot)

    assert quality["status"] == "fallback"
    assert quality["initial_score"] < 70
    assert safe["llm_enrich_pending"] is False


def test_enrichment_uses_frozen_profile_instead_of_latest_profile(monkeypatch):
    report = _report()
    report["input_snapshot"] = _snapshot(report)
    captured = {}
    monkeypatch.setattr(services, "fetch_report_row", lambda *_: {
        "id": 9, "resume_id": 3, "primary_job_id": "job-1", "target_job_ids_json": ["job-1"],
        "settings_revision": 8, "report_json": copy.deepcopy(report),
    })
    monkeypatch.setattr(services, "_load_profile", lambda *_: (_ for _ in ()).throw(AssertionError("latest profile must not be loaded")))
    monkeypatch.setattr(services, "build_graph_recommendations", lambda *_args, **_kwargs: copy.deepcopy(report["recommendations"]))
    monkeypatch.setattr(services, "enrich_growth_plan_with_recommendations", lambda *_: None)
    monkeypatch.setattr(services, "build_plans_by_target", lambda *_: copy.deepcopy(report["plans_by_target"]))
    monkeypatch.setattr(services, "bind_plan_line_ids", lambda *_: None)
    monkeypatch.setattr(services, "build_custom_plan_actions_batch", lambda *_args, **_kwargs: {"ok": False, "reason": "disabled"})
    monkeypatch.setattr(services, "augment_plans_narrative_with_doubao", lambda *_: {"ok": False, "reason": "disabled"})
    monkeypatch.setattr(services, "setting", lambda *_args, **_kwargs: True)

    def fake_summary(*, profile, **_kwargs):
        captured["profile"] = copy.deepcopy(profile)
        return {"provider": "test", "text": "基于冻结画像生成。"}

    monkeypatch.setattr(services, "_build_llm_summary", fake_summary)
    monkeypatch.setattr(services, "ensure_next_month_plans_for_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(services, "sync_action_progress_to_plans", lambda *_: None)
    monkeypatch.setattr(services, "merge_report_enrichment", lambda _report_id, enriched, **_kwargs: enriched)

    result = services.enrich_career_report(7, 9)

    assert captured["profile"]["scores"]["cap_req_practice"] == 55
    assert result["report"]["input_snapshot"]["sha256"] == report["input_snapshot"]["sha256"]
