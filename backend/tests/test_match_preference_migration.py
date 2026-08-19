from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "migrations" / "versions" / "20260819_0011_match_preference_context.py"


def test_match_preference_migration_contract():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260819_0011"' in source
    assert 'down_revision = "20260819_0010"' in source
    for field in (
        "personality_profile_id",
        "preference_mode",
        "preference_snapshot_json",
        "preference_algorithm_version",
        "workstyle_snapshot_version",
    ):
        assert field in source
    assert "ON DELETE SET NULL" in source
