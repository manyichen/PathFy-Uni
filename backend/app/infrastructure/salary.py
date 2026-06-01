"""招聘薪资文本解析与筛选匹配。"""

from __future__ import annotations

import re
from typing import Any


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_salary_text(text: str) -> str:
    raw = str(text or "").strip().lower()
    raw = raw.replace("k", "千")
    raw = raw.replace("／", "/")
    raw = raw.replace("·", "")
    raw = raw.replace(" ", "")
    return raw


def parse_salary_range(text: str) -> dict[str, Any]:
    """
    解析中文招聘薪资字符串，返回 monthly_min/max 等结构化字段。
    jobs 转岗分析与岗位助手筛薪共用此实现。
    """
    raw = str(text or "").strip()
    norm = normalize_salary_text(raw)
    if not norm:
        return {
            "raw": raw,
            "monthly_min": None,
            "monthly_max": None,
            "negotiable": True,
            "bonus_months": None,
            "period": "unknown",
            "confidence": 0.0,
        }

    negotiable_tokens = ("面议", "薪资面议", "未知", "待定")
    if any(token in raw for token in negotiable_tokens):
        return {
            "raw": raw,
            "monthly_min": None,
            "monthly_max": None,
            "negotiable": True,
            "bonus_months": None,
            "period": "unknown",
            "confidence": 0.2,
        }

    bonus_months = None
    bonus_match = re.search(r"(\d{2})薪", raw)
    if bonus_match:
        bonus_months = _safe_int(bonus_match.group(1), 0) or None

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)万", norm)
    if m:
        lo = float(m.group(1)) * 10000
        hi = float(m.group(2)) * 10000
        return {
            "raw": raw,
            "monthly_min": lo,
            "monthly_max": hi,
            "negotiable": False,
            "bonus_months": bonus_months,
            "period": "monthly",
            "confidence": 0.95,
        }

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)千", norm)
    if m:
        lo = float(m.group(1)) * 1000
        hi = float(m.group(2)) * 1000
        return {
            "raw": raw,
            "monthly_min": lo,
            "monthly_max": hi,
            "negotiable": False,
            "bonus_months": bonus_months,
            "period": "monthly",
            "confidence": 0.95,
        }

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)元/天", norm)
    if m:
        lo = float(m.group(1)) * 21.75
        hi = float(m.group(2)) * 21.75
        return {
            "raw": raw,
            "monthly_min": lo,
            "monthly_max": hi,
            "negotiable": False,
            "bonus_months": bonus_months,
            "period": "daily",
            "confidence": 0.9,
        }

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)元", norm)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2))
        return {
            "raw": raw,
            "monthly_min": lo,
            "monthly_max": hi,
            "negotiable": False,
            "bonus_months": bonus_months,
            "period": "monthly",
            "confidence": 0.9,
        }

    m = re.search(r"(\d+(?:\.\d+)?)万以上", norm)
    if m:
        lo = float(m.group(1)) * 10000
        return {
            "raw": raw,
            "monthly_min": lo,
            "monthly_max": None,
            "negotiable": False,
            "bonus_months": bonus_months,
            "period": "monthly",
            "confidence": 0.88,
        }

    m = re.search(r"(\d+(?:\.\d+)?)千以上", norm)
    if m:
        lo = float(m.group(1)) * 1000
        return {
            "raw": raw,
            "monthly_min": lo,
            "monthly_max": None,
            "negotiable": False,
            "bonus_months": bonus_months,
            "period": "monthly",
            "confidence": 0.88,
        }

    return {
        "raw": raw,
        "monthly_min": None,
        "monthly_max": None,
        "negotiable": False,
        "bonus_months": bonus_months,
        "period": "unknown",
        "confidence": 0.0,
    }


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
