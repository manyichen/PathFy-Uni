"""薪资归一化。"""

from __future__ import annotations

from app.infrastructure.salary import (
    format_salary_norm,
    neo4j_salary_properties,
    normalize_job_salary,
    parse_salary_range,
)


def test_format_yuan_range():
    p = parse_salary_range("4000-6000元")
    assert format_salary_norm(p) == "4000-6000元"


def test_format_wan_range():
    p = parse_salary_range("1-1.5万")
    assert format_salary_norm(p) == "10000-15000元"


def test_format_daily_to_monthly():
    p = parse_salary_range("150-200元/天")
    assert format_salary_norm(p) == "3262-4350元"


def test_format_bonus_suffix_stripped_from_norm():
    p = parse_salary_range("6000-10000元·13薪")
    assert format_salary_norm(p) == "6000-10000元"
    assert p.get("bonus_months") == 13


def test_format_negotiable_labels():
    assert format_salary_norm(parse_salary_range("薪资面议")) == "面议"
    assert format_salary_norm(parse_salary_range("待定")) == "待定"
    assert format_salary_norm(parse_salary_range("未知")) == "未知"


def test_format_below_yuan():
    p = parse_salary_range("1000元以下")
    assert format_salary_norm(p) == "0-1000元"
    assert p["monthly_min"] == 0
    assert p["monthly_max"] == 1000


def test_neo4j_properties_keeps_raw():
    props = neo4j_salary_properties("1.5-3万·14薪")
    assert props["salary"] == "1.5-3万·14薪"
    assert props["salary_norm"] == "15000-30000元"
    assert props["salary_bonus_months"] == 14
    assert props["salary_monthly_min"] == 15000
    assert props["salary_monthly_max"] == 30000


def test_normalize_job_salary_roundtrip():
    n = normalize_job_salary("5000-7000元")
    assert n["salary_norm"] == "5000-7000元"
