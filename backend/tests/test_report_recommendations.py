"""图谱推荐：打分与规则选题（不依赖 Neo4j）。"""
from app.domains.report.recommendations import (
    _parse_cap_tags,
    _rule_pick,
    _score_competition,
    _score_learning_resource,
)


def test_score_learning_resource_boosts_entry_for_short_term():
    row = {
        "resource_name": "Java入门",
        "skill_tag": "Java基础",
        "difficulty": "入门",
        "resource_type": "视频课程",
    }
    s = _score_learning_resource(
        row, top_gaps=["cap_req_theory"], phase="short_term", match_score=50.0
    )
    assert s >= 0.5


def test_score_competition_cap_tag_overlap():
    row = {"cap_tags": "cap_req_innovation|cap_req_teamwork", "difficulty": "高阶"}
    s = _score_competition(row, top_gaps=["cap_req_innovation"], phase="mid_term")
    assert s >= 0.4


def test_rule_pick_respects_limits():
    pool = [
        {"resource_id": f"r{i}", "resource_type": "视频课程" if i < 2 else "文档教程", "_score": 0.9 - i * 0.1}
        for i in range(10)
    ]
    comp = [{"competition_id": f"c{i}", "_score": 0.8} for i in range(5)]
    lr, cp = _rule_pick(pool, comp, lr_final=3, comp_final=2)
    assert len(lr) == 3
    assert len(cp) == 2
    assert all("_llm_phase" in x for x in lr)


def test_parse_cap_tags():
    assert _parse_cap_tags("a|b| c") == ["a", "b", "c"]
