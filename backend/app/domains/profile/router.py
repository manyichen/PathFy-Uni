from decimal import Decimal
from uuid import uuid4

from flask import Blueprint, request, jsonify
import os
import json
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET
from werkzeug.utils import secure_filename

from app.core.security import assert_self_user_id, get_bearer_user_id
from app.core.config import Config
from app.db import db_cursor
from app.infrastructure.privacy import redact_text, storage_safe_text
from app.infrastructure.ocr import extract_pdf_text, ocr_image, pdf_to_images
from app.utils import create_radar_chart, score_resume
from app.domains.profile.analysis import generate_detailed_analysis

portrait_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

_IMAGE_MATERIAL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_TEXT_MATERIAL_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json"}
_WORD_MATERIAL_EXTENSIONS = {".docx"}
_SPREADSHEET_MATERIAL_EXTENSIONS = {".xls", ".xlsx"}
_PDF_MATERIAL_EXTENSIONS = {".pdf"}
_ALLOWED_RESUME_EXTENSIONS = (
    _PDF_MATERIAL_EXTENSIONS
    | _IMAGE_MATERIAL_EXTENSIONS
    | _TEXT_MATERIAL_EXTENSIONS
    | _WORD_MATERIAL_EXTENSIONS
    | _SPREADSHEET_MATERIAL_EXTENSIONS
)
_MAX_MATERIALS = 12
_MAX_DIRECT_TEXT_CHARS = 20000
_MAX_EXTRACTED_CHARS_PER_MATERIAL = 30000
_MIN_PDF_TEXT_CHARS_BEFORE_OCR = 80


def _jsonable_row(row: dict | None) -> dict | None:
    if not row:
        return row
    out: dict = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    if out.get("resume_text"):
        out["resume_text"] = redact_text(
            out["resume_text"],
            max_chars=int(getattr(Config, "LOCAL_MAX_STORED_TEXT_CHARS", 4000)),
        )
    return out

def _resume_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    return ext.lower()


def _resume_upload_dir() -> str:
    """为单个材料创建独立 OCR 临时工作目录。"""
    base_dirs = []
    configured = str(getattr(Config, "RESUME_UPLOAD_DIR", "") or "").strip()
    if configured:
        base_dirs.append(os.path.abspath(configured))
    temp_root = tempfile.gettempdir()
    if temp_root not in base_dirs:
        base_dirs.append(temp_root)

    last_error: OSError | None = None
    for base_dir in base_dirs:
        try:
            os.makedirs(base_dir, mode=0o700, exist_ok=True)
            return tempfile.mkdtemp(prefix="pathfy_profile_", dir=base_dir)
        except OSError as exc:
            last_error = exc

    raise OSError(f"无法创建可写的材料上传临时目录: {last_error}")


def _discard_path(path: str | None) -> None:
    if not path or not os.path.isfile(path):
        return
    try:
        os.remove(path)
    except OSError:
        pass


def _discard_empty_dir(path: str | None) -> None:
    if not path or not os.path.isdir(path):
        return
    try:
        os.rmdir(path)
    except OSError:
        pass


def _discard_pdf_preview_artifacts(pdf_path: str | None) -> None:
    """删除 PDF 转 PNG 时产生的 pdf_images 子目录及其中文件。"""
    if not pdf_path:
        return
    preview_dir = os.path.join(os.path.dirname(pdf_path), "pdf_images")
    if not os.path.isdir(preview_dir):
        return
    try:
        for name in os.listdir(preview_dir):
            fp = os.path.join(preview_dir, name)
            if os.path.isfile(fp):
                os.remove(fp)
        os.rmdir(preview_dir)
    except OSError:
        pass


def _cleanup_resume_upload_artifacts(
    file_path: str | None, ocr_path: str | None, *, from_pdf: bool
) -> None:
    """OCR 结束后删除磁盘上的画像材料原文件与 PDF 预览图。"""
    if not getattr(Config, "DELETE_UPLOADED_RESUME_AFTER_OCR", True):
        return
    if ocr_path and ocr_path != file_path:
        _discard_path(ocr_path)
    if from_pdf:
        _discard_pdf_preview_artifacts(file_path)
    _discard_path(file_path)


def _save_resume_upload(file) -> tuple[str | None, str | None]:
    """校验并保存画像材料文件，返回 (磁盘路径, 错误信息)。"""
    if not file or not file.filename:
        return None, "请上传画像材料"

    ext = _resume_extension(file.filename)
    if ext not in _ALLOWED_RESUME_EXTENSIONS:
        return None, "仅支持 PDF、图片、TXT/MD/CSV/JSON、DOCX、XLS/XLSX 格式"

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size <= 0:
        return None, "文件为空"
    max_bytes = Config.MAX_UPLOAD_MB * 1024 * 1024
    if size > max_bytes:
        return None, f"文件大小不能超过 {Config.MAX_UPLOAD_MB}MB"

    safe_name = secure_filename(file.filename)
    if not safe_name or "." not in safe_name:
        safe_name = f"material{ext or ''}"
    stored_name = f"{uuid4().hex}_{safe_name}"
    upload_dir: str | None = None
    try:
        upload_dir = _resume_upload_dir()
        file_path = os.path.join(upload_dir, stored_name)
        file.save(file_path)
        return file_path, None
    except OSError as exc:
        if upload_dir:
            _discard_empty_dir(upload_dir)
        return None, f"保存材料失败: {exc}"


def _decode_text_bytes(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _trim_material_text(text: str, *, limit: int = _MAX_EXTRACTED_CHARS_PER_MATERIAL) -> str:
    clean = str(text or "").replace("\x00", "").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n...[材料内容过长，已截断]"


def _extract_text_file(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return _decode_text_bytes(f.read())


def _extract_docx_text(file_path: str) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(file_path) as zf:
        names = [
            name
            for name in zf.namelist()
            if name == "word/document.xml"
            or name.startswith("word/header")
            or name.startswith("word/footer")
        ]
        for name in names:
            xml_bytes = zf.read(name)
            root = ET.fromstring(xml_bytes)
            texts = []
            for elem in root.iter():
                if elem.tag.endswith("}t") and elem.text:
                    texts.append(elem.text)
                elif elem.tag.endswith("}tab"):
                    texts.append("\t")
                elif elem.tag.endswith("}br"):
                    texts.append("\n")
            if texts:
                parts.append("".join(texts))
    return "\n".join(parts)


def _extract_spreadsheet_text(file_path: str) -> str:
    import pandas as pd

    chunks: list[str] = []
    workbook = pd.ExcelFile(file_path)
    for sheet_name in workbook.sheet_names[:3]:
        frame = pd.read_excel(workbook, sheet_name=sheet_name, dtype=str, nrows=80)
        frame = frame.fillna("")
        rows = []
        for _, row in frame.iterrows():
            values = [str(x).strip() for x in row.tolist() if str(x).strip()]
            if values:
                rows.append(" | ".join(values))
        if rows:
            chunks.append(f"[表格：{sheet_name}]\n" + "\n".join(rows))
    return "\n\n".join(chunks)


def _extract_pdf_material_text(file_path: str) -> tuple[str, list[str]]:
    artifacts: list[str] = []
    max_pages = max(1, int(getattr(Config, "OCR_MAX_PDF_PAGES", 12)))

    text = extract_pdf_text(file_path, max_pages=max_pages).strip()
    if len(text) >= _MIN_PDF_TEXT_CHARS_BEFORE_OCR:
        return text, artifacts

    page_images = pdf_to_images(file_path, max_pages=max_pages)
    artifacts.extend(page_images)
    chunks = [text] if text else []
    for idx, img_path in enumerate(page_images, start=1):
        page_text = ocr_image(img_path).strip()
        if page_text:
            chunks.append(f"[PDF OCR 第 {idx} 页]\n{page_text}")
    return "\n\n".join(chunks).strip(), artifacts


def _extract_material_text(file_path: str, filename: str) -> tuple[str, str, list[str]]:
    ext = _resume_extension(filename)
    artifacts: list[str] = []
    if ext in _TEXT_MATERIAL_EXTENSIONS:
        return _extract_text_file(file_path), "文本文件", artifacts
    if ext in _WORD_MATERIAL_EXTENSIONS:
        return _extract_docx_text(file_path), "Word 文档", artifacts
    if ext in _SPREADSHEET_MATERIAL_EXTENSIONS:
        return _extract_spreadsheet_text(file_path), "表格材料", artifacts
    if ext in _IMAGE_MATERIAL_EXTENSIONS:
        return ocr_image(file_path), "图片 OCR", artifacts
    if ext in _PDF_MATERIAL_EXTENSIONS:
        text, artifacts = _extract_pdf_material_text(file_path)
        return text, "PDF 文档", artifacts
    raise ValueError(f"不支持的文件类型：{ext}")


def _material_form_files() -> list:
    files = []
    legacy = request.files.get("resume")
    if legacy and legacy.filename:
        files.append(legacy)
    for item in request.files.getlist("materials"):
        if item and item.filename and item is not legacy:
            files.append(item)
    return files[:_MAX_MATERIALS]


def _direct_profile_text() -> str:
    fields = [
        "profile_text",
        "direct_text",
        "self_intro",
        "self_intro_text",
        "extra_text",
    ]
    chunks = []
    for field in fields:
        value = str(request.form.get(field) or "").strip()
        if value:
            chunks.append(value)
    text = "\n\n".join(chunks).strip()
    if len(text) > _MAX_DIRECT_TEXT_CHARS:
        text = text[:_MAX_DIRECT_TEXT_CHARS] + "\n...[直接输入内容过长，已截断]"
    return text


def _collect_profile_materials() -> tuple[str, list[dict], list[str], list[str]]:
    """返回 (合并文本, 材料元信息, 保存文件路径, 临时衍生文件路径)。"""
    files = _material_form_files()
    direct_text = _direct_profile_text()
    saved_paths: list[str] = []
    artifact_paths: list[str] = []
    metas: list[dict] = []
    sections: list[str] = []

    if direct_text:
        sections.append(f"[直接输入 | 自我介绍/补充材料]\n{direct_text}")
        metas.append(
            {
                "name": "直接输入",
                "kind": "direct_text",
                "status": "ok",
                "chars": len(direct_text),
            }
        )

    for file in files:
        file_path, upload_err = _save_resume_upload(file)
        if upload_err or not file_path:
            metas.append(
                {
                    "name": file.filename or "未命名材料",
                    "kind": "file",
                    "status": "error",
                    "error": upload_err or "上传失败",
                    "chars": 0,
                }
            )
            continue
        saved_paths.append(file_path)
        filename = file.filename or os.path.basename(file_path)
        ext = _resume_extension(filename)
        started_at = time.monotonic()
        try:
            raw_text, kind, artifacts = _extract_material_text(file_path, filename)
            artifact_paths.extend(artifacts)
            material_text = _trim_material_text(raw_text)
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            if material_text:
                sections.append(f"[{filename} | {kind}]\n{material_text}")
                metas.append(
                    {
                        "name": filename,
                        "kind": kind,
                        "extension": ext,
                        "status": "ok",
                        "chars": len(material_text),
                        "elapsed_ms": elapsed_ms,
                    }
                )
            else:
                metas.append(
                    {
                        "name": filename,
                        "kind": kind,
                        "extension": ext,
                        "status": "empty",
                        "error": "未识别到有效文本",
                        "chars": 0,
                        "elapsed_ms": elapsed_ms,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            metas.append(
                {
                    "name": filename,
                    "kind": "file",
                    "extension": ext,
                    "status": "error",
                    "error": str(exc),
                    "chars": 0,
                    "elapsed_ms": elapsed_ms,
                }
            )

    combined_text = "\n\n---\n\n".join(sections).strip()
    return combined_text, metas, saved_paths, artifact_paths


def _cleanup_material_upload_artifacts(file_paths: list[str], artifact_paths: list[str]) -> None:
    if not getattr(Config, "DELETE_UPLOADED_RESUME_AFTER_OCR", True):
        return
    upload_dirs = {os.path.dirname(path) for path in file_paths if path}
    for path in artifact_paths:
        _discard_path(path)
    seen_dirs = {os.path.dirname(path) for path in artifact_paths if path}
    for path in file_paths:
        _discard_pdf_preview_artifacts(path)
        _discard_path(path)
    for directory in seen_dirs:
        if os.path.basename(directory) != "pdf_images":
            continue
        try:
            if os.path.isdir(directory) and not os.listdir(directory):
                os.rmdir(directory)
        except OSError:
            pass
    for directory in upload_dirs:
        if os.path.basename(directory).startswith("pathfy_profile_"):
            _discard_empty_dir(directory)


@portrait_bp.route("/resumes", methods=["GET"])
def list_my_resumes():
    """当前登录用户的能力画像列表，供人岗匹配选用。"""
    uid = get_bearer_user_id()
    if uid is None:
        return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401

    try:
        with db_cursor() as (_, cur):
            cur.execute(
                """
                SELECT id, name, major, create_time,
                  cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
                  cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
                  completeness, competitiveness
                FROM student_resume
                WHERE user_id = %s
                ORDER BY id DESC
                """,
                (uid,),
            )
            rows = cur.fetchall()

        out = []
        for r in rows:
            dims = [
                r["cap_req_theory"],
                r["cap_req_cross"],
                r["cap_req_practice"],
                r["cap_req_digital"],
                r["cap_req_innovation"],
                r["cap_req_teamwork"],
                r["cap_req_social"],
                r["cap_req_growth"],
            ]
            nums = [float(x) for x in dims if x is not None]
            score_avg = round(sum(nums) / len(nums), 2) if nums else 0.0
            scores = {
                "cap_req_theory": int(r["cap_req_theory"] or 0),
                "cap_req_cross": int(r["cap_req_cross"] or 0),
                "cap_req_practice": int(r["cap_req_practice"] or 0),
                "cap_req_digital": int(r["cap_req_digital"] or 0),
                "cap_req_innovation": int(r["cap_req_innovation"] or 0),
                "cap_req_teamwork": int(r["cap_req_teamwork"] or 0),
                "cap_req_social": int(r["cap_req_social"] or 0),
                "cap_req_growth": int(r["cap_req_growth"] or 0),
            }
            out.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "major": r["major"],
                    "create_time": str(r["create_time"]) if r.get("create_time") else None,
                    "completeness": r.get("completeness"),
                    "competitiveness": r.get("competitiveness"),
                    "score_avg": score_avg,
                    "scores": scores,
                }
            )

        return jsonify({"code": 200, "msg": "success", "data": out})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500


@portrait_bp.route("/upload", methods=["POST"])
def upload_resume():
    file_paths: list[str] = []
    artifact_paths: list[str] = []
    try:
        uid = get_bearer_user_id()
        if uid is None:
            return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401

        name = request.form.get("name")
        major = request.form.get("major")

        if not all([name, major]):
            return jsonify({"code": 400, "msg": "请填写姓名和专业"}), 400

        resume_text, material_metas, file_paths, artifact_paths = _collect_profile_materials()
        if not resume_text.strip():
            return (
                jsonify(
                    {
                        "code": 400,
                        "msg": "未识别到可用于能力画像的材料内容，请上传文件或填写补充文本",
                        "data": {"materials": material_metas},
                    }
                ),
                400,
            )

        scores, confidences = score_resume(resume_text)
        radar_html = create_radar_chart(scores)

        detailed_analysis = generate_detailed_analysis(scores, resume_text)
        detailed_analysis["material_summary"] = material_metas
        stored_resume_text = storage_safe_text(
            resume_text,
            kind="resume",
            max_chars=int(getattr(Config, "LLM_MAX_RESUME_CHARS", 20000)),
        )

        with db_cursor() as (_, cur):
            cur.execute("SHOW COLUMNS FROM student_resume LIKE 'detailed_analysis'")
            has_detailed_analysis = cur.fetchone() is not None

            total = sum(scores.values())
            completeness = total // 8
            competitiveness = total // 8

            row_vals = (
                uid,
                name,
                major,
                stored_resume_text,
                scores["cap_req_theory"],
                scores["cap_req_cross"],
                scores["cap_req_practice"],
                scores["cap_req_digital"],
                scores["cap_req_innovation"],
                scores["cap_req_teamwork"],
                scores["cap_req_social"],
                scores["cap_req_growth"],
                confidences["cap_conf_theory"],
                confidences["cap_conf_cross"],
                confidences["cap_conf_practice"],
                confidences["cap_conf_digital"],
                confidences["cap_conf_innovation"],
                confidences["cap_conf_teamwork"],
                confidences["cap_conf_social"],
                confidences["cap_conf_growth"],
                completeness,
                competitiveness,
                radar_html,
            )

            if has_detailed_analysis:
                sql = """
                INSERT INTO student_resume
                (user_id, name, major, resume_text,
                cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
                cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
                cap_conf_theory, cap_conf_cross, cap_conf_practice, cap_conf_digital,
                cap_conf_innovation, cap_conf_teamwork, cap_conf_social, cap_conf_growth,
                completeness, competitiveness, radar_html, detailed_analysis)
                VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s)
                """
                cur.execute(
                    sql,
                    row_vals + (json.dumps(detailed_analysis, ensure_ascii=False, indent=2),),
                )
            else:
                sql = """
                INSERT INTO student_resume
                (user_id, name, major, resume_text,
                cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
                cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
                cap_conf_theory, cap_conf_cross, cap_conf_practice, cap_conf_digital,
                cap_conf_innovation, cap_conf_teamwork, cap_conf_social, cap_conf_growth,
                completeness, competitiveness, radar_html)
                VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s)
                """
                cur.execute(sql, row_vals)

            resume_id = cur.lastrowid

        return jsonify(
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "resume_id": resume_id,
                    "scores": scores,
                    "confidences": confidences,
                    "completeness": completeness,
                    "competitiveness": competitiveness,
                    "detailed_analysis": detailed_analysis,
                    "materials": material_metas,
                },
            }
        )
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500
    finally:
        _cleanup_material_upload_artifacts(file_paths, artifact_paths)


@portrait_bp.route("/result/<int:resume_id>", methods=["GET"])
def get_result(resume_id):
    try:
        uid = get_bearer_user_id()
        if uid is None:
            return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401

        with db_cursor() as (_, cur):
            cur.execute(
                "SELECT * FROM student_resume WHERE id = %s AND user_id = %s",
                (resume_id, uid),
            )
            result = cur.fetchone()
        if not result:
            return jsonify({"code": 404, "msg": "结果不存在或无权查看"}), 404

        if result.get("detailed_analysis") and isinstance(result["detailed_analysis"], str):
            result["detailed_analysis"] = json.loads(result["detailed_analysis"])

        return jsonify({"code": 200, "data": _jsonable_row(result)})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"错误: {str(e)}"}), 500

@portrait_bp.route('/history/<int:user_id>', methods=['GET'])
def get_user_history(user_id):
    """获取用户的历史能力画像记录"""
    try:
        uid = get_bearer_user_id()
        if uid is None:
            return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401
        if not assert_self_user_id(user_id, uid):
            return jsonify({"code": 403, "msg": "无权访问该用户数据"}), 403

        with db_cursor() as (_, cur):
            cur.execute("""
                SELECT id, name, major, create_time,
                cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
                cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
                completeness, competitiveness
                FROM student_resume
                WHERE user_id = %s
                ORDER BY create_time DESC
            """, (user_id,))
            results = cur.fetchall()

        # 解析每个记录的能力数据
        history = []
        for r in results:
            history.append({
                "id": r["id"],
                "name": r["name"],
                "major": r["major"],
                "create_time": r["create_time"].isoformat() if r.get("create_time") else None,
                "scores": {
                    "cap_req_theory": r["cap_req_theory"],
                    "cap_req_cross": r["cap_req_cross"],
                    "cap_req_practice": r["cap_req_practice"],
                    "cap_req_digital": r["cap_req_digital"],
                    "cap_req_innovation": r["cap_req_innovation"],
                    "cap_req_teamwork": r["cap_req_teamwork"],
                    "cap_req_social": r["cap_req_social"],
                    "cap_req_growth": r["cap_req_growth"]
                },
                "completeness": r["completeness"],
                "competitiveness": r["competitiveness"]
            })

        return jsonify({"code": 200, "data": history})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"错误: {str(e)}"}), 500

@portrait_bp.route('/trend/<int:user_id>', methods=['GET'])
def get_ability_trend(user_id):
    """获取用户能力变化趋势"""
    try:
        uid = get_bearer_user_id()
        if uid is None:
            return jsonify({"code": 401, "msg": "需要登录（Authorization: Bearer）"}), 401
        if not assert_self_user_id(user_id, uid):
            return jsonify({"code": 403, "msg": "无权访问该用户数据"}), 403

        with db_cursor() as (_, cur):
            cur.execute("""
                SELECT id, create_time,
                cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
                cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
                completeness, competitiveness
                FROM student_resume
                WHERE user_id = %s
                ORDER BY create_time ASC
            """, (user_id,))
            results = cur.fetchall()

        if not results:
            return jsonify({"code": 404, "msg": "暂无历史数据"}), 404

        trend = []
        for r in results:
            trend.append({
                "id": r["id"],
                "date": r["create_time"].isoformat() if r.get("create_time") else None,
                "scores": {
                    "cap_req_theory": r["cap_req_theory"],
                    "cap_req_cross": r["cap_req_cross"],
                    "cap_req_practice": r["cap_req_practice"],
                    "cap_req_digital": r["cap_req_digital"],
                    "cap_req_innovation": r["cap_req_innovation"],
                    "cap_req_teamwork": r["cap_req_teamwork"],
                    "cap_req_social": r["cap_req_social"],
                    "cap_req_growth": r["cap_req_growth"]
                },
                "completeness": r["completeness"],
                "competitiveness": r["competitiveness"]
            })

        # 计算变化趋势
        if len(trend) >= 2:
            latest = trend[-1]["scores"]
            previous = trend[-2]["scores"]
            changes = {}
            for dim in latest:
                diff = latest[dim] - previous[dim]
                changes[dim] = {
                    "change": round(diff, 1),
                    "direction": "上升" if diff > 0 else ("下降" if diff < 0 else "持平"),
                    "percentage": round((diff / previous[dim]) * 100, 1) if previous[dim] != 0 else 0
                }
            trend[-1]["changes"] = changes

        return jsonify({"code": 200, "data": trend})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"错误: {str(e)}"}), 500
