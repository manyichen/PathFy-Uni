"""Graph ETL 域：HTTP API 路由。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.core.security import get_bearer_user_id
from app.db import db_cursor
from app.domains.graph.services import (
    GraphServiceError,
    clear_graph,
    get_job_titles,
    get_stats,
    import_jobs_from_excel,
)

graph_bp = Blueprint("graph", __name__, url_prefix="/api/graph")
TRUE_VALUES = {"1", "true", "yes", "on"}


# ============================================================
# 认证辅助
# ============================================================

def _require_admin():
    """校验 JWT 并从数据库确认管理员身份。"""
    uid = get_bearer_user_id()
    if uid is None:
        return None, (jsonify({"ok": False, "message": "请先登录"}), 401)

    with db_cursor() as (_, cur):
        cur.execute("SELECT is_admin FROM users WHERE id = %s", (uid,))
        row = cur.fetchone()

    if not row or not row["is_admin"]:
        return None, (
            jsonify({"ok": False, "message": "无权限，仅管理员可操作"}),
            403,
        )
    return uid, None


def _parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in TRUE_VALUES
    return bool(value)


# ============================================================
# 路由
# ============================================================

@graph_bp.post("/import-jobs")
def import_jobs():
    """
    从 Excel 导入岗位到 Neo4j。

    JSON Body（file_path 模式）:
        { "file_path": "/path/to/data.xls", "batch_size": 128, "clear_all": false }

    multipart/form-data（上传模式）:
        file: Excel 文件
        batch_size: 128（可选）
        clear_all: false（可选）
    """
    _, err = _require_admin()
    if err:
        return err

    try:
        uploaded_file = request.files.get("file")
        if uploaded_file:
            params = request.form
            file_path = None
        else:
            params = request.get_json(silent=True) or {}
            file_path = params.get("file_path")

        batch_size = int(params.get("batch_size") or 128)
        clear_all = _parse_bool(params.get("clear_all"), False)

        result = import_jobs_from_excel(
            excel_path=file_path,
            uploaded_file=uploaded_file,
            batch_size=batch_size,
            clear_all=clear_all,
        )
        return jsonify({"ok": True, "data": result}), 200

    except GraphServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:
        return (
            jsonify({"ok": False, "message": f"导入岗位失败: {exc}"}),
            500,
        )


@graph_bp.post("/generate-promotions")
def generate_promotions():
    """旧 Job 节点晋升边生成接口已废弃，保留 410 响应防止误写库。"""
    _, err = _require_admin()
    if err:
        return err

    return (
        jsonify(
            {
                "ok": False,
                "message": (
                    "generate-promotions 已废弃，不再写入 Job 层晋升边；"
                    "请先调用 /api/graph/sync/job-titles，再调用 "
                    "/api/graph/generate/promotion-paths 生成 JobTitle 层晋升路径。"
                ),
            }
        ),
        410,
    )


@graph_bp.get("/stats")
def graph_stats():
    """获取图谱统计信息（节点数、关系数）。"""
    _, err = _require_admin()
    if err:
        return err

    try:
        stats = get_stats()
        return jsonify({"ok": True, "data": stats}), 200
    except GraphServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:
        return (
            jsonify({"ok": False, "message": f"获取图谱统计失败: {exc}"}),
            500,
        )


@graph_bp.get("/job-titles")
def job_titles_list():
    """获取 MySQL job_titles 表中的岗位名称统计。"""
    _, err = _require_admin()
    if err:
        return err

    try:
        titles = get_job_titles()
        return jsonify({"ok": True, "data": {"total": len(titles), "titles": titles}}), 200
    except Exception as exc:
        return (
            jsonify({"ok": False, "message": f"获取岗位名称列表失败: {exc}"}),
            500,
        )


@graph_bp.post("/qc-report")
def qc_report():
    """
    从 job_eval_results JSONL 文件生成质检报告。

    JSON Body:
        { "input_file": "path/to/job_eval_results_xxx.jsonl", "threshold": 0.60 }
    """
    _, err = _require_admin()
    if err:
        return err

    try:
        from app.domains.graph.services import generate_qc_report

        body = request.get_json(silent=True) or {}
        input_file = body.get("input_file") or ""
        threshold = float(body.get("threshold", 0.60))

        result = generate_qc_report(input_file=input_file, threshold=threshold)
        return jsonify({"ok": True, "data": result}), 200
    except GraphServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:
        return (
            jsonify({"ok": False, "message": f"生成质检报告失败: {exc}"}),
            500,
        )


# ============================================================
# 图谱智能生成（LLM 自动推断）
# ============================================================

def _run_sync(handler, dry_run: bool):
    """统一执行同步/生成，返回 Flask 响应。"""
    try:
        result = handler(dry_run=dry_run)
        return jsonify({"ok": True, "data": result}), 200
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


@graph_bp.post("/sync/job-titles")
def sync_job_titles():
    """从 :Job 聚合创建 :JobTitle 节点。"""
    _, err = _require_admin()
    if err:
        return err
    from app.domains.graph.sync_service import sync_job_titles as _sync

    body = request.get_json(silent=True) or {}
    return _run_sync(_sync, bool(body.get("dry_run", False)))


@graph_bp.post("/generate/promotion-paths")
def generate_promotion_paths():
    """LLM 推断晋升路径。"""
    _, err = _require_admin()
    if err:
        return err
    from app.domains.graph.sync_service import generate_promotion_paths as _gen

    body = request.get_json(silent=True) or {}
    return _run_sync(_gen, bool(body.get("dry_run", False)))


@graph_bp.post("/generate/lateral-transfers")
def generate_lateral_transfers():
    """LLM 推断换岗关系。"""
    _, err = _require_admin()
    if err:
        return err
    from app.domains.graph.sync_service import generate_lateral_transfers as _gen

    body = request.get_json(silent=True) or {}
    return _run_sync(_gen, bool(body.get("dry_run", False)))


@graph_bp.post("/generate/learning-resources")
def generate_learning_resources():
    """LLM 推荐学习资源。"""
    _, err = _require_admin()
    if err:
        return err
    from app.domains.graph.sync_service import generate_learning_resources as _gen

    body = request.get_json(silent=True) or {}
    return _run_sync(_gen, bool(body.get("dry_run", False)))


@graph_bp.post("/generate/competitions")
def generate_competitions():
    """LLM 推荐竞赛。"""
    _, err = _require_admin()
    if err:
        return err
    from app.domains.graph.sync_service import generate_competitions as _gen

    body = request.get_json(silent=True) or {}
    return _run_sync(_gen, bool(body.get("dry_run", False)))


@graph_bp.post("/clear")
def clear():
    """
    清空整个图谱。

    JSON Body: { "confirmed": true }
    """
    _, err = _require_admin()
    if err:
        return err

    try:
        body = request.get_json(silent=True) or {}
        if not body.get("confirmed"):
            return jsonify({"ok": False, "message": "请二次确认（confirmed: true）"}), 400

        result = clear_graph()
        return jsonify(
            {
                "ok": True,
                "message": f"已清空图谱（删除 {result['deleted_nodes']} 个节点）",
                "data": result,
            }
        ), 200

    except GraphServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:
        return (
            jsonify({"ok": False, "message": f"清空图谱失败: {exc}"}),
            500,
        )
