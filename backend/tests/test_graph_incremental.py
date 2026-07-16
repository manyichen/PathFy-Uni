from __future__ import annotations

import pandas as pd

from app.domains.graph.incremental import (
    deduplicate_jobs,
    fingerprint_for_row,
    job_key_for_row,
    normalize_source_id,
    plan_incremental_rows,
)
from app.domains.graph import repository
from app.domains.graph import locking
from app.domains.graph import services
from app.domains.graph.constants import COLUMN_ALIASES, REQUIRED_CN_COLUMNS


def _row(**overrides):
    row = {
        "name": "Java 工程师",
        "company": "示例公司",
        "location": "杭州",
        "salary": "10-15K",
        "industry": "软件",
        "company_size": "100-499人",
        "company_type": "民营",
        "job_code": "J001",
        "demand": "负责服务开发",
        "updated_date": "2026-07-12",
        "company_detail": "",
        "source_url": "https://example.test/job/1",
    }
    row.update(overrides)
    return row


def test_incremental_plan_only_selects_changed_rows():
    df = pd.DataFrame([_row(), _row(name="测试工程师", job_code="J002")])
    first = df.iloc[0]
    existing = {
        job_key_for_row(first): fingerprint_for_row(first, extraction_version="model:v1")
    }

    changed, unchanged, fingerprints = plan_incremental_rows(
        df, existing, extraction_version="model:v1"
    )

    assert len(changed) == 1
    assert changed.iloc[0]["name"] == "测试工程师"
    assert unchanged == [job_key_for_row(first)]
    assert len(fingerprints) == 2


def test_fingerprint_changes_with_content_or_extractor_version():
    row = pd.Series(_row())
    base = fingerprint_for_row(row, extraction_version="model:v1")
    assert base != fingerprint_for_row(
        pd.Series(_row(demand="新的职责")), extraction_version="model:v1"
    )
    assert base != fingerprint_for_row(row, extraction_version="model:v2")


def test_deduplicate_uses_existing_business_key_and_last_row():
    df = pd.DataFrame([_row(demand="旧"), _row(demand="新")])
    deduped, count = deduplicate_jobs(df)
    assert count == 1
    assert len(deduped) == 1
    assert deduped.iloc[0]["demand"] == "新"


def test_source_id_is_path_safe_and_stable():
    assert normalize_source_id("/data/2026 七月岗位.xls") == "2026-七月岗位.xls"


def test_direct_snapshot_prune_writer_has_been_removed():
    assert not hasattr(repository, "prune_missing_jobs")


def test_graph_write_lock_is_released(monkeypatch):
    class Cursor:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params=None):
            self.calls.append((query, params))

        def fetchone(self):
            return {"acquired": 1}

    class Connection:
        def __init__(self):
            self.value = Cursor()
            self.closed = False

        def cursor(self):
            return self.value

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(locking, "get_connection", lambda: connection)

    with locking.graph_write_lock():
        pass

    assert any("GET_LOCK" in query for query, _ in connection.value.calls)
    assert "RELEASE_LOCK" in connection.value.calls[-1][0]
    assert connection.closed is True


def _excel_frame() -> pd.DataFrame:
    values = {
        "岗位名称": "Java 工程师",
        "地址": "杭州",
        "薪资范围": "10-15K",
        "公司名称": "示例公司",
        "所属行业": "软件",
        "公司规模": "100-499人",
        "公司类型": "民营",
        "岗位编码": "J001",
        "岗位详情": "负责服务开发",
        "更新日期": "2026-07-12",
        "公司详情": "",
        "岗位来源地址": "https://example.test/job/1",
    }
    assert set(REQUIRED_CN_COLUMNS) == set(values)
    return pd.DataFrame([values])


def test_direct_import_service_is_disabled():
    try:
        services.import_jobs_from_excel(excel_path="jobs.xls", mode="merge")
    except services.GraphServiceError as exc:
        assert exc.status == 410
    else:
        raise AssertionError("direct graph writes must be disabled")
