import json

import pytest

from app.domains.graph import task_planner


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, query, **_params):
        if "MATCH (j:Job)" in query:
            return [{"key": "job-1"}]
        if "MATCH (jt:JobTitle)" in query:
            return [{"name": "数据分析师"}]
        return []


class FakeDriver:
    def session(self, **_kwargs):
        return FakeSession()


class EvaluationSession(FakeSession):
    def run(self, _query, **_params):
        return [{
            "job_key": "job-1", "title": "数据分析师",
            "demand": "需要跨部门沟通，使用数据分析支持指标体系，并按项目计划交付。",
            "company_detail": "", "experience": "",
            "workstyle_scoring_version": None, "workstyle_input_fingerprint": None,
            "workstyle_interaction": None, "workstyle_abstraction": None,
            "workstyle_analytical": None, "workstyle_structure": None,
        }]


class EvaluationDriver:
    def session(self, **_kwargs):
        return EvaluationSession()


def _row():
    return {
        "target_type": "job",
        "target_id": "job-1",
        "workstyle_source": "reviewed-job-description",
        "workstyle_scoring_version": "workstyle-evidence-v1",
        "workstyle_evidence_json": json.dumps({
            "interaction_intensity": [{"text": "需要每周参与客户访谈"}],
            "structure_preference": [{"text": "采用固定双周迭代"}],
        }, ensure_ascii=False),
        "workstyle_interaction": "75",
        "workstyle_conf_interaction": "0.85",
        "workstyle_abstraction": "",
        "workstyle_conf_abstraction": "",
        "workstyle_analytical": "",
        "workstyle_conf_analytical": "",
        "workstyle_structure": "70",
        "workstyle_conf_structure": "0.8",
    }


def _prepare(monkeypatch, row):
    monkeypatch.setattr(task_planner, "_read_csv", lambda *_args, **_kwargs: [row])
    monkeypatch.setattr(task_planner, "_driver", lambda: (FakeDriver(), "neo4j"))


def test_workstyle_import_builds_a_reviewable_versioned_change_set(monkeypatch):
    _prepare(monkeypatch, _row())
    change, summary = task_planner.plan_workstyle_import({"source_id": "manual-review"})
    assert change["kind"] == "job_workstyle_import"
    assert change["items"][0]["properties"]["workstyle_interaction"] == 75
    assert change["items"][0]["properties"]["workstyle_conf_structure"] == 0.8
    assert summary["jobs"] == 1


def test_workstyle_import_rejects_an_axis_without_evidence(monkeypatch):
    row = _row()
    row["workstyle_evidence_json"] = "{}"
    _prepare(monkeypatch, row)
    with pytest.raises(task_planner.TaskPlanningError, match="缺少可审计证据"):
        task_planner.plan_workstyle_import({})


def test_workstyle_import_rejects_out_of_range_values(monkeypatch):
    row = _row()
    row["workstyle_conf_interaction"] = "1.2"
    _prepare(monkeypatch, row)
    with pytest.raises(task_planner.TaskPlanningError, match="超出"):
        task_planner.plan_workstyle_import({})


def test_workstyle_evaluation_extracts_only_text_supported_axes_for_review(monkeypatch):
    monkeypatch.setattr(task_planner, "_driver", lambda: (EvaluationDriver(), "neo4j"))
    change, summary = task_planner.plan_workstyle_evaluation({"options": {"scope": "missing"}})
    assert change["kind"] == "job_workstyle_evaluation"
    properties = change["items"][0]["properties"]
    assert properties["workstyle_interaction"] > 50
    assert properties["workstyle_analytical"] > 50
    assert summary["workstyle_ready"] == 1
