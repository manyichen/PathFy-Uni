"""Runtime schema doctor contract."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "tools" / "check_runtime_schema.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_runtime_schema", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_schema_doctor_tracks_snapshot_columns():
    script = _load_script()

    assert "settings_revision" in script.REQUIRED_TABLE_COLUMNS["match_runs"]
    assert "config_snapshot_json" in script.REQUIRED_TABLE_COLUMNS["match_runs"]
    assert "personality_profile_id" in script.REQUIRED_TABLE_COLUMNS["match_runs"]
    assert "preference_snapshot_json" in script.REQUIRED_TABLE_COLUMNS["match_runs"]
    assert "settings_revision" in script.REQUIRED_TABLE_COLUMNS["career_reports"]
    assert "config_snapshot_json" in script.REQUIRED_TABLE_COLUMNS["career_reports"]
    assert "report_version" in script.REQUIRED_TABLE_COLUMNS["career_reports"]
    assert "scope" in script.REQUIRED_TABLE_COLUMNS["career_report_reviews"]
    assert "job_id" in script.REQUIRED_TABLE_COLUMNS["career_report_reviews"]
    assert "candidates_json" in script.REQUIRED_TABLE_COLUMNS["career_report_review_drafts"]
    assert "diff_json" in script.REQUIRED_TABLE_COLUMNS["career_report_plan_versions"]
    assert "updated_at" in script.REQUIRED_TABLE_COLUMNS["student_resume"]
    assert "variant" in script.REQUIRED_TABLE_COLUMNS["career_report_experiment_assignments"]
    assert "settings_revision" in script.REQUIRED_TABLE_COLUMNS["graph_update_tasks"]
    assert "config_snapshot_json" in script.REQUIRED_TABLE_COLUMNS["graph_update_tasks"]
    assert "dimension_scores_json" in script.REQUIRED_TABLE_COLUMNS["personality_profiles"]
    assert "answer_signature" in script.REQUIRED_TABLE_COLUMNS["personality_profiles"]
    assert "personality_profile_id" in script.REQUIRED_TABLE_COLUMNS["personality_test_answers"]
    assert "personality_profile_id" in script.REQUIRED_TABLE_COLUMNS["career_reports"]
    assert "preference_experiment_variant" in script.REQUIRED_TABLE_COLUMNS["match_runs"]
    assert "user_confirmed" in script.REQUIRED_TABLE_COLUMNS["behavioral_preference_evidence"]
    assert script.EXPECTED_ALEMBIC_HEAD == "20260819_0012"


def test_runtime_schema_doctor_reports_missing_columns():
    script = _load_script()
    columns = {
        table: set(required)
        for table, required in script.REQUIRED_TABLE_COLUMNS.items()
    }
    columns["career_reports"] = {"id", "user_id", "resume_id", "report_json"}

    results = script.evaluate_schema(columns, [script.EXPECTED_ALEMBIC_HEAD])

    report_result = next(result for result in results if result.name == "career_reports")
    assert report_result.status == "FAIL"
    assert "settings_revision" in report_result.detail
    assert "config_snapshot_json" in report_result.detail


def test_runtime_schema_doctor_checks_report_cascade_and_indexes():
    script = _load_script()
    rules = dict(script.REQUIRED_DELETE_RULES)
    indexes = set(script.REQUIRED_INDEXES)
    results = script.evaluate_runtime_guards(rules, indexes)
    assert results
    assert all(result.status == "OK" for result in results)

    rules[("career_report_action_events", "fk_action_events_report")] = "RESTRICT"
    indexes.remove(("career_report_experiment_assignments", "idx_experiment_variant"))
    results = script.evaluate_runtime_guards(rules, indexes)
    assert next(result for result in results if result.name.endswith("fk_action_events_report")).status == "FAIL"
    assert next(result for result in results if result.name.endswith("idx_experiment_variant")).status == "FAIL"
