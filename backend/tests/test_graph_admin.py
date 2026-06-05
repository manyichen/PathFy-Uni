from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from app.domains.graph import repository as graph_repository
from app.domains.graph import router as graph_router
from app.domains.graph import services as graph_services
from app.domains.graph import sync_service as graph_sync_service


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_import_jobs_reads_multipart_options(client, monkeypatch):
    captured = {}

    monkeypatch.setattr(graph_router, "_require_admin", lambda: (1, None))

    def fake_import_jobs_from_excel(*, excel_path, uploaded_file, batch_size, clear_all):
        captured.update(
            {
                "excel_path": excel_path,
                "uploaded_filename": uploaded_file.filename,
                "batch_size": batch_size,
                "clear_all": clear_all,
            }
        )
        return {"total_jobs": 0, "batches_completed": 0, "batches_failed": 0}

    monkeypatch.setattr(
        graph_router, "import_jobs_from_excel", fake_import_jobs_from_excel
    )

    res = client.post(
        "/api/graph/import-jobs",
        data={
            "file": (BytesIO(b"excel"), "jobs.xls"),
            "batch_size": "256",
            "clear_all": "true",
        },
        content_type="multipart/form-data",
    )

    assert res.status_code == 200
    assert captured == {
        "excel_path": None,
        "uploaded_filename": "jobs.xls",
        "batch_size": 256,
        "clear_all": True,
    }


def test_import_jobs_keeps_json_options(client, monkeypatch):
    captured = {}

    monkeypatch.setattr(graph_router, "_require_admin", lambda: (1, None))

    def fake_import_jobs_from_excel(*, excel_path, uploaded_file, batch_size, clear_all):
        captured.update(
            {
                "excel_path": excel_path,
                "uploaded_file": uploaded_file,
                "batch_size": batch_size,
                "clear_all": clear_all,
            }
        )
        return {"total_jobs": 0, "batches_completed": 0, "batches_failed": 0}

    monkeypatch.setattr(
        graph_router, "import_jobs_from_excel", fake_import_jobs_from_excel
    )

    res = client.post(
        "/api/graph/import-jobs",
        json={"file_path": "/data/jobs.xls", "batch_size": 64, "clear_all": True},
    )

    assert res.status_code == 200
    assert captured == {
        "excel_path": "/data/jobs.xls",
        "uploaded_file": None,
        "batch_size": 64,
        "clear_all": True,
    }


def test_delete_edges_by_source_keeps_relationships_in_scope():
    class FakeResult:
        def single(self):
            return {"total": 3}

    class FakeSession:
        def __init__(self):
            self.query = ""
            self.params = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **params):
            self.query = query
            self.params = params
            return FakeResult()

    class FakeDriver:
        def __init__(self):
            self.session_obj = FakeSession()
            self.database = None

        def session(self, *, database):
            self.database = database
            return self.session_obj

    driver = FakeDriver()

    deleted = graph_repository.delete_edges_by_source(
        driver, "neo4j", "openai_lmstudio"
    )

    assert deleted == 3
    assert driver.database == "neo4j"
    assert "collect(r)" in driver.session_obj.query
    assert "DELETE r" in driver.session_obj.query
    assert driver.session_obj.params == {"source": "openai_lmstudio"}


def test_generate_promotions_endpoint_is_deprecated(client, monkeypatch):
    monkeypatch.setattr(graph_router, "_require_admin", lambda: (1, None))

    res = client.post("/api/graph/generate-promotions", json={"dry_run": True})

    assert res.status_code == 410
    body = res.get_json()
    assert body["ok"] is False
    assert "已废弃" in body["message"]
    assert "/api/graph/generate/promotion-paths" in body["message"]


def test_legacy_generate_promotion_edges_service_is_deprecated():
    with pytest.raises(graph_services.GraphServiceError) as exc_info:
        graph_services.generate_promotion_edges(dry_run=True)

    assert exc_info.value.status == 410
    assert "JobTitle" in exc_info.value.message
    assert "/api/graph/generate/promotion-paths" in exc_info.value.message


def test_legacy_persist_promotion_edges_is_deprecated():
    with pytest.raises(RuntimeError) as exc_info:
        graph_repository.persist_promotion_edges(
            object(),
            "neo4j",
            [],
            "openai_lmstudio",
        )

    assert "JobPromotion" in str(exc_info.value)


def test_navbar_separates_admin_and_normal_navigation():
    navbar = (REPO_ROOT / "frontend/src/components/AppNavbar.astro").read_text()

    assert 'adminOnly: true' in navbar
    assert 'userOnly: true' in navbar
    assert 'data-admin-only={item.adminOnly ? "true" : undefined}' in navbar
    assert 'data-user-only={item.userOnly ? "true" : undefined}' in navbar
    assert 'a[data-admin-only="true"]' in navbar
    assert 'a[data-user-only="true"]' in navbar
    assert 'el.classList.toggle("hidden", !isAdmin);' in navbar
    assert 'el.classList.toggle("hidden", isAdmin);' in navbar


def test_graph_manager_uses_jobtitle_promotion_paths():
    manager = (REPO_ROOT / "frontend/src/components/graph/GraphManager.svelte").read_text()

    assert "generatePromotionPaths" in manager
    assert "generatePromotions" not in manager
    assert "VERTICAL_UP" not in manager
    assert "JobTitle" in manager


def test_jobs_promotion_path_reads_jobtitle_layer():
    router = (REPO_ROOT / "backend/app/domains/jobs/router.py").read_text()
    block = router.split('def get_promotion_path(job_id: str):', 1)[1]

    assert "JobPromotion" in block
    assert "JobTitle" in block
    assert "VERTICAL_UP" not in block
    assert "PROMOTION_EDGE_SOURCES" not in block


def test_graph_readme_documents_api_and_principles():
    readme = (REPO_ROOT / "backend/app/domains/graph/README.md").read_text()

    assert "## API 端点" in readme
    assert "## 核心原理" in readme
    assert "### 建图原则" in readme
    assert "### LLM 抽取原则" in readme
    assert "### 晋升路径推断原则" in readme
    assert "### 数据一致性原则" in readme
    assert "generate-promotions` 已废弃" in readme


def test_generate_promotion_paths_uses_stable_ids_and_filters_invalid_titles(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.writes = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **params):
            if "MERGE (pr:JobPromotion" in query:
                self.writes.append(params)
            return []

    class FakeDriver:
        def __init__(self):
            self.session_obj = FakeSession()

        def session(self, *, database):
            return self.session_obj

    driver = FakeDriver()
    monkeypatch.setattr(graph_sync_service, "_get_driver", lambda: (driver, "neo4j"))
    monkeypatch.setattr(
        graph_sync_service,
        "fetch_all_job_titles",
        lambda _driver, _database: ["前端工程师", "高级前端工程师"],
    )
    monkeypatch.setattr(
        graph_sync_service,
        "_call_llm_json",
        lambda *_args, **_kwargs: {
            "paths": [
                {
                    "from_title": "前端工程师",
                    "to_title": "高级前端工程师",
                    "promotion_name": "前端晋升路径",
                    "confidence": "85%",
                },
                {
                    "from_title": "不存在岗位",
                    "to_title": "高级前端工程师",
                    "promotion_name": "无效路径",
                    "confidence": 0.9,
                },
                {
                    "from_title": "前端工程师",
                    "to_title": "不存在岗位",
                    "promotion_name": "无效目标",
                    "confidence": None,
                },
            ]
        },
    )

    result = graph_sync_service.generate_promotion_paths(dry_run=False)

    assert result["created_promotions"] == 1
    assert len(driver.session_obj.writes) == 1
    write = driver.session_obj.writes[0]
    assert write["from_title"] == "前端工程师"
    assert write["to_title"] == "高级前端工程师"
    assert write["confidence"] == 0.85

    first_pid = write["pid"]
    driver.session_obj.writes.clear()
    graph_sync_service.generate_promotion_paths(dry_run=False)
    assert driver.session_obj.writes[0]["pid"] == first_pid
