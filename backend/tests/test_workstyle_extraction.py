import json

from app.domains.jobs.workstyle_extraction import WORKSTYLE_TEXT_VERSION, extract_workstyle_profile


def test_explicit_job_text_generates_versioned_axes_and_source_snippets():
    result = extract_workstyle_profile({
        "demand": "需要跨团队协作和客户沟通，使用数据分析支持指标体系，并按项目计划和里程碑交付。",
        "company_detail": "",
        "experience": "",
    })
    evidence = json.loads(result["workstyle_evidence_json"])
    assert result["workstyle_scoring_version"] == WORKSTYLE_TEXT_VERSION
    assert result["workstyle_interaction"] > 50
    assert result["workstyle_analytical"] > 50
    assert result["workstyle_structure"] > 50
    assert evidence["interaction_intensity"][0]["source"] == "job_description"


def test_job_title_alone_never_creates_a_stereotyped_profile():
    result = extract_workstyle_profile({"title": "销售经理", "demand": "", "company_detail": "", "experience": ""})
    assert "workstyle_interaction" not in result
    assert json.loads(result["workstyle_evidence_json"]) == {}


def test_conflicting_signals_stay_near_the_middle_instead_of_hiding_evidence():
    result = extract_workstyle_profile({"demand": "既要独立分析，也要跨部门推进。"})
    assert result["workstyle_interaction"] == 50
    assert result["workstyle_conf_interaction"] > 0.5
