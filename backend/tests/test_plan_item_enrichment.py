"""计划条目丰富：骨架行动与指标对齐。"""
from app.domains.report.constants import sanitize_user_facing_text
from app.domains.report.plan_item_enrichment import (
    build_skeleton_custom_actions,
    enrich_plan_item,
    remediation_actions_for_failed_rows,
)


def test_sanitize_user_facing_text_replaces_metric_codes():
    raw = "推动 project_completion 完成率与 dim_gap_reduction 收敛"
    out = sanitize_user_facing_text(raw)
    assert "project_completion" not in out
    assert "dim_gap_reduction" not in out
    assert "计划完成" in out


def test_sanitize_strips_jargon():
    raw = "当前匹配约 91 分，学习 Java，拉动 计划完成 完成率"
    out = sanitize_user_facing_text(raw)
    assert "91" not in out or "匹配" not in out
    assert "拉动" not in out
    assert "学习 Java" in out


def test_skeleton_actions_from_refs():
    item = {
        "focus_dimension": "cap_req_digital",
        "focus_label": "数字素养",
        "learning_path_refs": [{"label": "Redis入门", "url": "http://x"}],
        "practice_plan_refs": [],
    }
    acts = build_skeleton_custom_actions(
        item, company="甲公司", job_title="Java开发", plan_month=2, phase_key="early"
    )
    assert len(acts) >= 3
    assert any("Redis" in a["text"] for a in acts)
    assert any(a["kind"] == "deliverable" for a in acts)


def test_enrich_merges_failed_metric_remediation():
    item = {
        "focus_dimension": "cap_req_practice",
        "focus_label": "实践",
        "milestone": "完成小项目",
        "custom_actions": [{"kind": "learn", "text": "已有动作"}],
    }
    failed = [
        {"code": "delivery_output", "label": "成果", "passed": False},
    ]
    out = enrich_plan_item(
        item,
        plan_month=2,
        phase_key="early",
        replan_mode="light",
        company="乙公司",
        job_title="前端",
        match_score=62.0,
        failed_rows=failed,
    )
    assert out.get("growth_rationale")
    assert len(out["custom_actions"]) >= 3
    assert out.get("metric_target_labels")
    assert "delivery_output" not in str(out.get("metric_target_labels"))
    texts = " ".join(a["text"] for a in out["custom_actions"])
    assert "成果" in texts or "交付" in texts


def test_remediation_actions_for_failed_rows():
    rows = [
        {"code": "dim_gap_reduction", "passed": False},
        {"code": "project_completion", "passed": False},
    ]
    acts = remediation_actions_for_failed_rows(rows)
    assert len(acts) == 2
    assert acts[0]["kind"] in ("learn", "practice", "deliverable")
