"""Failure boundaries for interactive career-graph endpoints."""

from flask import Flask

from app.domains.jobs import router
from app.infrastructure.neo4j import neo4j_query


class _UnavailableDriver:
    def session(self, **_kwargs):
        raise ConnectionError("neo4j unavailable")


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, *_args):
        return False


class _AvailableDriver:
    def session(self, **_kwargs):
        return _SessionContext()


def _client(monkeypatch, driver):
    app = Flask(__name__)
    app.config.update(TESTING=True, JOBS_TRANSITION_LLM_ENABLED=False)
    app.register_blueprint(router.jobs_bp)
    monkeypatch.setattr(router, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(router, "neo4j_driver", lambda *_args: driver)
    return app.test_client()


def test_graph_endpoints_return_json_503_when_neo4j_is_unavailable(monkeypatch):
    client = _client(monkeypatch, _UnavailableDriver())

    responses = [
        client.get("/api/jobs/job-1/promotion-path"),
        client.get("/api/jobs/job-1/lateral-paths"),
        client.post(
            "/api/jobs/transition-analysis",
            json={"from_job_id": "job-1", "to_job_id": "job-2"},
        ),
    ]

    assert [response.status_code for response in responses] == [503, 503, 503]
    assert all(response.is_json for response in responses)
    assert all(response.get_json()["ok"] is False for response in responses)


def test_transition_uses_fast_deterministic_advice_by_default(monkeypatch):
    client = _client(monkeypatch, _AvailableDriver())
    rows = {
        "job-1": {
            "id": "job-1", "title": "开发工程师", "company": "A", "location": "上海",
            "salary": "15K", "salary_raw": "15K", "experience_years": 1,
            "requirement_names": ["Python"],
        },
        "job-2": {
            "id": "job-2", "title": "高级开发工程师", "company": "B", "location": "上海",
            "salary": "25K", "salary_raw": "25K", "experience_years": 3,
            "requirement_names": ["Python", "系统设计"],
        },
    }
    for row in rows.values():
        row.update({key: 60 for key in router.DIM_KEYS})
    monkeypatch.setattr(router, "_fetch_job_for_analysis", lambda _session, job_id: rows[job_id])
    monkeypatch.setattr(
        router,
        "_llm_transition_advice",
        lambda *_args: (_ for _ in ()).throw(AssertionError("LLM must not run")),
    )

    response = client.post(
        "/api/jobs/transition-analysis",
        json={"from_job_id": "job-1", "to_job_id": "job-2"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["meta"]["advice_source"] == "deterministic"


def test_neo4j_query_applies_configured_server_deadline():
    captured = {}

    class Session:
        def run(self, query, parameters):
            captured["query"] = query
            captured["parameters"] = parameters
            return "result"

    app = Flask(__name__)
    app.config["NEO4J_QUERY_TIMEOUT_SECONDS"] = 7
    with app.app_context():
        result = neo4j_query(Session(), "RETURN $value", {"value": 1})

    assert result == "result"
    assert captured["query"].timeout == 7
    assert captured["parameters"] == {"value": 1}
