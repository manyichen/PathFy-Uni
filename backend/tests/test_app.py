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
