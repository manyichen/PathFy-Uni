"""Alembic-only database URL construction; runtime access remains PyMySQL."""

from __future__ import annotations

from sqlalchemy import URL

from app.core.config import Config


def database_url() -> URL:
    """Build a safely escaped SQLAlchemy URL from the existing MYSQL_* settings."""
    return URL.create(
        drivername="mysql+pymysql",
        username=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        database=Config.MYSQL_DATABASE,
        query={"charset": "utf8mb4"},
    )
