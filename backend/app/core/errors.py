"""统一 API 错误类型与 Flask 错误处理器（不改动既有响应字段约定）。"""

from __future__ import annotations

from typing import Any, Literal

from flask import Flask, jsonify

EnvelopeKind = Literal["ok", "code"]


class ApiError(Exception):
    """
    业务/校验错误。由 ``register_error_handlers`` 转为 JSON 响应。

    - ``envelope="ok"`` → ``{"ok": false, "message": "..."}``（auth/jobs/match/report）
    - ``envelope="code"`` → ``{"code": <status>, "msg": "..."}``（profile/personality）
    """

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        *,
        envelope: EnvelopeKind = "ok",
        code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.envelope = envelope
        self.code = code if code is not None else status_code


def ok_response(data: Any = None, *, message: str = "success", status: int = 200):
    """标准 ``{ok, message, data?}`` 成功响应。"""
    body: dict[str, Any] = {"ok": True, "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def fail_ok(message: str, status: int = 400):
    """标准 ``{ok: false, message}`` 失败响应。"""
    return jsonify({"ok": False, "message": message}), status


def fail_code(msg: str, code: int = 400):
    """标准 ``{code, msg}`` 失败响应（profile/personality 域）。"""
    return jsonify({"code": code, "msg": msg}), code


def register_error_handlers(app: Flask) -> None:
    """注册全局错误处理器；未捕获异常仍走 Flask 默认 500。"""

    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):  # type: ignore[unused-ignore]
        if exc.envelope == "code":
            return fail_code(exc.message, exc.code)
        return fail_ok(exc.message, exc.status_code)

    @app.errorhandler(404)
    def _handle_not_found(_exc):  # type: ignore[unused-ignore]
        return fail_ok("资源不存在", 404)

    @app.errorhandler(405)
    def _handle_method_not_allowed(_exc):  # type: ignore[unused-ignore]
        return fail_ok("方法不允许", 405)

    @app.errorhandler(413)
    def _handle_payload_too_large(_exc):  # type: ignore[unused-ignore]
        return fail_ok("上传文件过大", 413)
