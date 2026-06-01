"""ApiError 全局 handler。"""

from __future__ import annotations

from app.core.errors import ApiError


def test_api_error_handler_ok_envelope(client, app):
    @app.get("/api/_test/api-error-ok")
    def _raise_ok():
        raise ApiError("校验失败", 400)

    res = client.get("/api/_test/api-error-ok")
    assert res.status_code == 400
    body = res.get_json()
    assert body == {"ok": False, "message": "校验失败"}


def test_api_error_handler_code_envelope(client, app):
    @app.get("/api/_test/api-error-code")
    def _raise_code():
        raise ApiError("未登录", 401, envelope="code")

    res = client.get("/api/_test/api-error-code")
    assert res.status_code == 401
    body = res.get_json()
    assert body == {"code": 401, "msg": "未登录"}
