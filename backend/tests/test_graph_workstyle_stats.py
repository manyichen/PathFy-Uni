from app.domains.graph import services


class FakeRecord(dict):
    def single(self):
        return self


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, query, **_params):
        if "workstyle_total" in query:
            return FakeRecord(workstyle_total=10, workstyle_evidenced=7, workstyle_ready=5, workstyle_inherited=2)
        return FakeRecord(jobs=10, capability_missing=1, capability_stale=0, low_confidence=2, salary_stale=3,
                          inferred_jobs=0, low_frequency_titles=1, curated_lateral=2, auto_lateral=3,
                          curated_promotions=1, auto_promotions=4)


class FakeDriver:
    def session(self, **_kwargs):
        return FakeSession()


def test_graph_stats_exposes_workstyle_evidence_coverage(monkeypatch):
    monkeypatch.setattr(services, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(services, "neo4j_driver", lambda *_args: FakeDriver())
    monkeypatch.setattr(services, "get_graph_statistics", lambda *_args: {"job_count": 10})
    monkeypatch.setattr(services, "setting", lambda _key, default=None: default)
    result = services.get_stats()
    assert result["workstyle_ready"] == 5
    assert result["workstyle_missing"] == 3
    assert result["workstyle_coverage_percent"] == 50
