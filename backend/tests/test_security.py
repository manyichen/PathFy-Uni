"""JWT 签发与解析。"""

from __future__ import annotations

from app.core.security import assert_self_user_id, create_token, get_bearer_user_id


def test_create_token_and_bearer(app):
    with app.app_context():
        token = create_token(42, "alice", "alice@example.com")
    assert isinstance(token, str) and token

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert get_bearer_user_id() == 42


def test_bearer_missing(app):
    with app.test_request_context():
        assert get_bearer_user_id() is None


def test_bearer_invalid(app):
    with app.test_request_context(headers={"Authorization": "Bearer not-a-jwt"}):
        assert get_bearer_user_id() is None


def test_assert_self_user_id():
    assert assert_self_user_id(5, 5) is True
    assert assert_self_user_id(5, 6) is False
