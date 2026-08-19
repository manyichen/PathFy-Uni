from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "migrations" / "versions" / "20260819_0010_personality_assessments.py"


def test_personality_migration_is_chained_and_contains_assessment_contract():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260819_0010"' in source
    assert 'down_revision = "20260819_0009"' in source
    assert "dimension_scores_json" in source
    assert "question_set_version" in source
    assert "scoring_version" in source
    assert "answer_signature" in source
    assert "personality_profile_id" in source
    assert "fk_personality_answers_profile" in source
