from __future__ import annotations

from io import BytesIO

import pytest

from app.domains.graph import router as graph_router
from app.domains.graph import task_planner


@pytest.fixture(autouse=True)
def _admin(monkeypatch):
    monkeypatch.setattr(graph_router, "_require_admin", lambda: (7, None))


def test_create_graph_task_reads_multipart_options(client, monkeypatch):
    captured = {}
    def enqueue(**kwargs):
        captured.update(kwargs); return {"id": 12, "status": "queued"}
    monkeypatch.setattr(graph_router, "enqueue_task", enqueue)
    response = client.post("/api/graph/tasks", data={
        "task_type": "job_import", "file": (BytesIO(b"excel"), "jobs.xlsx"),
        "batch_size": "64", "mode": "snapshot", "source_id": "monthly",
        "generate_promotions": "true", "generate_lateral": "false",
    }, content_type="multipart/form-data")
    assert response.status_code == 202
    assert captured["user_id"] == 7
    assert captured["task_type"] == "job_import"
    assert captured["uploaded_file"].filename == "jobs.xlsx"
    assert captured["mode"] == "snapshot"
    assert captured["generate_promotions"] is True
    assert captured["generate_lateral"] is False


def test_direct_graph_writers_are_gone(client):
    for path in (
        "/api/graph/import-jobs", "/api/graph/sync/job-titles",
        "/api/graph/generate/promotion-paths", "/api/graph/generate/lateral-transfers",
        "/api/graph/generate/learning-resources", "/api/graph/generate/competitions",
    ):
        response = client.post(path, json={})
        assert response.status_code == 410
        assert response.get_json()["ok"] is False


def test_task_list_and_detail_are_admin_scoped(client, monkeypatch):
    monkeypatch.setattr(graph_router, "list_tasks", lambda **kw: {"items": [{"id": 1}], "total": 1, **kw})
    monkeypatch.setattr(graph_router, "task_detail", lambda task_id: {"id": task_id, "events": []})
    assert client.get("/api/graph/tasks?page=2&page_size=10").get_json()["data"]["page"] == 2
    assert client.get("/api/graph/tasks/9").get_json()["data"]["id"] == 9


def test_confirm_reject_cancel_routes(client, monkeypatch):
    monkeypatch.setattr(graph_router, "confirm_task", lambda task_id, user_id: {"id": task_id, "user": user_id})
    monkeypatch.setattr(graph_router, "reject_task", lambda task_id, user_id, reason: {"reason": reason})
    monkeypatch.setattr(graph_router, "cancel_task", lambda task_id, user_id: {"status": "cancelled"})
    assert client.post("/api/graph/tasks/4/confirm").status_code == 200
    assert client.post("/api/graph/tasks/4/reject", json={"reason": "数据异常"}).get_json()["data"]["reason"] == "数据异常"
    assert client.post("/api/graph/tasks/4/cancel").get_json()["data"]["status"] == "cancelled"


class _TitleSession:
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def run(self, *_args, **_kwargs): return [{"name": "Java"}, {"name": "测试"}]


class _TitleDriver:
    def session(self, **_kwargs): return _TitleSession()


def test_resource_csv_schema_and_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(task_planner, "_driver", lambda: (_TitleDriver(), "neo4j"))
    path = tmp_path / "resources.csv"
    path.write_text(
        "resource_id,job_name,resource_name,resource_desc,resource_url,resource_type,difficulty,source,skill_tag\n"
        "r1,Java|测试,课程,说明,https://example.com,课程,入门,官方,Java\n",
        encoding="utf-8",
    )
    task = {"input_file_path": str(path), "source_id": "resources", "mode": "snapshot"}
    change, summary = task_planner._plan_csv(task, kind="learning_resource_import", required=task_planner.RESOURCE_COLUMNS, id_column="resource_id")
    assert summary == {"items": 1, "job_title_links": 2, "snapshot_prune": True}
    assert change["items"][0]["job_titles"] == ["Java", "测试"]


def test_competition_csv_rejects_duplicate_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(task_planner, "_driver", lambda: (_TitleDriver(), "neo4j"))
    header = ",".join(sorted(task_planner.COMPETITION_COLUMNS))
    values = {key: "x" for key in task_planner.COMPETITION_COLUMNS}; values["competition_id"] = "c1"; values["job_name"] = "Java"
    row = ",".join(values[key] for key in sorted(task_planner.COMPETITION_COLUMNS))
    path = tmp_path / "competitions.csv"; path.write_text(f"{header}\n{row}\n{row}\n", encoding="utf-8")
    with pytest.raises(task_planner.TaskPlanningError, match="重复"):
        task_planner._plan_csv({"input_file_path": str(path), "source_id": "c", "mode": "merge"}, kind="competition_import", required=task_planner.COMPETITION_COLUMNS, id_column="competition_id")
