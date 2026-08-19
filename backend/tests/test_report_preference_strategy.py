from app.domains.report.enrichment_quality import create_input_snapshot, snapshot_hash, verify_input_snapshot
from app.domains.report.preference_strategy import (
    apply_strategy_decision,
    behavioral_evidence_rows,
    build_preference_strategy,
    update_calibration,
)


def _snapshot():
    return {
        "status": "measured",
        "personality_profile_id": 7,
        "mbti_type": "INTJ",
        "axes": [
            {"code": "interaction_intensity", "value": 25, "preference_strength": .5},
            {"code": "abstraction_preference", "value": 80, "preference_strength": .6},
            {"code": "analytical_decision", "value": 75, "preference_strength": .5},
            {"code": "structure_preference", "value": 85, "preference_strength": .7},
        ],
    }


def test_strategy_changes_execution_only_and_is_editable():
    strategy = build_preference_strategy(_snapshot())
    assert strategy["status"] == "suggested"
    assert strategy["influences_capability"] is False
    assert len(strategy["sections"]) == 4
    edited = apply_strategy_decision(strategy, {"decision": "edit", "sections": [{"code": "structure_preference", "recommendation": "每周一设置两个里程碑"}]})
    assert edited["status"] == "edited"
    assert edited["sections"][3]["recommendation"] == "每周一设置两个里程碑"
    assert edited["sections"][3]["source"] == strategy["sections"][3]["source"]


def test_three_cycle_calibration_never_mutates_profile():
    strategy = build_preference_strategy(_snapshot())
    history = [{"preference_signals": {"structure_fit": value}} for value in (1, 2, 1)]
    calibrated = update_calibration(strategy, history)
    assert calibrated["calibration"]["status"] == "review_recommended"
    assert calibrated["calibration"]["candidate_axes"][0]["axis_code"] == "structure_preference"
    assert calibrated["sections"] == strategy["sections"]
    evidence = behavioral_evidence_rows({"structure_fit": 5})
    assert evidence[0]["observed_value"] == 100


def test_report_snapshot_v2_freezes_minimal_preference_and_hash():
    report = {"student": {"id": 1, "scores": {}}, "targets": []}
    frozen = create_input_snapshot(
        report,
        resume_id=1,
        primary_job_id="job-1",
        target_job_ids=["job-1"],
        match_goal="fit",
        settings_revision=2,
        preference_snapshot=_snapshot(),
        preference_revisions={"preference_strategy_version": "preference-strategy-v1"},
    )
    assert frozen["schema_version"] == 2
    assert frozen["personality_profile_id"] == 7
    assert "answers" not in frozen["preference_profile"]
    assert verify_input_snapshot(frozen)


def test_legacy_v1_hash_remains_valid():
    snapshot = create_input_snapshot({"student": {}, "targets": []}, resume_id=1, primary_job_id="j", target_job_ids=["j"], match_goal="fit", settings_revision=None)
    snapshot["schema_version"] = 1
    snapshot.pop("personality_profile_id", None)
    snapshot.pop("preference_profile", None)
    snapshot["sha256"] = snapshot_hash({key: value for key, value in snapshot.items() if key != "sha256"})
    assert verify_input_snapshot(snapshot)
