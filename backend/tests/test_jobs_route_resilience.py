"""HTTP failure contract for the Neo4j-backed jobs list."""

from flask import Flask

from app.domains.jobs import router


class _UnavailableDriver:
    def session(self, **_kwargs):
        raise ConnectionError("neo4j reset")


def test_jobs_list_returns_json_503_when_neo4j_is_unavailable(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(router.jobs_bp)
    monkeypatch.setattr(router, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(router, "neo4j_driver", lambda *_args: _UnavailableDriver())

    response = app.test_client().get("/api/jobs?page=1&page_size=20")

    assert response.status_code == 503
    assert response.is_json
    assert response.get_json() == {
        "ok": False,
        "message": "岗位数据服务暂时不可用，请稍后重试",
    }


def test_job_detail_returns_json_503_when_neo4j_is_unavailable(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(router.jobs_bp)
    monkeypatch.setattr(router, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(router, "neo4j_driver", lambda *_args: _UnavailableDriver())

    response = app.test_client().get("/api/jobs/job-1")

    assert response.status_code == 503
    assert response.is_json
    assert response.get_json()["ok"] is False
    assert "暂时" in response.get_json()["message"] or "超时" in response.get_json()["message"]
