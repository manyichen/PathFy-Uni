from copy import deepcopy

from app.domains.match.preference_ranking import apply_preference_tie_break, experiment_variant


def _card(job_id, ability, preference=None):
    fit = {"status": "available", "score": preference, "influenced_ranking": False} if preference is not None else {"status": "insufficient_job_evidence", "score": None, "influenced_ranking": False}
    return {"id": job_id, "match_preview": {"match_score": ability, "preference_fit": fit}}


def test_tie_break_only_reorders_inside_ability_band_and_preserves_scores():
    rows = [_card("a", 90, 60), _card("b", 89, 95), _card("c", 80, 100)]
    original = deepcopy(rows)
    diff = apply_preference_tie_break(rows, max_ability_gap=3)
    assert [row["id"] for row in rows] == ["b", "a", "c"]
    assert [row["match_preview"]["match_score"] for row in rows] == [89, 90, 80]
    assert rows[2]["id"] == original[2]["id"]
    assert diff["changed_jobs"] == 2
    assert rows[0]["match_preview"]["ability_rank"] == 2


def test_missing_preference_does_not_jump_a_supported_job():
    rows = [_card("a", 90), _card("b", 89, 80)]
    apply_preference_tie_break(rows, max_ability_gap=3)
    assert [row["id"] for row in rows] == ["b", "a"]


def test_experiment_bucket_is_stable_and_respects_extremes():
    assert experiment_variant(42, 0)[0] == "control"
    assert experiment_variant(42, 100)[0] == "tie_break"
    assert experiment_variant(42, 50) == experiment_variant(42, 50)
