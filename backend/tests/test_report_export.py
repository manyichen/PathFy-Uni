"""生涯报告 PDF/HTML 导出。"""
import copy
import pytest

from app.domains.report.export import (
    ReportExportValidationError,
    build_report_export_html,
    normalize_export_options,
)


def _report():
    return {
        "summary": "聚焦 Java 工程实践，先完成一个可核对项目。",
        "targets": [
            {"id": "job-1", "title": "Java 开发", "company": "A 公司", "match_preview": {"match_score": 72}},
            {"id": "job-2", "title": "数据分析", "company": "B 公司", "match_preview": {"match_score": 66}},
        ],
        "plans_by_target": [{
            "job_id": "job-1", "display_title": "Java 开发工程师",
            "phases": {"early": {"label": "前期", "period": "0-3个月", "summary": "打基础", "items": []}},
            "recommendations": {"learning_resources": [{"resource_name": "Java 入门", "resource_url": "https://example.com/java"}]},
        }],
        "decision_support": {"target_decisions": [{
            "job_id": "job-1", "display_title": "Java 开发工程师",
            "actions": [{"title": "完成接口项目", "status": "todo", "deliverable": "仓库链接", "acceptance_criteria": ["可运行"]}],
            "claims": [{"kind": "gap", "title": "项目证据不足", "summary": "暂无完整项目", "impact": "面试说服力不足", "facts": [{"label": "项目数", "value": 0, "source_label": "简历画像", "evidence_grade": "B"}]}],
        }]},
        "evaluation": {"latest_review": {"review_id": 3, "review_text": "完成第一版接口", "evaluation": {"pass_rate": 0.5}}},
        "longitudinal_insights": {"execution_profile": {"diagnosis_label": "按计划推进"}},
        "preference_strategy": {"sections": [{"title": "协作方式", "recommendation": "先书面同步", "rationale": "偏好结构化表达", "alternative": "短会确认"}]},
    }


def test_export_uses_current_workspace_sections():
    html = build_report_export_html(1, "测试报告", _report())
    for heading in ("当前判断", "本月行动", "判断依据", "推进路线", "复盘与校准", "资源清单", "执行方式建议"):
        assert heading in html
    assert "完成接口项目" in html
    assert "项目证据不足" in html
    assert "完成第一版接口" in html
    assert "编辑项仅影响本次 PDF，不会回写原报告" in html


def test_export_filters_target_action_scope_and_sections_and_escapes_copy():
    report = _report()
    report["decision_support"]["target_decisions"][0]["actions"].append({"title": "已完成行动", "status": "done"})
    source_snapshot = copy.deepcopy(report)
    html = build_report_export_html(2, "源报告", report, {
        "document_title": "<script>alert(1)</script>",
        "executive_summary": "自定义摘要",
        "selected_target_job_ids": ["job-1"],
        "sections": {"overview": True, "actions": True, "evidence": False, "route": False, "review": False, "resources": False, "preference": False},
        "action_scope": "todo",
        "closing_note": "仅用于求职准备",
    })
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "自定义摘要" in html
    assert "Java 开发" in html
    assert "数据分析" not in html
    assert "完成接口项目" in html
    assert "已完成行动" not in html
    assert "判断依据" not in html
    assert "仅用于求职准备" in html
    assert report == source_snapshot


def test_export_rejects_empty_target_or_sections():
    with pytest.raises(ReportExportValidationError, match="请填写 PDF 标题"):
        normalize_export_options("测试", _report(), {"document_title": "   "})
    with pytest.raises(ReportExportValidationError, match="至少选择一个目标岗位"):
        normalize_export_options("测试", _report(), {"selected_target_job_ids": []})
    with pytest.raises(ReportExportValidationError, match="至少保留一个报告章节"):
        normalize_export_options("测试", _report(), {"sections": {key: False for key in ("overview", "actions", "evidence", "route", "review", "resources", "preference")}})


def test_export_service_forwards_the_temporary_copy(monkeypatch):
    from app.domains.report import services

    rendered = {}
    monkeypatch.setattr(services, "fetch_report_for_export", lambda user_id, report_id: {
        "id": report_id, "title": "源报告", "report_json": _report()
    })
    monkeypatch.setattr(services, "render_pdf_with_playwright", lambda html: rendered.setdefault("html", html) and b"%PDF-test")
    pdf, filename = services.export_career_report_pdf(7, 8, {
        "document_title": "面试准备版",
        "selected_target_job_ids": ["job-1"],
    })
    assert pdf == b"%PDF-test"
    assert filename == "career_report_8.pdf"
    assert "面试准备版" in rendered["html"]
