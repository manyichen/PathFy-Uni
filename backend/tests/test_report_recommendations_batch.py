"""图谱推荐 batch 策展。"""
from __future__ import annotations

from unittest.mock import patch

from app.domains.report.recommendations import _curate_batch_with_llm, _rule_pick


def test_curate_batch_parses_items():
    jobs = [
        {
            "job_id": "j1",
            "job_title_name": "Java",
            "top_gaps": ["cap_req_practice"],
            "match_score": 70.0,
            "lr_candidates": [
                {
                    "resource_id": "r1",
                    "resource_name": "Java基础",
                    "resource_type": "视频课程",
                    "difficulty": "入门",
                    "skill_tag": "Java",
                    "_score": 0.9,
                }
            ],
            "comp_candidates": [
                {
                    "competition_id": "c1",
                    "competition_name": "蓝桥杯",
                    "difficulty": "进阶",
                    "cap_tags": "cap_req_practice",
                    "_score": 0.8,
                }
            ],
        }
    ]
    mock_json = (
        '{"items":[{"job_id":"j1","learning_resources":[{"resource_id":"r1",'
        '"phase":"short_term","rationale":"补实践"}],"competitions":'
        '[{"competition_id":"c1","phase":"mid_term","rationale":"练手"}]}]}'
    )

    class _Cfg:
        def get(self, key, default=None):
            return {
                "DEEPSEEK_API_KEY": "test-key",
                "CAREER_DEEPSEEK_MODEL": "deepseek-chat",
                "CAREER_LLM_TIMEOUT_SECONDS": 30,
                "CAREER_ENABLE_RECOMMENDATION_LLM": True,
            }.get(key, default)

    fake_app = type("App", (), {"config": _Cfg()})()

    with patch("app.domains.report.recommendations.truthy", return_value=True), patch(
        "app.domains.report.recommendations.current_app",
        fake_app,
    ), patch(
        "app.domains.report.recommendations._call_openai_compatible",
        return_value=mock_json,
    ):
        by_job, meta = _curate_batch_with_llm(jobs, lr_final=6, comp_final=3)

    assert meta.get("ok") is True
    assert meta.get("mode") == "batch"
    assert "j1" in by_job
    assert len(by_job["j1"]["lr"]) == 1
    assert by_job["j1"]["lr"][0]["_llm_rationale"] == "补实践"


def test_rule_pick_fallback_without_llm():
    lr_pool = [{"resource_id": "r1", "resource_type": "视频课程", "_score": 0.5}]
    cp_pool = [{"competition_id": "c1", "_score": 0.5}]
    lr, cp = _rule_pick(lr_pool, cp_pool, lr_final=1, comp_final=1)
    assert len(lr) == 1
    assert len(cp) == 1
