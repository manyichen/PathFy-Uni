"""pytest 公共 fixture。"""

from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def app():
    flask_app = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "TOKEN_EXPIRES_HOURS": 1,
        }
    )
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
