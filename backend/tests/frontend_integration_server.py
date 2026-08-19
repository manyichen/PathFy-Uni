"""Deterministic Flask API used by Playwright's frontend integration gate.

This process deliberately keeps an in-memory test database and stable OCR/graph/LLM
results. The browser talks to it through Nuxt's normal /api proxy; Playwright does
not intercept or fulfill API requests.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from flask import Flask, jsonify, request


app = Flask(__name__)
state: dict[str, object] = {"users": [], "profiles": [], "matches": [], "reports": [], "enrichment_polls": []}


def ok(data=None, status=200):
    return jsonify({"ok": status < 400, "code": status, "data": data}), status


def legacy(data=None, status=200):
    return jsonify({"code": status, "data": data}), status


def now():
    return datetime.now(UTC).isoformat()


def scores():
    return {
        "cap_req_theory": 82, "cap_req_cross": 75, "cap_req_practice": 88,
        "cap_req_digital": 91, "cap_req_innovation": 78, "cap_req_teamwork": 84,
        "cap_req_social": 70, "cap_req_growth": 86,
    }


def job():
    return {"id": "job-integration-1", "job_id": "job-integration-1", "title": "数据分析师", "display_title": "数据分析师", "company": "集成测试科技", "location": "上海", "salary": "15-22K", **scores()}


def report_payload():
    target = {
        **job(),
        "scores": scores(),
        "match_preview": {"match_score": 88, "dimension_gaps": {"cap_req_cross": 9, "cap_req_social": 8}},
        "track_profile": {"job_title": "数据分析师", "hiring_visibility_0_100": 84, "path_breadth_0_100": 81, "resource_density_0_100": 79},
    }
    return {
        "generated_at": now(), "targets": [target],
        "narrative": {"text": "集成测试报告骨架已由 Flask 测试实例生成。"},
        "plans_by_target": [{
            "job_id": target["job_id"], "display_title": target["title"], "match_score": 88,
            "next_month_plan": {"phase_label": "基础强化", "plan_month": 1, "items": [{"focus_label": "实践技能", "milestone": "完成端到端分析案例", "custom_actions": [{"text": "提交一次案例复盘", "done": False}]}]},
            "phases": {"short": {"label": "短期", "period": "1-3 个月", "items": [{"order": 1, "focus_dimension": "cap_req_practice", "focus_label": "实践技能", "milestone": "完成作品集"}]}},
        }],
        "development_lines": {"lines": [{"line_id": "integration-line", "line_name": "数据分析师成长线", "target_job_id": target["job_id"], "timeline": [{"month": 0, "progress": 10, "label": "起点"}, {"month": 3, "progress": 65, "label": "作品集"}]}], "adjustments": []},
        "evaluation": {"metrics": [{"code": "portfolio", "label": "作品集完成度", "target": "完成 1 个案例"}]},
    }


@app.get("/api/health")
def health():
    return ok({"service": "frontend-integration", "database": "memory", "stubs": ["neo4j", "llm", "ocr"]})


@app.post("/api/auth/register")
def register():
    body = request.get_json(silent=True) or {}
    user = {"id": 1, "username": body.get("username") or "集成测试用户", "email": body.get("email") or "integration@example.com", "is_admin": False}
    state["users"] = [user]
    return ok({"token": "integration-token", "user": user})


@app.get("/api/auth/me")
def me():
    users = state["users"]
    return ok({"user": users[0] if users else {"id": 1, "username": "集成测试用户", "email": "integration@example.com", "is_admin": False}})


@app.get("/api/account/preferences")
def preferences():
    values = {"theme": "light", "hue": "192", "default_match_goal": "fit", "default_refine_with_llm": False, "match_result_count": 30, "learning_resource_count": 5, "competition_count": 3}
    return ok({"stored": False, "preferences": values, "effective": values, "limits": {"match_result_count": 100, "learning_resource_count": 20, "competition_count": 10}})


@app.get("/api/profile/resumes")
def resumes():
    return legacy([{"id": row["id"], "name": row["name"], "major": row["major"], "create_time": row["create_time"]} for row in state["profiles"]])


@app.post("/api/profile/upload")
def upload_profile():
    profile = {
        "id": 1, "resume_id": 1, "name": request.form.get("name", "集成测试用户"), "major": request.form.get("major", "计算机科学"),
        **scores(), "completeness": 86, "competitiveness": 84, "create_time": now(),
        "detailed_analysis": {"overall_evaluation": "稳定 fixture 表明画像链路工作正常。", "completeness_analysis": "材料完整。", "competitiveness_analysis": "实践与数字能力突出。", "material_summary": [{"name": "补充文本", "kind": "补充材料", "status": "ok", "chars": len(request.form.get("profile_text", ""))}], "advantage_dimensions": [{"dimension": "数字素养", "score": 91}], "weakness_dimensions": [{"dimension": "社会网络", "score": 70}]},
    }
    state["profiles"] = [profile]
    return legacy(profile)


@app.get("/api/profile/result/<int:profile_id>")
def profile_result(profile_id):
    profiles = state["profiles"]
    return legacy(profiles[0] if profiles else {}, 200 if profiles else 404)


@app.post("/api/match/preview")
def match_preview():
    body = request.get_json(silent=True) or {}
    result = {"resume_id": body.get("resume_id", 1), "student": {"scores": scores()}, "jobs": [{"job": job(), "match_score": 88, "reason": "稳定 fixture 验证八维匹配链路。"}], "filters": {"q": body.get("q", ""), "location_q": body.get("location_q", ""), "match_goal": body.get("match_goal", "fit")}}
    run = {"run_id": 1, "resume_id": 1, "student_name": "集成测试用户", "match_goal": body.get("match_goal", "fit"), "q": body.get("q", ""), "returned": 1, "created_at": now(), "result": result}
    state["matches"] = [run]
    return ok(result)


@app.get("/api/match/history")
def match_history():
    return ok({"items": [{key: value for key, value in row.items() if key != "result"} for row in state["matches"]]})


@app.get("/api/match/history/<int:run_id>")
def match_detail(run_id):
    matches = state["matches"]
    return ok(matches[0]["result"] if matches else {"student": {}, "jobs": []})


@app.post("/api/report/targets/import-from-match")
def import_match():
    return ok({"run_id": 1, "resume_id": 1, "match_goal": "fit", "source": "integration", "targets": [job()]})


@app.post("/api/report/generate")
def generate_report():
    payload = report_payload()
    payload["llm_enrich_pending"] = True
    record = {"report_id": 1, "resume_id": 1, "primary_job_id": "job-integration-1", "target_job_ids": ["job-integration-1"], "report": payload, "llm_enrich_pending": True}
    state["reports"] = [record]
    state["enrichment_polls"] = []
    return ok(record)


@app.post("/api/report/<int:report_id>/enrichment")
def start_enrichment(report_id):
    return ok({"report_id": report_id, "status": "queued", "attempt": 1}, 202)


@app.get("/api/report/<int:report_id>/enrichment")
def enrichment_status(report_id):
    polls = state["enrichment_polls"]
    polls.append(now())
    if len(polls) < 2:
        return ok({"report_id": report_id, "status": "running", "attempt": 1})
    reports = state["reports"]
    if reports:
        reports[0]["llm_enrich_pending"] = False
        reports[0]["report"]["llm_enrich_pending"] = False
    return ok({"report_id": report_id, "status": "completed", "attempt": 1})


@app.get("/api/report/<int:report_id>")
def report_detail(report_id):
    reports = state["reports"]
    return ok(reports[0] if reports else {"report_id": report_id, "report": report_payload(), "llm_enrich_pending": False})


@app.get("/api/report/<int:report_id>/reviews")
def report_reviews(report_id):
    return ok({"items": []})


@app.get("/api/report/my/list")
def reports():
    return ok({"items": [{"report_id": row["report_id"], "title": "集成测试生涯报告"} for row in state["reports"]]})


@app.get("/__test__/state")
def test_state():
    return jsonify({key: len(value) for key, value in state.items()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PATHFY_INTEGRATION_PORT", "5011")), debug=False, use_reloader=False)
