"""报告域通用小工具。"""
from __future__ import annotations

import json
import re
from typing import Any

_TARGET_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(v, (int, float)):
        return bool(v)
    return False


def clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        x = int(v)
    except (TypeError, ValueError):
        x = default
    return max(lo, min(hi, x))


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_metric_target(target_text: str) -> float:
    text = str(target_text or "").strip()
    m = _TARGET_NUM_RE.search(text)
    if not m:
        return 0.0
    return to_float(m.group(0), 0.0)
