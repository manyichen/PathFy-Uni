"""能力缺口与复盘基线。"""
from __future__ import annotations

from app.domains.report.gap_analysis import (
    build_gap_baseline,
    build_match_preview,
    compute_review_gap_metrics,
    parse_match_goal,
)
from app.infrastructure.neo4j import DIM_KEYS


def _profile(scores: dict[str, float]) -> dict:
    conf = {k.replace("cap_req_", "cap_conf_"): 0.7 for k in DIM_KEYS}
    return {"scores": scores, "confidences": conf}


def _job(scores: dict[str, float], *, title: str = "Java") -> dict:
    conf = {k.replace("cap_req_", "cap_conf_"): 0.7 for k in DIM_KEYS}
    return {
        "id": "job-1",
        "title": title,
        "company": "Acme",
        "scores": scores,
        "confidences": conf,
    }


def test_parse_match_goal():
    assert parse_match_goal("stretch") == "stretch"
    assert parse_match_goal("fit") == "fit"


def test_build_match_preview_jd_only():
    student = {k: 50.0 for k in DIM_KEYS}
    job = {k: 70.0 for k in DIM_KEYS}
    mp = build_match_preview(_profile(student), _job(job), match_goal="fit")
    assert mp["soft_margin"] == 6.0
    assert mp["dimension_gaps"]["cap_req_theory"] == 14.0
    assert "dimension_gaps_vs_category" not in mp
    assert "category_median_scores" not in mp
    assert mp["dimension_raw_delta"]["cap_req_theory"] == 20.0
    assert "岗位要求" in mp["reference_note"]


def test_stretch_margin_more_lenient():
    student = {k: 50.0 for k in DIM_KEYS}
    job = {k: 58.0 for k in DIM_KEYS}
    fit = build_match_preview(_profile(student), _job(job), match_goal="fit")
    stretch = build_match_preview(_profile(student), _job(job), match_goal="stretch")
    assert stretch["soft_margin"] == 10.0
    assert stretch["weighted_gap"] <= fit["weighted_gap"]


def test_gap_baseline_and_review_reduction():
    student = {k: 50.0 for k in DIM_KEYS}
    job = _job({k: 70.0 for k in DIM_KEYS})
    mp = build_match_preview(_profile(student), job, match_goal="fit")
    insights = [{"id": "job-1", "match_preview": mp}]
    baseline = build_gap_baseline(insights, primary_job_id="job-1", resume_id=1)
    report_obj = {"evaluation": {"gap_baseline": baseline}}

    improved = {k: 55.0 for k in DIM_KEYS}
    metrics = compute_review_gap_metrics(report_obj, _profile(improved), [job])
    assert metrics["dim_gap_reduction"] > 0
    assert "match_score_change" in metrics
