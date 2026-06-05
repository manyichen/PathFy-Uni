"""赛道画像：招聘 CSV + 图谱统计分位数。"""
from __future__ import annotations

from app.domains.report.trends import build_track_profile, _load_hiring_table


def test_load_hiring_table_has_java():
    rows = _load_hiring_table()
    assert rows
    java = next((r for r in rows if r["job_title"] == "Java"), None)
    assert java is not None
    assert java["record_count"] == 591
    assert java["rank"] == 1


def test_build_track_profile_java_top_visibility():
    tp = build_track_profile(job_title_name="Java")
    assert tp["job_title"] == "Java"
    assert tp["hiring"]["record_count"] == 591
    assert tp["hiring_visibility_0_100"] >= 90.0
    assert 0 <= tp["path_breadth_0_100"] <= 100
    assert 0 <= tp["resource_density_0_100"] <= 100
    assert tp["source"] == "internal"
    assert "demand_index" not in str(tp)
