import re
from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, current_app, jsonify, request
from pymysql.err import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .db import db_cursor

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{2,32}$")


def _create_token(user_id: int, username: str, email: str) -> str:
    expires = datetime.now(tz=timezone.utc) + timedelta(
        hours=current_app.config["TOKEN_EXPIRES_HOURS"]
    )
    payload = {
        # PyJWT validates "sub" as a string in newer versions.
        "sub": str(user_id),
        "username": username,
        "email": email,
        "exp": expires,
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not USERNAME_RE.match(username):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "用户名需为2-32位，仅支持字母、数字和下划线",
                }
            ),
            400,
        )
    if not EMAIL_RE.match(email):
        return jsonify({"ok": False, "message": "邮箱格式不正确"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "message": "密码至少6位"}), 400

    password_hash = generate_password_hash(password)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, email, password_hash, now, now),
            )
            user_id = cursor.lastrowid
    except IntegrityError:
        return jsonify({"ok": False, "message": "用户名或邮箱已存在"}), 409

    token = _create_token(user_id, username, email)
    return (
        jsonify(
            {
                "ok": True,
                "message": "注册成功",
                "data": {
                    "token": token,
                    "user": {"id": user_id, "username": username, "email": email},
                },
            }
        ),
        201,
    )


@auth_bp.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        account = (payload.get("account") or "").strip()
        password = payload.get("password") or ""
    else:
        # Fallback for clients that accidentally submit login as GET.
        account = (request.args.get("account") or "").strip()
        password = request.args.get("password") or ""

    if not account or not password:
        return jsonify({"ok": False, "message": "账号和密码不能为空"}), 400

    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT id, username, email, password_hash
            FROM users
            WHERE email = %s OR username = %s
            LIMIT 1
            """,
            (account.lower(), account),
        )
        user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"ok": False, "message": "账号或密码错误"}), 401

    with db_cursor() as (_, cursor):
        cursor.execute(
            "UPDATE users SET last_login_at = %s WHERE id = %s",
            (datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), user["id"]),
        )

    token = _create_token(user["id"], user["username"], user["email"])
    return jsonify(
        {
            "ok": True,
            "message": "登录成功",
            "data": {
                "token": token,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                },
            },
        }
    )


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

    return jsonify(
        {
            "ok": True,
            "data": {
                "user": {
                    "id": user_id,
                    "username": payload.get("username"),
                    "email": payload.get("email"),
                }
            },
        }
    )
