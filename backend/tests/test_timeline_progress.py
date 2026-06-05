"""发展线进步度：按月封顶、12 个月分期。"""
from app.domains.report.constants import TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH
from app.domains.report.growth import (
    _review_achievement_score,
    timeline_progress_after_review,
)


def test_zero_metrics_yield_zero_achievement():
    assert _review_achievement_score({}, 0.0) == 0.0


def test_first_month_capped_at_max_gain():
    submitted = {
        "dim_gap_reduction": 100,
        "project_completion": 100,
        "match_score_change": 10,
        "delivery_output": 5,
    }
    p1 = timeline_progress_after_review(
        submitted=submitted,
        pass_rate=1.0,
        prev_progress=0.0,
        month_span=1.0,
    )
    assert p1 <= TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH + 0.01
    assert p1 == TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH


def test_partial_achievement_scales_linearly():
    submitted = {"project_completion": 50}
    p = timeline_progress_after_review(
        submitted=submitted,
        pass_rate=0.0,
        prev_progress=0.0,
        month_span=1.0,
    )
    assert 0 < p < TIMELINE_MAX_PROGRESS_GAIN_PER_MONTH


def test_twelve_months_full_achievement_reaches_100():
    progress = 0.0
    for _ in range(12):
        progress = timeline_progress_after_review(
            submitted={"project_completion": 100, "dim_gap_reduction": 100, "delivery_output": 5},
            pass_rate=1.0,
            prev_progress=progress,
            month_span=1.0,
        )
    assert progress >= 99.0
