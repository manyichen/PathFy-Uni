"""应用入口与健康检查。"""

from __future__ import annotations


def test_create_app_importable():
    from app import create_app

    app = create_app()
    assert app is not None


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert "message" in body
    assert res.headers.get("Cache-Control") == "no-store, max-age=0"
    assert res.headers.get("X-Content-Type-Options") == "nosniff"


def test_index_lists_routes(client):
    res = client.get("/")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert any("health" in r for r in body.get("routes", []))


def test_not_found_envelope(client):
    res = client.get("/api/no-such-route")
    assert res.status_code == 404
    body = res.get_json()
    assert body["ok"] is False


def test_route_contract_inventory(app):
    """Guard the public route surface while internal modules are reorganized."""
    routes = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }
    assert len(routes) == 86
    assert ("/api/profile/upload", "POST") in routes
    assert ("/api/jobs/<path:job_id>/promotion-path", "GET") in routes
    assert ("/api/match/preview", "POST") in routes
    assert ("/api/personality/me/latest", "GET") in routes
    assert ("/api/personality/me/profiles", "GET") in routes
    assert ("/api/personality/profiles/<int:profile_id>", "GET") in routes
    assert ("/api/personality/profiles/<int:profile_id>/activate", "POST") in routes
    assert ("/api/personality/profiles/<int:profile_id>/preferences", "PATCH") in routes
    assert ("/api/personality/profiles/<int:profile_id>", "DELETE") in routes
    assert ("/api/report/generate", "POST") in routes
    assert ("/api/report/<int:report_id>/enrichment", "POST") in routes
    assert ("/api/report/<int:report_id>/enrichment", "GET") in routes
    assert ("/api/report/<int:report_id>/preference-strategy", "PATCH") in routes
    assert ("/api/report/review-drafts", "POST") in routes
    assert ("/api/report/review-drafts/<int:draft_id>/confirm", "POST") in routes
    assert ("/api/report/<int:report_id>/plan-versions", "GET") in routes
    assert ("/api/report/plan-proposals/<int:proposal_id>/decision", "POST") in routes
    assert ("/api/report/<int:report_id>/plan-actions", "POST") in routes
    assert ("/api/report/<int:report_id>/plan-actions/<path:action_uid>", "PATCH") in routes
    assert ("/api/report/<int:report_id>/plan-actions/<path:action_uid>", "DELETE") in routes
    assert ("/api/report/<int:report_id>/export/data", "GET") in routes
    assert ("/api/report/<int:report_id>/export/pdf", "POST") in routes
    assert ("/api/report/<int:report_id>", "DELETE") in routes
    assert ("/api/report/operations/metrics", "GET") in routes
    assert ("/api/graph/sync/job-titles", "POST") in routes
    assert ("/api/graph/import-runs", "GET") in routes
    assert ("/api/graph/tasks", "POST") in routes
    assert ("/api/graph/tasks", "GET") in routes
    assert ("/api/graph/tasks/<int:task_id>", "GET") in routes
    assert ("/api/graph/tasks/<int:task_id>/changes", "GET") in routes
    assert ("/api/graph/tasks/<int:task_id>/files/<string:role>/download", "GET") in routes
    assert ("/api/graph/tasks/<int:task_id>/confirm", "POST") in routes
    assert ("/api/graph/tasks/<int:task_id>/reject", "POST") in routes
    assert ("/api/graph/tasks/<int:task_id>/cancel", "POST") in routes
    assert ("/api/graph/guard", "GET") in routes
    assert ("/api/admin/settings", "GET") in routes
    assert ("/api/admin/settings/publish", "POST") in routes
    assert ("/api/admin/settings/history", "GET") in routes
    assert ("/api/admin/settings/revisions/<int:revision>", "GET") in routes
    assert ("/api/account/preferences", "GET") in routes
    assert ("/api/account/preferences", "PATCH") in routes
