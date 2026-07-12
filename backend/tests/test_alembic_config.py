"""Alembic configuration must not alter runtime PyMySQL access."""

from app.db.alembic_config import database_url


def test_database_url_uses_existing_mysql_settings(monkeypatch):
    monkeypatch.setattr("app.db.alembic_config.Config.MYSQL_USER", "user@name")
    monkeypatch.setattr("app.db.alembic_config.Config.MYSQL_PASSWORD", "p@ss:/word")
    monkeypatch.setattr("app.db.alembic_config.Config.MYSQL_HOST", "db.internal")
    monkeypatch.setattr("app.db.alembic_config.Config.MYSQL_PORT", 3307)
    monkeypatch.setattr("app.db.alembic_config.Config.MYSQL_DATABASE", "pathfy")

    url = database_url()
    assert url.drivername == "mysql+pymysql"
    assert url.username == "user@name"
    assert url.password == "p@ss:/word"
    assert url.host == "db.internal"
    assert url.port == 3307
    assert url.database == "pathfy"
    assert url.query["charset"] == "utf8mb4"
