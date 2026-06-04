"""infrastructure 纯函数。"""

from __future__ import annotations

from app.core.errors import ApiError
from app.infrastructure.llm import strip_json_fence
from app.infrastructure.salary import parse_salary_range, salary_matches_target


def test_strip_json_fence_codeblock():
    raw = '```json\n{"a": 1}\n```'
    assert strip_json_fence(raw) == '{"a": 1}'


def test_parse_salary_range_wan():
    parsed = parse_salary_range("15-25万")
    assert parsed["monthly_min"] == 150000
    assert parsed["monthly_max"] == 250000
    assert parsed["negotiable"] is False


def test_parse_salary_negotiable():
    parsed = parse_salary_range("薪资面议")
    assert parsed["negotiable"] is True


def test_salary_matches_target():
    parsed = parse_salary_range("10-15千")
    assert salary_matches_target(parsed, {"min_monthly": 8000, "max_monthly": 20000}) is True
    assert salary_matches_target(parsed, {"min_monthly": 20000}) is False


def test_api_error_attributes():
    err = ApiError("bad", 422, envelope="code", code=422)
    assert err.message == "bad"
    assert err.envelope == "code"
