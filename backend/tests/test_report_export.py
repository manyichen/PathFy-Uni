"""生涯报告 PDF/HTML 导出。"""
from app.domains.report.export import build_report_export_html


def test_export_per_job_chapters():
    report = {
        "student": {"display_name": "测试"},
        "targets": [{"title": "Java 开发", "company": "A 公司", "match_preview": {"match_score": 72}}],
        "plans_by_target": [
            {
                "display_title": "Java 开发工程师",
                "job_title_name": "Java",
                "match_score": 72,
                "top_gap_labels": ["实践"],
                "phases": {
                    "early": {"label": "前期", "period": "0-3个月", "summary": "打基础", "items": []},
                    "mid": {"label": "中期", "period": "3-9个月", "summary": "做项目", "items": []},
                    "late": {"label": "后期", "period": "9-12个月", "summary": "冲刺", "items": []},
                },
                "narrative": {
                    "path_advice": "先补实践短板",
                    "execution_reminder": "每周复盘",
                    "provider": "doubao",
                },
                "recommendations": {"learning_resources": [], "competitions": []},
            }
        ],
        "evaluation": {"metrics": []},
        "narrative": {"text": "全局建议"},
    }
    html = build_report_export_html(1, "测试报告", report)
    assert "三、分岗位成长计划（按章）" in html
    assert "第1章 · Java 开发工程师" in html
    assert "四、评估指标" in html
    assert "五、总体建议（全局）" in html
    assert "叙事来源：doubao" in html
