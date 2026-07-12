"""Pure job-list behavior retained while the jobs router is split."""

from app.domains.jobs.listing import (
    jobs_order_clause,
    jobs_page_payload,
    jobs_shuffle_key,
    normalize_jobs_sort,
)


def _row(job_id: str, score: float = 50.0) -> dict:
    row = {
        "id": job_id,
        "title": job_id,
        "salary": "面议",
        "company": "测试公司",
        "location": "测试地点",
    }
    for key in (
        "cap_req_theory", "cap_req_cross", "cap_req_practice", "cap_req_digital",
        "cap_req_innovation", "cap_req_teamwork", "cap_req_social", "cap_req_growth",
    ):
        row[key] = score
    return row


def test_sort_normalization_and_order_clause():
    assert normalize_jobs_sort(" SCORE_ASC ") == "score_asc"
    assert normalize_jobs_sort("unknown") == "default"
    assert jobs_order_clause("score_asc").startswith("ORDER BY total_score ASC")
    assert jobs_order_clause("default").startswith("ORDER BY total_score DESC")


def test_shuffle_key_is_seeded_and_stable():
    assert jobs_shuffle_key("job-1", "seed") == jobs_shuffle_key("job-1", "seed")
    assert jobs_shuffle_key("job-1", "seed") != jobs_shuffle_key("job-1", "other")


def test_page_payload_preserves_shape_and_bounds_page():
    payload = jobs_page_payload(
        [_row("a"), _row("b"), _row("c")],
        page=99,
        page_size=2,
        sort_mode="random",
        seed="fixed",
    )
    assert payload["page"] == 2
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert payload["seed"] == "fixed"
    assert [row["id"] for row in payload["jobs"]] == ["c"]
