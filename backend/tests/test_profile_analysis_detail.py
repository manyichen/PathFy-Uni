from app.domains.profile.analysis import generate_detailed_analysis


SCORES = {
    "cap_req_theory": 75,
    "cap_req_cross": 60,
    "cap_req_practice": 80,
    "cap_req_digital": 70,
    "cap_req_innovation": 65,
    "cap_req_teamwork": 75,
    "cap_req_social": 55,
    "cap_req_growth": 80,
}


def test_dimension_analysis_contains_actionable_evidence_fields():
    result = generate_detailed_analysis(
        SCORES,
        "使用 Python 和 SQL 完成数据项目，负责团队协作，并持续记录学习复盘。",
    )

    assert len(result["dimension_analysis"]) == 8
    for dimension in result["dimension_analysis"]:
        assert dimension["rank"] >= 1
        assert dimension["stage"]
        assert dimension["judgement"]
        assert dimension["development_gap"]
        assert dimension["next_actions"]
        assert dimension["expected_evidence"]
        assert dimension["success_metric"]

    digital = next(item for item in result["dimension_analysis"] if item["dimension_key"] == "cap_req_digital")
    assert "Python" in digital["evidence_clues"]
    assert result["weakness_dimensions"] == result["劣势_dimensions"]


def test_growth_route_is_complete_without_extreme_scores():
    result = generate_detailed_analysis(SCORES)

    assert len(result["short_term_plan"]) == 3
    assert len(result["long_term_goals"]) == 3
    for stop in result["short_term_plan"]:
        assert stop["actions"]
        assert stop["deliverable"]
        assert stop["success_metric"]
        assert stop["target_score"] > stop["current_score"]
    for goal in result["long_term_goals"]:
        assert goal["milestones"]
        assert goal["portfolio_evidence"]
        assert goal["success_metric"]
