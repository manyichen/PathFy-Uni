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


# ===================== 行业能力要求数据 =====================
INDUSTRY_REQUIREMENTS = {
    "互联网/IT": {
        "权重": {"cap_req_theory": 0.15, "cap_req_cross": 0.10, "cap_req_practice": 0.25, "cap_req_digital": 0.20, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.05, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_practice", "cap_req_digital", "cap_req_theory"],
        "描述": "互联网/IT行业注重技术实践能力和数字素养，需要具备扎实的专业基础和持续学习能力"
    },
    "金融/银行": {
        "权重": {"cap_req_theory": 0.25, "cap_req_cross": 0.10, "cap_req_practice": 0.15, "cap_req_digital": 0.15, "cap_req_innovation": 0.05, "cap_req_teamwork": 0.10, "cap_req_social": 0.15, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_social", "cap_req_digital"],
        "描述": "金融行业注重专业理论知识和社交网络，需要具备扎实的金融理论基础和良好的职业素养"
    },
    "教育/培训": {
        "权重": {"cap_req_theory": 0.25, "cap_req_cross": 0.15, "cap_req_practice": 0.15, "cap_req_digital": 0.10, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.10, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_teamwork", "cap_req_social"],
        "描述": "教育培训行业注重专业理论知识和团队协作能力，需要具备良好的表达能力和持续学习精神"
    },
    "制造/工程": {
        "权重": {"cap_req_theory": 0.25, "cap_req_cross": 0.10, "cap_req_practice": 0.25, "cap_req_digital": 0.10, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.05, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_practice", "cap_req_innovation"],
        "描述": "制造工程行业注重专业理论和实践技能，需要具备扎实的工程基础和创新思维"
    },
    "医疗/健康": {
        "权重": {"cap_req_theory": 0.30, "cap_req_cross": 0.10, "cap_req_practice": 0.20, "cap_req_digital": 0.10, "cap_req_innovation": 0.05, "cap_req_teamwork": 0.10, "cap_req_social": 0.10, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_practice", "cap_req_teamwork"],
        "描述": "医疗健康行业注重专业理论知识和实践技能，需要具备扎实的医学基础和高度的责任心"
    },
    "销售/市场": {
        "权重": {"cap_req_theory": 0.10, "cap_req_cross": 0.15, "cap_req_practice": 0.10, "cap_req_digital": 0.15, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.15, "cap_req_social": 0.20, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_social", "cap_req_teamwork", "cap_req_digital"],
        "描述": "销售市场行业注重社交网络和团队协作能力，需要具备良好的沟通能力和市场洞察力"
    },
    "政府/事业单位": {
        "权重": {"cap_req_theory": 0.20, "cap_req_cross": 0.15, "cap_req_practice": 0.15, "cap_req_digital": 0.10, "cap_req_innovation": 0.05, "cap_req_teamwork": 0.15, "cap_req_social": 0.15, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_theory", "cap_req_teamwork", "cap_req_social"],
        "描述": "政府事业单位注重综合素质和服务意识，需要具备扎实的理论基础和良好的职业素养"
    },
    "咨询/专业服务": {
        "权重": {"cap_req_theory": 0.15, "cap_req_cross": 0.20, "cap_req_practice": 0.15, "cap_req_digital": 0.10, "cap_req_innovation": 0.10, "cap_req_teamwork": 0.10, "cap_req_social": 0.15, "cap_req_growth": 0.05},
        "核心能力": ["cap_req_cross", "cap_req_social", "cap_req_theory"],
        "描述": "咨询专业服务行业注重跨学科能力和社交网络，需要具备广博的知识面和良好的分析能力"
    }
}

# ===================== 能力维度中文名称映射 =====================
DIMENSION_NAMES = {
    "cap_req_theory": "专业理论知识",
    "cap_req_cross": "交叉学科广度",
    "cap_req_practice": "专业实践技能",
    "cap_req_digital": "数字素养技能",
    "cap_req_innovation": "创新创业能力",
    "cap_req_teamwork": "团队协作能力",
    "cap_req_social": "社会实践网络",
    "cap_req_growth": "学习与发展潜力"
}

# ===================== 能力提升建议库 =====================
SKILL_IMPROVEMENT_SUGGESTIONS = {
    "cap_req_theory": {
        "短期": [
            "参加专业相关的在线课程（Coursera、MOOC等平台）",
            "阅读2-3本专业核心教材和参考书目",
            "整理并复习专业课程笔记，构建知识图谱",
            "参加专业讲座和学术报告，了解学科前沿动态"
        ],
        "长期": [
            "考取相关专业资格证书（如CPA、PMP、司考等）",
            "参与科研项目或学术论文写作",
            "建立个人专业博客或技术文档库",
            "定期阅读行业白皮书和研究报告"
        ]
    },
    "cap_req_cross": {
        "短期": [
            "选修1-2门跨学科选修课",
            "参加跨学科讲座或工作坊",
            "阅读不同领域的科普书籍",
            "加入跨学科学习小组"
        ],
        "长期": [
            "辅修或双学位学习",
            "参与跨学科项目实践",
            "建立跨学科人脉网络",
            "培养T型知识结构（深耕一个领域的同时拓展相关领域）"
        ]
    },
    "cap_req_practice": {
        "短期": [
            "完成课程设计和实验报告",
            "参加专业技能竞赛",
            "申请实验室或课题组助研岗位",
            "使用所学知识解决一个实际问题"
        ],
        "长期": [
            "寻找与专业相关的实习机会",
            "参与企业实际项目或课题研究",
            "建立个人项目作品集（GitHub、Portfolio）",
            "考取行业认可的技术认证"
        ]
    },
    "cap_req_digital": {
        "短期": [
            "学习办公软件高级功能（Excel数据分析、PPT设计）",
            "掌握文献管理工具（EndNote、Zotero）",
            "学习基础编程技能（Python、R）",
            "了解AI工具的基本原理和应用场景"
        ],
        "长期": [
            "学习数据分析和可视化工具",
            "掌握机器学习和人工智能基础",
            "建立数据分析项目经验",
            "探索数字技术在专业领域的应用"
        ]
    },
    "cap_req_innovation": {
        "短期": [
            "参加创新思维训练工作坊",
            "尝试用新方法解决熟悉的问题",
            "记录并分析创新想法",
            "参与头脑风暴活动"
        ],
        "长期": [
            "参加创新创业大赛",
            "尝试将创意转化为实际项目",
            "申请发明专利或软件著作权",
            "关注并分析行业创新趋势"
        ]
    },
    "cap_req_teamwork": {
        "短期": [
            "在课程项目中主动承担不同角色",
            "学习团队协作工具（Notion、Trello、飞书）",
            "参加团队体育运动或集体活动",
            "练习有效的会议组织和时间管理"
        ],
        "长期": [
            "争取学生组织或社团的组织管理机会",
            "参与跨部门或跨专业合作项目",
            "学习冲突管理和团队激励技巧",
            "培养服务意识和领导者视野"
        ]
    },
    "cap_req_social": {
        "短期": [
            "主动与同学、老师建立联系",
            "参加学术会议或行业活动",
            "维护和拓展社交媒体专业网络",
            "学习职业礼仪和沟通技巧"
        ],
        "长期": [
            "建立个人职业社交圈",
            "寻找行业导师或职业榜样",
            "参与行业协会或专业社群",
            "维护和发展长期人际关系网络"
        ]
    },
    "cap_req_growth": {
        "短期": [
            "制定个人学习计划和目标",
            "养成每日阅读和反思的习惯",
            "记录学习笔记和成长日志",
            "寻求反馈并持续改进"
        ],
        "长期": [
            "建立个人知识管理体系（PKM）",
            "培养元认知能力和学习方法论",
            "关注行业趋势和新兴技术",
            "制定并执行3-5年职业发展规划"
        ]
    }
}

def calculate_industry_match(scores):
    """计算用户与各行业的匹配度"""
    results = []
    for industry, req in INDUSTRY_REQUIREMENTS.items():
        weighted_sum = 0
        for dim, weight in req["权重"].items():
            weighted_sum += scores.get(dim, 60) * weight

        # 计算与核心能力的匹配度
        core_match = sum([scores.get(cap, 60) for cap in req["核心能力"]]) / len(req["核心能力"])

        # 综合得分
        total_score = (weighted_sum * 0.6 + core_match * 0.4)

        results.append({
            "industry": industry,
            "match_score": round(total_score, 1),
            "description": req["描述"],
            "core_abilities": [DIMENSION_NAMES[c] for c in req["核心能力"]]
        })

    # 按匹配度排序
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results

def generate_short_term_plan(scores):
    """生成短期提升计划（3-6个月）"""
    # 选择分数在40-70分之间的维度作为提升目标
    improvement_targets = []
    for dim, score in scores.items():
        if 40 <= score <= 70:
            improvement_targets.append((dim, score))

    # 按分数升序排列，优先提升较低分数的维度
    improvement_targets.sort(key=lambda x: x[1])

    # 选择2-3个最需要提升的维度
    top_targets = improvement_targets[:3]

    plan = []
    for dim, score in top_targets:
        suggestions = SKILL_IMPROVEMENT_SUGGESTIONS.get(dim, {}).get("短期", [])
        plan.append({
            "dimension": DIMENSION_NAMES.get(dim, dim),
            "current_score": score,
            "suggestions": suggestions[:2]  # 每个维度提供2条短期建议
        })

    return plan

def generate_long_term_goals(scores):
    """生成长期发展目标（1-2年）"""
    # 选择分数低于50或高于70的维度
    goals = []

    for dim, score in scores.items():
        if score < 50:
            # 低分维度作为需要重点培养的能力
            suggestions = SKILL_IMPROVEMENT_SUGGESTIONS.get(dim, {}).get("长期", [])
            goals.append({
                "dimension": DIMENSION_NAMES.get(dim, dim),
                "current_score": score,
                "goal_type": "重点培养",
                "suggestions": suggestions[:2]
            })
        elif score > 80:
            # 高分维度作为可以深化的优势
            suggestions = SKILL_IMPROVEMENT_SUGGESTIONS.get(dim, {}).get("长期", [])
            goals.append({
                "dimension": DIMENSION_NAMES.get(dim, dim),
                "current_score": score,
                "goal_type": "深化优势",
                "suggestions": suggestions[:2]
            })

    # 按分数升序排列
    goals.sort(key=lambda x: x["current_score"])
    return goals[:4]  # 最多返回4个目标

def extract_resume_keywords(resume_text):
    """提取画像材料关键词并分析"""
    # 常见技能关键词库
    skill_keywords = {
        "编程语言": ["Python", "Java", "C++", "JavaScript", "Go", "Rust", "SQL", "R", "MATLAB", "PHP"],
        "框架工具": ["Spring", "Django", "React", "Vue", "Angular", "Node.js", "Flask", "FastAPI", "TensorFlow", "PyTorch"],
        "数据处理": ["Excel", "SPSS", "SAS", "Power BI", "Tableau", "FineBI", "ETL", "Hadoop", "Spark"],
        "设计工具": ["Photoshop", "Illustrator", "Figma", "Sketch", "Premiere", "After Effects"],
        "文档写作": ["Word", "LaTeX", "Markdown", "Notion", "Obsidian"],
        "协作工具": ["Git", "SVN", "Jira", "Confluence", "飞书", "钉钉", "企业微信"],
        "语言能力": ["英语", "CET-4", "CET-6", "IELTS", "TOEFL", "日语", "法语", "德语"],
        "软技能": ["沟通", "协调", "领导", "团队合作", "项目管理", "时间管理", "问题解决", "批判性思维"]
    }

    found_keywords = {category: [] for category in skill_keywords}

    for category, keywords in skill_keywords.items():
        for keyword in keywords:
            if keyword.lower() in resume_text.lower():
                found_keywords[category].append(keyword)

    # 计算技能密度
    total_skills = sum(len(kws) for kws in found_keywords.values())
    skill_density = min(total_skills / 10, 1.0)  # 假设10个技能为理想状态

    return {
        "found_keywords": found_keywords,
        "total_skills": total_skills,
        "skill_density": round(skill_density * 100, 1),
        "suggestions": generate_keyword_suggestions(found_keywords, skill_density)
    }

def generate_keyword_suggestions(found_keywords, skill_density):
    """生成画像材料关键词优化建议"""
    suggestions = []

    # 检查缺失的技能类别
    missing_categories = [cat for cat, kws in found_keywords.items() if not kws]

    if missing_categories:
        suggestions.append(f"建议补充以下技能领域：{', '.join(missing_categories[:3])}")

    if skill_density < 50:
        suggestions.append("画像材料中技能关键词较少，建议增加技术技能描述，如熟练使用的工具、掌握的技术栈等")

    # 检查软硬技能比例
    soft_skills = found_keywords.get("软技能", [])
    hard_skills_count = sum(len(kws) for cat, kws in found_keywords.items() if cat != "软技能")

    if len(soft_skills) > hard_skills_count:
        suggestions.append("建议增加更多硬技能描述，如编程语言、工具使用等，使材料更具技术说服力")
    elif len(soft_skills) < 2 and hard_skills_count > 5:
        suggestions.append("建议适当增加软技能描述，如团队协作、沟通能力等，展现综合素质")

    return suggestions

def generate_detailed_analysis(scores, resume_text=""):
    """生成详细的能力分析报告"""
    analysis = {
        "dimension_analysis": [],  # 各维度详细分析
        "advantage_dimensions": [],  # 优势维度
        "劣势_dimensions": [],  # 劣势维度
        "overall_evaluation": "",  # 整体评价
        "short_term_plan": [],  # 短期提升计划
        "long_term_goals": [],  # 长期发展目标
        "industry_match": [],  # 行业适配性分析
        "resume_analysis": {}  # 画像材料关键词分析
    }

    # 1. 各维度详细分析
    for dim, score in scores.items():
        dim_name = DIMENSION_NAMES.get(dim, dim)
        analysis["dimension_analysis"].append({
            "dimension": dim_name,
            "score": score,
            "level": "高" if score >= 75 else ("中" if score >= 50 else "低"),
            "interpretation": get_dimension_interpretation(dim, score)
        })

    # 2. 优势和劣势维度排序
    sorted_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    analysis["advantage_dimensions"] = [
        {"dimension": DIMENSION_NAMES.get(dim, dim), "score": score}
        for dim, score in sorted_dims[:3]
    ]
    analysis["劣势_dimensions"] = [
        {"dimension": DIMENSION_NAMES.get(dim, dim), "score": score}
        for dim, score in sorted_dims[-3:]
    ]

    # 3. 整体评价
    avg_score = sum(scores.values()) / len(scores)
    analysis["overall_evaluation"] = generate_overall_evaluation(scores, avg_score)

    # 4. 生成发展计划
    analysis["short_term_plan"] = generate_short_term_plan(scores)
    analysis["long_term_goals"] = generate_long_term_goals(scores)

    # 5. 行业适配性分析
    analysis["industry_match"] = calculate_industry_match(scores)

    # 6. 画像材料关键词分析
    if resume_text:
        analysis["resume_analysis"] = extract_resume_keywords(resume_text)

    return analysis

def get_dimension_interpretation(dim, score):
    """获取维度的详细解读"""
    interpretations = {
        "cap_req_theory": {
            "高": "您展现出扎实的专业理论基础，能够深入理解学科核心概念并灵活应用。建议继续保持理论学习的深度和广度，关注学科前沿动态。",
            "中": "您的专业理论基础处于中等水平，对核心概念有基本理解。建议加强系统性学习，构建完整的知识体系。",
            "低": "您的专业理论基础相对薄弱，建议从核心教材入手，系统性地补足基础知识，建立扎实的理论根基。"
        },
        "cap_req_cross": {
            "高": "您具备优秀的跨学科视野，能够整合多领域知识解决问题。建议继续拓展知识边界，培养T型知识结构。",
            "中": "您有一定的跨学科学习经历，但知识整合能力有待加强。建议选择性学习相关领域课程，培养跨学科思维。",
            "低": "您的知识面相对单一，建议主动学习其他领域的知识，培养跨学科思维和问题解决能力。"
        },
        "cap_req_practice": {
            "高": "您具备丰富的实践经验和出色的动手能力，能够将理论知识转化为实际成果。建议积累更多项目经验，建立个人作品集。",
            "中": "您有一定的实践经验，但项目经历相对有限。建议主动寻找实习和项目机会，提升动手能力。",
            "低": "您的实践经验相对不足，建议从课程项目和基础实验开始，逐步积累实际工作经验。"
        },
        "cap_req_digital": {
            "高": "您具备优秀的数字素养，熟练使用各种数字化工具和平台。建议继续学习数据分析和AI工具，保持技术敏感度。",
            "中": "您基本掌握常用办公软件，但数据分析能力有待提升。建议学习Python、R等数据分析工具。",
            "低": "您的数字化能力需要加强，建议从基础办公软件开始，系统学习数据分析工具和编程技能。"
        },
        "cap_req_innovation": {
            "高": "您具备出色的创新思维和创业精神，善于发现问题和提出新解决方案。建议将创新想法转化为实际项目。",
            "中": "您有一定的创新意识，但创新实践相对有限。建议参与创新竞赛或尝试小规模创新实践。",
            "低": "您的创新思维需要培养，建议多接触新事物，练习发散性思考，积极参与创新活动。"
        },
        "cap_req_teamwork": {
            "高": "您具备优秀的团队协作能力，善于沟通和协调。建议争取团队领导机会，提升项目管理能力。",
            "中": "您能够融入团队工作，但领导协调经验有限。建议在团队项目中主动承担不同角色，积累协作经验。",
            "低": "您的团队协作经验较少，建议积极参与团队活动和学生组织，培养沟通和协调能力。"
        },
        "cap_req_social": {
            "高": "您拥有广泛的社会实践网络和良好的人际关系。建议维护并拓展人脉，为职业发展积累资源。",
            "中": "您有一定的社会实践经历，但人脉网络有限。建议主动参与行业活动，建立职业社交圈。",
            "低": "您的社会实践经验和人脉资源相对不足，建议积极参加社会实践和行业交流，拓展社交网络。"
        },
        "cap_req_growth": {
            "高": "您具备出色的学习能力和成长潜力，能够快速适应新环境。建议制定清晰的职业发展规划，持续提升竞争力。",
            "中": "您有较好的学习能力，但成长目标不够明确。建议设定具体的学习和发展目标，制定实施计划。",
            "低": "您的学习和发展潜力有待挖掘，建议从培养良好学习习惯开始，制定阶段性成长目标。"
        }
    }
    level = "高" if score >= 75 else ("中" if score >= 50 else "低")
    return interpretations.get(dim, {}).get(level, "该维度分析暂未完善。")

def generate_overall_evaluation(scores, avg_score):
    """生成整体评价"""
    # 计算各维度均衡度
    max_score = max(scores.values())
    min_score = min(scores.values())
    balance = 1 - (max_score - min_score) / 100

    # 计算能力分布特征
    high_dims = [DIMENSION_NAMES.get(k, k) for k, v in scores.items() if v >= 75]
    low_dims = [DIMENSION_NAMES.get(k, k) for k, v in scores.items() if v < 50]

    evaluation = f"您的能力雷达图呈现"

    if balance >= 0.8:
        evaluation += "均衡发展型特征，各维度发展较为平衡，没有明显的短板。"
    elif balance >= 0.6:
        evaluation += "略有差异型特征，能力分布相对均衡，但仍有提升空间。"
    else:
        evaluation += "差异明显型特征，能力发展有一定偏向，建议关注薄弱维度。"

    if high_dims:
        evaluation += f"优势维度包括{'、'.join(high_dims)}，这些是您的核心竞争力。"

    if low_dims:
        evaluation += f"需要重点关注的维度包括{'、'.join(low_dims)}，建议制定针对性的提升计划。"

    evaluation += f"综合平均分为{avg_score:.1f}分，整体处于{'优秀' if avg_score >= 75 else ('良好' if avg_score >= 60 else ('中等' if avg_score >= 50 else '较低'))}水平。"

    return evaluation


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
