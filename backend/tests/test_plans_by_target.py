"""分岗三阶段计划构建。"""
from app.domains.report.plans_by_target import build_plans_by_target


def _insight(job_id: str, title: str, gaps: dict) -> dict:
    return {
        "id": job_id,
        "title": title,
        "company": "测试公司",
        "display_title": f"{title} · 测试公司",
        "match_preview": {
            "match_score": 65.0,
            "dimension_gaps": gaps,
        },
    }


def test_build_plans_by_target_per_job_phases():
    insights = [
        _insight("j1", "Java", {"cap_req_theory": 8.0, "cap_req_practice": 2.0}),
        _insight("j2", "前端开发", {"cap_req_digital": 9.0}),
    ]
    recommendations = {
        "enabled": True,
        "by_target": [
            {
                "job_id": "j1",
                "job_title_name": "Java",
                "learning_resources": [{"resource_id": "Java_1", "resource_name": "课A", "score": 0.9}],
                "competitions": [],
            },
            {
                "job_id": "j2",
                "job_title_name": "前端开发",
                "learning_resources": [],
                "competitions": [{"competition_id": "c1", "competition_name": "赛B", "score": 0.8}],
            },
        ],
    }
    plans = build_plans_by_target(insights, recommendations)
    assert len(plans) == 2
    assert plans[0]["job_id"] == "j1"
    assert plans[0]["phases"]["early"]["items"]
    assert plans[0]["phases"]["late"]["items"]
    assert plans[1]["job_id"] == "j2"
    assert plans[0]["phases"]["early"]["label"] == "前期"
    assert plans[0]["phases"]["early"]["period"] == "0-3个月"
    assert plans[0]["phases"]["mid"]["period"] == "3-9个月"
    assert plans[0]["phases"]["late"]["period"] == "9-12个月"
