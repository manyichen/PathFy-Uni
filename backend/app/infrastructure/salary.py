"""招聘薪资文本解析、归一化与筛选匹配。"""

from __future__ import annotations

import re
from typing import Any

SALARY_PARSE_VERSION = "v1"
SALARY_DISPLAY_FALLBACK = "薪资面议"
DAILY_TO_MONTHLY_FACTOR = 21.75

_NEGOTIABLE_LABELS = (
    ("薪资面议", "面议"),
    ("面议", "面议"),
    ("待定", "待定"),
    ("未知", "未知"),
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _round_yuan(value: float) -> int:
    return int(round(float(value)))


def normalize_salary_text(text: str) -> str:
    """解析前统一写法（去奖金后缀、空白、大小写）。"""
    raw = str(text or "").strip()
    raw = re.sub(r"[·.]?\d{1,2}薪", "", raw)
    raw = raw.lower()
    raw = raw.replace("k", "千")
    raw = raw.replace("／", "/")
    raw = raw.replace("·", "")
    raw = raw.replace(" ", "")
    return raw


def _negotiable_label(raw: str) -> str | None:
    for token, label in _NEGOTIABLE_LABELS:
        if token in raw:
            return label
    return None


def _extract_bonus_months(raw: str) -> int | None:
    m = re.search(r"(\d{1,2})薪", raw)
    if not m:
        return None
    n = _safe_int(m.group(1), 0)
    return n if n > 0 else None


def parse_salary_range(text: str) -> dict[str, Any]:
    """
    解析中文招聘薪资，返回 monthly_min/max 等结构化字段。
    jobs 转岗分析、岗位助手筛薪、Neo4j 归一化共用。
    """
    raw = str(text or "").strip()
    bonus_months = _extract_bonus_months(raw)
    norm_label = _negotiable_label(raw)

    base: dict[str, Any] = {
        "raw": raw,
        "monthly_min": None,
        "monthly_max": None,
        "negotiable": norm_label is not None,
        "norm_label": norm_label,
        "bonus_months": bonus_months,
        "period": "unknown",
        "confidence": 0.0,
    }

    if norm_label:
        base["confidence"] = 0.2
        return base

    norm = normalize_salary_text(raw)
    if not norm:
        base["negotiable"] = True
        base["norm_label"] = "面议"
        base["confidence"] = 0.0
        return base

    m = re.search(r"(\d+(?:\.\d+)?)元以下", norm)
    if m:
        hi = float(m.group(1))
        base.update(
            {
                "monthly_min": 0.0,
                "monthly_max": hi,
                "period": "monthly",
                "confidence": 0.88,
            }
        )
        return base

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)万", norm)
    if m:
        lo = float(m.group(1)) * 10000
        hi = float(m.group(2)) * 10000
        base.update(
            {
                "monthly_min": lo,
                "monthly_max": hi,
                "period": "monthly",
                "confidence": 0.95,
            }
        )
        return base

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)千", norm)
    if m:
        lo = float(m.group(1)) * 1000
        hi = float(m.group(2)) * 1000
        base.update(
            {
                "monthly_min": lo,
                "monthly_max": hi,
                "period": "monthly",
                "confidence": 0.95,
            }
        )
        return base

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)元/天", norm)
    if m:
        lo = float(m.group(1)) * DAILY_TO_MONTHLY_FACTOR
        hi = float(m.group(2)) * DAILY_TO_MONTHLY_FACTOR
        base.update(
            {
                "monthly_min": lo,
                "monthly_max": hi,
                "period": "daily",
                "confidence": 0.9,
            }
        )
        return base

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)元", norm)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2))
        base.update(
            {
                "monthly_min": lo,
                "monthly_max": hi,
                "period": "monthly",
                "confidence": 0.9,
            }
        )
        return base

    m = re.search(r"(\d+(?:\.\d+)?)万以上", norm)
    if m:
        lo = float(m.group(1)) * 10000
        base.update(
            {
                "monthly_min": lo,
                "monthly_max": lo,
                "period": "monthly",
                "confidence": 0.88,
            }
        )
        return base

    m = re.search(r"(\d+(?:\.\d+)?)千以上", norm)
    if m:
        lo = float(m.group(1)) * 1000
        base.update(
            {
                "monthly_min": lo,
                "monthly_max": lo,
                "period": "monthly",
                "confidence": 0.88,
            }
        )
        return base

    base["norm_label"] = "未知"
    return base


def format_salary_norm(parsed: dict[str, Any]) -> str:
    """规范展示串：X-Y元 / 面议 / 未知 / 待定。"""
    label = parsed.get("norm_label")
    if label in ("面议", "未知", "待定"):
        return str(label)

    lo = parsed.get("monthly_min")
    hi = parsed.get("monthly_max")
    if lo is not None and hi is not None:
        return f"{_round_yuan(lo)}-{_round_yuan(hi)}元"
    if lo is not None:
        v = _round_yuan(lo)
        return f"{v}-{v}元"
    if hi is not None:
        return f"0-{_round_yuan(hi)}元"
    return "未知"


def normalize_job_salary(raw: str) -> dict[str, Any]:
    """从招聘原文生成解析结果 + salary_norm。"""
    parsed = parse_salary_range(raw)
    parsed["salary_norm"] = format_salary_norm(parsed)
    return parsed


def neo4j_salary_properties(raw: str) -> dict[str, Any]:
    """写入 Neo4j Job 节点的薪资相关属性（保留原文 salary）。"""
    raw_s = str(raw or "").strip()
    p = normalize_job_salary(raw_s)
    out: dict[str, Any] = {
        "salary": raw_s,
        "salary_norm": p["salary_norm"],
        "salary_negotiable": bool(p.get("negotiable")),
        "salary_parse_version": SALARY_PARSE_VERSION,
    }
    if p.get("monthly_min") is not None:
        out["salary_monthly_min"] = _round_yuan(p["monthly_min"])
    if p.get("monthly_max") is not None:
        out["salary_monthly_max"] = _round_yuan(p["monthly_max"])
    if p.get("bonus_months") is not None:
        out["salary_bonus_months"] = int(p["bonus_months"])
    return out


def cypher_job_salary_display(alias: str = "j", *, as_name: str = "salary") -> str:
    """Cypher 片段：API 展示用规范月薪。"""
    return (
        f"coalesce({alias}.salary_norm, {alias}.salary, '{SALARY_DISPLAY_FALLBACK}') AS {as_name}"
    )


def cypher_job_salary_raw(alias: str = "j", *, as_name: str = "salary_raw") -> str:
    return f"coalesce({alias}.salary, '') AS {as_name}"


def salary_matches_target(parsed: dict[str, Any], target: dict[str, Any]) -> bool:
    if not target:
        return True
    if parsed.get("negotiable"):
        return bool(target.get("include_negotiable"))

    monthly_min = parsed.get("monthly_min")
    monthly_max = parsed.get("monthly_max")
    if monthly_min is None and monthly_max is None:
        return bool(target.get("include_bonus_only") and parsed.get("bonus_months"))

    target_min = target.get("min_monthly")
    target_max = target.get("max_monthly")
    if target_min is not None:
        upper = monthly_max if monthly_max is not None else monthly_min
        if upper is None or upper < float(target_min):
            return False
    if target_max is not None:
        lower = monthly_min if monthly_min is not None else monthly_max
        if lower is not None and lower > float(target_max):
            return False
    return True
