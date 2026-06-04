"""报告 JSON 出站前清洗敏感字段。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.privacy import storage_safe_text


def sanitize_review_text_fields(obj: Any) -> Any:
    """递归清洗 review_text（兼容历史明文）。"""
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if key == "review_text":
                obj[key] = storage_safe_text(value, kind="review", max_chars=4000)
            else:
                obj[key] = sanitize_review_text_fields(value)
        return obj
    if isinstance(obj, list):
        for idx, item in enumerate(obj):
            obj[idx] = sanitize_review_text_fields(item)
        return obj
    return obj
