"""Graph ETL 域：HTTP API 路由。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from app.core.security import get_bearer_user_id
from app.db import db_cursor
from app.domains.graph.services import (
    GraphServiceError,
    clear_graph,
    get_job_titles,
    get_stats,
)
from app.domains.graph.locking import GraphOperationBusy, graph_write_lock
from app.domains.graph import task_repository
from app.domains.graph.task_service import (
    GraphTaskError, cancel_task, confirm_task, downloadable_task_file, enqueue_task, guard_status,
    list_tasks, reject_task, task_changes, task_detail,
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
    """Deprecated direct writer; graph updates must use the durable queue."""
    _, err = _require_admin()
    if err:
        return err
    return jsonify({"ok": False, "message": "直接导入已停用，请使用 POST /api/graph/tasks"}), 410


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


@graph_bp.get("/import-runs")
def import_runs_list():
    """Deprecated Neo4j-local audit endpoint."""
    _, err = _require_admin()
    if err:
        return err
    return jsonify({"ok": False, "message": "旧运行记录接口已停用，请使用 GET /api/graph/tasks"}), 410


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

def _deprecated_update():
    return jsonify({"ok": False, "message": "独立派生更新已停用，请创建图谱更新任务"}), 410


@graph_bp.post("/sync/job-titles")
def sync_job_titles():
    """从 :Job 聚合创建 :JobTitle 节点。"""
    _, err = _require_admin()
    if err:
        return err
    return _deprecated_update()


@graph_bp.post("/generate/promotion-paths")
def generate_promotion_paths():
    """LLM 推断晋升路径。"""
    _, err = _require_admin()
    if err:
        return err
    return _deprecated_update()


@graph_bp.post("/generate/lateral-transfers")
def generate_lateral_transfers():
    """LLM 推断换岗关系。"""
    _, err = _require_admin()
    if err:
        return err
    return _deprecated_update()


@graph_bp.post("/generate/learning-resources")
def generate_learning_resources():
    """LLM 推荐学习资源。"""
    _, err = _require_admin()
    if err:
        return err
    return _deprecated_update()


@graph_bp.post("/generate/competitions")
def generate_competitions():
    """LLM 推荐竞赛。"""
    _, err = _require_admin()
    if err:
        return err
    return _deprecated_update()


@graph_bp.post("/tasks")
def create_graph_task():
    user_id, err = _require_admin()
    if err: return err
    try:
        form = request.form.to_dict() if request.files else (request.get_json(silent=True) or {})
        task = enqueue_task(
            user_id=user_id, task_type=str(form.get("task_type") or ""),
            uploaded_file=request.files.get("file"),
            uploaded_files={key: value for key, value in request.files.items()},
            source_id=form.get("source_id"),
            mode=form.get("mode"), batch_size=int(form.get("batch_size") or 128),
            generate_promotions=_parse_bool(form.get("generate_promotions"), True),
            generate_lateral=_parse_bool(form.get("generate_lateral"), True),
            options=form,
        )
        return jsonify({"ok": True, "data": task}), 202
    except GraphTaskError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status
    except (TypeError, ValueError): return jsonify({"ok": False, "message": "任务参数格式错误"}), 400


@graph_bp.get("/tasks")
def graph_tasks_list():
    _, err = _require_admin()
    if err: return err
    try:
        page = max(1, int(request.args.get("page") or 1)); size = max(1, min(int(request.args.get("page_size") or 20), 100))
        requested_by = int(request.args["requested_by"]) if request.args.get("requested_by") else None
        data = list_tasks(page=page, page_size=size, status=request.args.get("status") or None,
                          task_type=request.args.get("task_type") or None, requested_by=requested_by,
                          created_from=request.args.get("created_from") or None,
                          created_to=request.args.get("created_to") or None)
        return jsonify({"ok": True, "data": data})
    except ValueError: return jsonify({"ok": False, "message": "分页参数格式错误"}), 400


@graph_bp.get("/tasks/<int:task_id>")
def graph_task_detail(task_id: int):
    _, err = _require_admin()
    if err: return err
    try: return jsonify({"ok": True, "data": task_detail(task_id)})
    except GraphTaskError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status


@graph_bp.get("/tasks/<int:task_id>/changes")
def graph_task_changes(task_id: int):
    _, err = _require_admin()
    if err: return err
    try:
        page = max(1, int(request.args.get("page") or 1))
        size = max(1, min(int(request.args.get("page_size") or 20), 100))
        return jsonify({"ok": True, "data": task_changes(task_id, group=request.args.get("group") or None, page=page, page_size=size)})
    except ValueError: return jsonify({"ok": False, "message": "分页参数格式错误"}), 400
    except GraphTaskError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status


@graph_bp.get("/tasks/<int:task_id>/files/<string:role>/download")
def graph_task_file_download(task_id: int, role: str):
    _, err = _require_admin()
    if err: return err
    try:
        item = downloadable_task_file(task_id, role)
        return send_file(
            item["path"],
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=item["original_name"],
            conditional=True,
        )
    except GraphTaskError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status


@graph_bp.post("/tasks/<int:task_id>/confirm")
def graph_task_confirm(task_id: int):
    user_id, err = _require_admin()
    if err: return err
    try: return jsonify({"ok": True, "data": confirm_task(task_id, user_id)})
    except GraphTaskError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status


@graph_bp.post("/tasks/<int:task_id>/reject")
def graph_task_reject(task_id: int):
    user_id, err = _require_admin()
    if err: return err
    try: return jsonify({"ok": True, "data": reject_task(task_id, user_id, str((request.get_json(silent=True) or {}).get("reason") or ""))})
    except GraphTaskError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status


@graph_bp.post("/tasks/<int:task_id>/cancel")
def graph_task_cancel(task_id: int):
    user_id, err = _require_admin()
    if err: return err
    try: return jsonify({"ok": True, "data": cancel_task(task_id, user_id)})
    except GraphTaskError as exc: return jsonify({"ok": False, "message": exc.message}), exc.status


@graph_bp.get("/guard")
def graph_guard():
    _, err = _require_admin()
    if err: return err
    return jsonify({"ok": True, "data": guard_status()})


@graph_bp.post("/clear")
def clear():
    """
    清空整个图谱。

    JSON Body: { "confirmed": true }
    """
    user_id, err = _require_admin()
    if err:
        return err

    try:
        body = request.get_json(silent=True) or {}
        if not body.get("confirmed"):
            return jsonify({"ok": False, "message": "请二次确认（confirmed: true）"}), 400

        guard = guard_status()
        if guard["locked"] or task_repository.has_active_tasks():
            return jsonify({"ok": False, "message": "存在运行中或待确认的图谱任务，不能执行紧急清空"}), 409
        with graph_write_lock():
            result = clear_graph()
            with db_cursor() as (_, cur):
                import json
                from uuid import uuid4
                cur.execute(
                    """INSERT INTO graph_update_tasks
                      (task_uuid,task_type,status,requested_by,handled_by,input_file_name,
                       input_file_size,input_sha256,mode,options_json,change_summary_json,
                       created_at,handled_at,finished_at)
                      VALUES (%s,'emergency_clear','succeeded',%s,%s,'-',0,%s,'snapshot',%s,%s,NOW(),NOW(),NOW())""",
                    (uuid4().hex, user_id, user_id, "0" * 64,
                     json.dumps({"confirmed": True}), json.dumps(result)),
                )
                audit_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO graph_update_task_events (task_id,event_type,stage,message,detail_json) VALUES (%s,'succeeded','emergency','管理员紧急清空图谱',%s)",
                    (audit_id, json.dumps(result)),
                )
                cur.execute("UPDATE graph_write_guard SET graph_revision=graph_revision+1 WHERE id=1")
        return jsonify(
            {
                "ok": True,
                "message": f"已清空图谱（删除 {result['deleted_nodes']} 个节点）",
                "data": result,
            }
        ), 200

    except GraphServiceError as exc:
        return jsonify({"ok": False, "message": exc.message}), exc.status
    except GraphOperationBusy as exc:
        return jsonify({"ok": False, "message": str(exc)}), 409
    except Exception as exc:
        return (
            jsonify({"ok": False, "message": f"清空图谱失败: {exc}"}),
            500,
        )
