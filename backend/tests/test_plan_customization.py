"""分岗计划：资源去重与定制行动合并。"""
from app.domains.report.plan_customization import apply_custom_plan_batch
from app.domains.report.plans_by_target import build_plans_by_target


def _insight(job_id: str, title: str, company: str, gaps: dict) -> dict:
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "display_title": f"{title} · {company}",
        "match_preview": {
            "match_score": 62.0,
            "dimension_gaps": gaps,
        },
    }


def test_lr_resource_deduped_within_same_job():
    insights = [
        _insight(
            "j1",
            "Java开发",
            "甲公司",
            {"cap_req_theory": 8.0, "cap_req_practice": 7.0},
        ),
    ]
    recommendations = {
        "enabled": True,
        "by_target": [
            {
                "job_id": "j1",
                "job_title_name": "Java开发",
                "learning_resources": [
                    {
                        "resource_id": "Java_1",
                        "resource_name": "Java程序设计",
                        "skill_tag": "Java 编程 理论",
                        "score": 0.95,
                        "phase": "short_term",
                    },
                ],
                "competitions": [],
            },
        ],
    }
    plans = build_plans_by_target(insights, recommendations)
    early = plans[0]["phases"]["early"]["items"]
    attached = [
        str(r.get("id") or "")
        for it in early
        for r in (it.get("learning_path_refs") or [])
    ]
    assert attached.count("Java_1") <= 1


def test_apply_custom_plan_batch_merges_actions():
    insights = [_insight("j1", "前端", "乙公司", {"cap_req_digital": 5.0})]
    recommendations = {
        "enabled": True,
        "by_target": [{"job_id": "j1", "job_title_name": "前端", "learning_resources": [], "competitions": []}],
    }
    plans = build_plans_by_target(insights, recommendations)
    dim = plans[0]["phases"]["early"]["items"][0]["focus_dimension"]
    updated = apply_custom_plan_batch(
        plans,
        [
            {
                "job_id": "j1",
                "phases": {
                    "early": {
                        "line_one_liner": "先补齐数字技能并产出小项目",
                        "items": [
                            {
                                "focus_dimension": dim,
                                "milestone": "2周内完成 1 个可演示页面",
                                "custom_actions": [
                                    {"kind": "practice", "text": "用公司技术栈复现岗位页面模块"},
                                ],
                            }
                        ],
                    },
                },
            }
        ],
    )
    assert updated == 1
    assert plans[0]["phases"]["early"]["line_one_liner"]
    item = plans[0]["phases"]["early"]["items"][0]
    assert item["milestone"].startswith("2周内")
    assert item["custom_actions"][0]["text"]
