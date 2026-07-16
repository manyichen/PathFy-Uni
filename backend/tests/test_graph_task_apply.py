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


def test_v2_job_apply_only_deletes_reviewed_manifest_rows():
    tx = FakeTx()
    change = {
        "version": 2,
        "kind": "job_import",
        "source_id": "feed-a",
        "mode": "snapshot",
        "input_keys": [],
        "jobs": [],
        "job_titles": [],
        "promotions": [],
        "lateral": [],
        "delete_manifest": {
            "jobs": [{"job_key": "old-job", "source_id": "feed-a"}],
            "job_titles": [{"name": "旧岗位"}],
            "promotions": [{"promotion_id": "old-promotion"}],
            "lateral": [{"from": "旧岗位", "to": "新岗位"}],
        },
    }

    task_apply._apply_job(tx, change, "run-1")

    queries = [query for query, _ in tx.queries]
    assert not any("last_seen_run_id,'')<>$run DETACH DELETE j" in query for query in queries)
    assert not any("generation_run_id,'')<>$run DETACH DELETE p" in query for query in queries)
    assert not any("generation_run_id,'')<>$run DELETE r" in query for query in queries)
    assert any("item.job_key" in query for query in queries)
    title_delete = next(query for query in queries if "item.name" in query and "DETACH DELETE jt" in query)
    assert "generation_source,'')='curated'" in title_delete


def test_v2_snapshot_without_manifest_never_derives_resource_deletes():
    tx = FakeTx()
    task_apply._apply_resources(
        tx,
        {"version": 2, "kind": "learning_resource_import", "source_id": "feed-a", "mode": "snapshot", "items": []},
        "run-1",
    )
    queries = [query for query, _ in tx.queries]
    assert not any("NOT r.resource_id IN" in query for query in queries)
    assert not any("DETACH DELETE r" in query for query in queries)


def test_chunk_loader_uses_one_unwind_per_chunk_not_per_item():
    tx = FakeTx()
    chunks = {
        "jobs": [
            [{"job_key": "j1", "capability": {"cap_req_theory": 70}},
             {"job_key": "j2", "capability": {"cap_req_theory": 80}}],
            [{"job_key": "j3", "capability": {"cap_req_theory": 90}}],
        ]
    }
    task_apply._apply_capabilities(tx, {"version": 2}, "run", lambda group: chunks.get(group, []))
    assert len(tx.queries) == 2
    assert all("UNWIND $rows" in query for query, _ in tx.queries)
    assert [len(params["rows"]) for _, params in tx.queries] == [2, 1]
