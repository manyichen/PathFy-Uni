"""MBTI 静态数据。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "mbti_static.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def dimension_analysis() -> dict:
    return _load()["dimension_analysis"]


def complete_analysis() -> dict:
    return _load()["complete_analysis"]


def job_recommendations() -> dict:
    return _load()["job_recommendations"]
