"""Graph ETL 域：HTTP API 路由。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.core.security import get_bearer_user_id
from app.db import db_cursor
from app.domains.graph.services import (
    GraphServiceError,
    clear_graph,
    generate_promotion_edges,
    get_job_titles,
    get_stats,
    import_jobs_from_excel,
)

graph_bp = Blueprint("graph", __name__, url_prefix="/api/graph")


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
        # 判断是文件上传还是服务器路径
        uploaded_file = request.files.get("file")
        body = request.get_json(silent=True) or {}

        file_path = body.get("file_path") if not uploaded_file else None
        batch_size = int(body.get("batch_size", 128))
        clear_all = bool(body.get("clear_all", False))

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
    """
    生成晋升边（VERTICAL_UP）。

    JSON Body:
        {
            "dry_run": false,
            "min_confidence": 0.55,
            "min_company_jobs": 2,
            "clear_existing": false
        }
    """
    _, err = _require_admin()
    if err:
        return err

    try:
        body = request.get_json(silent=True) or {}

        dry_run = bool(body.get("dry_run", False))
        min_confidence = float(body.get("min_confidence", 0.55))
        min_company_jobs = int(body.get("min_company_jobs", 2))
        clear_existing = bool(body.get("clear_existing", False))

        result = generate_promotion_edges(
            min_confidence=min_confidence,
            min_company_jobs=min_company_jobs,
            clear_existing=clear_existing,
            dry_run=dry_run,
        )
        return jsonify({"ok": True, "data": result}), 200

    except GraphServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except Exception as exc:
        return (
            jsonify({"ok": False, "message": f"生成晋升边失败: {exc}"}),
            500,
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
