from app.domains.graph import task_apply


class FakeTx:
    def __init__(self): self.queries = []
    def run(self, query, **params): self.queries.append((query, params)); return []


class FakeSession:
    def __init__(self): self.tx = FakeTx()
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def run(self, query, **params): return self.tx.run(query, **params)
    def execute_write(self, handler): return handler(self.tx)


class FakeDriver:
    def __init__(self): self.value = FakeSession()
    def session(self, **_kwargs): return self.value


def test_resource_change_set_uses_one_transaction_and_commit_marker(monkeypatch):
    driver = FakeDriver()
    monkeypatch.setattr(task_apply, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(task_apply, "neo4j_driver", lambda *_args: driver)
    monkeypatch.setattr(task_apply, "is_task_applied", lambda _uuid: False)
    change = {"kind": "learning_resource_import", "source_id": "master", "mode": "snapshot", "items": [{"resource_id": "r1", "resource_name": "课程", "job_titles": ["Java"]}]}
    result = task_apply.apply_change_set(change, task_uuid="a" * 32, change_sha256="b" * 64)
    queries = [query for query, _ in driver.value.tx.queries]
    assert result["kind"] == "learning_resource_import"
    assert any("MERGE (r:LearningResource" in query for query in queries)
    assert any("GraphTaskCommit" in query for query in queries)


def test_already_applied_task_is_idempotent(monkeypatch):
    monkeypatch.setattr(task_apply, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(task_apply, "neo4j_driver", lambda *_args: FakeDriver())
    monkeypatch.setattr(task_apply, "is_task_applied", lambda _uuid: True)
    result = task_apply.apply_change_set({"kind": "competition_import"}, task_uuid="a" * 32, change_sha256="b" * 64)
    assert result["already_applied"] is True


def test_capability_change_set_updates_jobs_in_same_transaction(monkeypatch):
    driver = FakeDriver()
    monkeypatch.setattr(task_apply, "neo4j_settings", lambda: ("bolt://test", "neo4j", "pw", "neo4j"))
    monkeypatch.setattr(task_apply, "neo4j_driver", lambda *_args: driver)
    monkeypatch.setattr(task_apply, "is_task_applied", lambda _uuid: False)
    task_apply.apply_change_set({"version": 2, "kind": "job_capability_evaluation", "jobs": [{"job_key": "j1", "capability": {"cap_req_theory": 70}}]}, task_uuid="c" * 32, change_sha256="d" * 64)
    queries = [query for query, _ in driver.value.tx.queries]
    assert any("cap_updated_at" in query for query in queries)
    assert any("GraphTaskCommit" in query for query in queries)
