"""The first Alembic revision must initialize an empty configured database."""

import importlib.util
from pathlib import Path


REVISION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260712_0001_existing_schema_baseline.py"
)


def _load_revision():
    spec = importlib.util.spec_from_file_location("initial_schema_revision", REVISION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_executes_full_schema_without_legacy_database_selection(monkeypatch):
    revision = _load_revision()
    statements = []

    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.upgrade()

    joined = "\n".join(statements).upper()
    assert "CREATE DATABASE" not in joined
    assert "USE `SUILLI_MIZI`" not in joined
    for table in (
        "users", "ai_chat_sessions", "ai_chat_messages", "job_titles",
        "student_resume", "personality_test_questions", "personality_test_answers",
        "personality_profiles", "career_reports", "career_report_targets",
        "career_report_reviews", "match_runs", "match_run_items",
    ):
        assert f"CREATE TABLE IF NOT EXISTS `{table.upper()}`" in joined or f"CREATE TABLE IF NOT EXISTS {table.upper()}" in joined
    assert "INSERT INTO PERSONALITY_TEST_QUESTIONS" in joined


def test_downgrade_drops_children_before_users(monkeypatch):
    revision = _load_revision()
    statements = []

    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.downgrade()

    assert statements[0] == "DROP TABLE IF EXISTS `match_run_items`"
    assert statements[-1] == "DROP TABLE IF EXISTS `users`"
