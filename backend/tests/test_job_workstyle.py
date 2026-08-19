import json

from app.domains.jobs.workstyle import build_job_workstyle


def test_job_axis_overrides_title_and_missing_axis_inherits_with_provenance():
    job = {
        "workstyle_interaction": 80,
        "workstyle_conf_interaction": 0.9,
        "workstyle_source": "job-description",
        "workstyle_evidence_json": json.dumps({"interaction_intensity": [{"text": "频繁跨团队沟通"}]}),
    }
    title = {
        "workstyle_interaction": 20,
        "workstyle_conf_interaction": 0.7,
        "workstyle_structure": 75,
        "workstyle_conf_structure": 0.8,
        "workstyle_source": "reviewed-title-template",
        "workstyle_evidence_json": json.dumps({
            "interaction_intensity": [{"text": "岗位族互动证据"}],
            "structure_preference": [{"text": "流程和里程碑明确"}],
        }),
    }
    result = build_job_workstyle(job, title)
    axes = {axis["code"]: axis for axis in result["axes"]}
    assert axes["interaction_intensity"]["value"] == 80
    assert axes["interaction_intensity"]["inherited_from_job_title"] is False
    assert axes["structure_preference"]["value"] == 75
    assert axes["structure_preference"]["inherited_from_job_title"] is True


def test_unproven_or_out_of_range_axis_is_not_serialized():
    result = build_job_workstyle({
        "workstyle_interaction": 120,
        "workstyle_conf_interaction": 0.9,
        "workstyle_abstraction": 70,
        "workstyle_conf_abstraction": 0.8,
        "workstyle_evidence_json": "{}",
    })
    assert result["axes"] == []
    assert result["status"] == "insufficient_evidence"
