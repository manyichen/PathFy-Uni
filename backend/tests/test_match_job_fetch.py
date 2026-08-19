"""Regression coverage for the Neo4j-backed matching job reader."""

from __future__ import annotations

from flask import Flask

from app.domains.match import services
from app.infrastructure.neo4j import CONF_KEYS, DIM_KEYS


class _Record(dict):
    pass


class _Session:
    def __init__(self, records):
        self.records = records
        self.query = ""
        self.params = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, query, params):
        self.query = query
        self.params = params
        return self.records


class _Driver:
    def __init__(self, session):
        self._session = session
        self.database = None

    def session(self, *, database):
        self.database = database
        return self._session


def test_fetch_jobs_uses_property_map_and_preserves_contract(monkeypatch):
    properties = {
        "job_key": "job-1",
        "title": "数据分析师",
        "salary": "15-20K",
        "company": "示例公司",
        "location": "上海",
        "cap_req_theory": 72,
        "cap_conf_growth": 0.81,
    }
    session = _Session([_Record(job=properties, element_id="node-1")])
    driver = _Driver(session)
    monkeypatch.setattr(services, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(services, "neo4j_driver", lambda *_args: driver)

    rows = services._fetch_jobs_for_match("数据", "上海", 40)

    assert driver.database == "neo4j"
    assert "RETURN properties(j) AS job" in session.query
    assert "coalesce(j.cap_req_theory" not in session.query
    assert session.params == {"q": "数据", "loc": "上海", "cap": 40}
    assert rows[0]["id"] == "job-1"
    assert rows[0]["title"] == "数据分析师"
    assert rows[0]["salary"] == "15-20K"
    assert rows[0]["cap_req_theory"] == 72
    assert rows[0]["cap_conf_growth"] == 0.81
    assert all(key in rows[0] for key in (*DIM_KEYS, *CONF_KEYS))


def test_job_property_normalization_has_safe_fallbacks():
    row = services._job_properties_to_match_row({}, "node-fallback")

    assert row["id"] == "node-fallback"
    assert row["title"] == "未命名岗位"
    assert row["salary"] == "薪资面议"
    assert row["company"] == "未知公司"
    assert row["location"] == "未知地点"
    assert row["risk_flags"] == []
    assert all(row[key] == 0.0 for key in (*DIM_KEYS, *CONF_KEYS))


def test_match_preview_reports_graph_outage_as_retryable_503(monkeypatch):
    app = Flask(__name__)
    app.config["MATCH_PREVIEW_MAX_SCAN_HARD"] = 8000
    profile = {
        "id": "1",
        "display_name": "测试画像",
        "scores": {key: 60.0 for key in DIM_KEYS},
        "confidences": {key: 0.6 for key in CONF_KEYS},
    }
    monkeypatch.setattr(services, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(services, "_resolve_student_profile", lambda *_args: (profile, None))
    monkeypatch.setattr(services, "setting", lambda _name, default=None: default)
    monkeypatch.setattr(services, "_fetch_jobs_for_match", lambda **_kwargs: (_ for _ in ()).throw(ConnectionError("reset")))

    with app.app_context():
        data, error, status = services.run_match_preview({"resume_id": 1}, 1)

    assert data is None
    assert error == "岗位数据服务暂时不可用，请稍后重试"
    assert status == 503
