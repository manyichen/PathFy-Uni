import re
from datetime import datetime, timezone

import jwt
from flask import Blueprint, current_app, jsonify, request
from pymysql.err import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.security import (
    assert_self_user_id,
    create_token,
    get_bearer_user_id,
    require_bearer_user_id,
)
from app.db import db_cursor

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{2,32}$")

__all__ = [
    "assert_self_user_id",
    "auth_bp",
    "get_bearer_user_id",
    "require_bearer_user_id",
]


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not USERNAME_RE.match(username):
        return jsonify({"ok": False,"message": "用户名需为2-32位，仅支持字母、数字和下划线"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"ok": False, "message": "邮箱格式不正确"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "message": "密码至少6位"}), 400

    password_hash = generate_password_hash(password)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with db_cursor() as (_, cursor):
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, created_at, updated_at, is_admin)
                VALUES (%s, %s, %s, %s, %s, 0)
            """, (username, email, password_hash, now, now))
            user_id = cursor.lastrowid
    except IntegrityError:
        return jsonify({"ok": False, "message": "用户名或邮箱已存在"}), 409

    token = create_token(user_id, username, email, is_admin=False)
    return jsonify({
        "ok": True,
        "message": "注册成功",
        "data": {
            "token": token,
            "user": {"id": user_id, "username": username, "email": email, "is_admin": False}
        }
    }), 201

@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    account = (payload.get("account") or "").strip()
    password = payload.get("password") or ""

    if not account or not password:
        return jsonify({"ok": False, "message": "账号和密码不能为空"}), 400

    with db_cursor() as (_, cursor):
        cursor.execute("""
            SELECT id, username, email, password_hash, is_admin
            FROM users
            WHERE email = %s OR username = %s
            LIMIT 1
        """, (account.lower(), account))
        user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"ok": False, "message": "账号或密码错误"}), 401

    with db_cursor() as (_, cursor):
        cursor.execute(
            "UPDATE users SET last_login_at = %s WHERE id = %s",
            (datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), user["id"]),
        )

    is_admin = bool(user["is_admin"])
    token = create_token(user["id"], user["username"], user["email"], is_admin=is_admin)
    return jsonify({
        "ok": True,
        "message": "登录成功",
        "data": {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "is_admin": is_admin,
            },
        },
    })

@auth_bp.get("/me")
def me():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"ok": False, "message": "未提供有效令牌"}), 401

    token = auth_header.replace("Bearer ", "", 1)
    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return jsonify({"ok": False, "message": "令牌无效或已过期"}), 401

    sub = payload.get("sub")
    try:
        user_id = int(sub) if sub is not None else None
    except (TypeError, ValueError):
        user_id = None

    is_admin = payload.get("is_admin")
    if is_admin is None and user_id is not None:
        # 旧 token 不含 is_admin，回退查 DB
        with db_cursor() as (_, cur):
            cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
        is_admin = bool(row["is_admin"]) if row else False
    else:
        is_admin = bool(is_admin)

    return jsonify({
        "ok": True,
        "data": {
            "user": {
                "id": user_id,
                "username": payload.get("username"),
                "email": payload.get("email"),
                "is_admin": is_admin,
            }
        }
    })
