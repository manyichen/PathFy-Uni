"""JWT 鉴权 helper（Bearer token 解析与签发）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app, request


def get_bearer_user_id() -> int | None:
    """从当前请求的 ``Authorization: Bearer`` 解析用户 id；缺失或无效时返回 ``None``。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.replace("Bearer ", "", 1)
    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    try:
        return int(sub) if sub is not None else None
    except (TypeError, ValueError):
        return None


def require_bearer_user_id() -> int | None:
    """从 Bearer JWT 解析用户 id；缺失或无效时返回 ``None``。"""
    return get_bearer_user_id()


def assert_self_user_id(requested: int, jwt_uid: int) -> bool:
    """路径中的 user_id 必须与 JWT 中的用户 id 一致。"""
    return int(requested) == int(jwt_uid)


def create_token(user_id: int, username: str, email: str, is_admin: bool = False) -> str:
    expires = datetime.now(tz=timezone.utc) + timedelta(
        hours=current_app.config["TOKEN_EXPIRES_HOURS"]
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "email": email,
        "is_admin": is_admin,
        "exp": expires,
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")
