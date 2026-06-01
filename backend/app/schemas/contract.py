"""API 响应契约（TypedDict，供文档与测试引用；运行时仍用 dict/jsonify）。"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class OkEnvelope(TypedDict):
    ok: bool
    message: NotRequired[str]
    data: NotRequired[Any]


class CodeEnvelope(TypedDict):
    code: int
    msg: NotRequired[str]
    data: NotRequired[Any]


class HealthResponse(TypedDict):
    ok: bool
    message: str
