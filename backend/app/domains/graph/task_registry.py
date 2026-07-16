"""Single source of truth for graph update task inputs and presentation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileSpec:
    role: str
    extensions: frozenset[str]
    required: bool = True
    max_bytes: int = 25 * 1024 * 1024


@dataclass(frozen=True)
class TaskSpec:
    label: str
    category: str
    files: tuple[FileSpec, ...] = ()
    default_mode: str = "merge"
    supports_source: bool = False
    uses_llm: bool = False
    dangerous: bool = False
    defaults: dict = field(default_factory=dict)
    description: str = ""
    input_format: str = ""
    columns: tuple[str, ...] = ()
    icon: str = "i-lucide-database"


CSV = frozenset({".csv"})
TASK_SPECS: dict[str, TaskSpec] = {
    "job_import": TaskSpec("岗位 Excel 导入", "jobs", (FileSpec("file", frozenset({".xls", ".xlsx"})),), "merge", True, True, defaults={"batch_size": 128, "capability_batch_size": 8, "generate_promotions": True, "generate_lateral": True}, description="导入岗位并强制完成八维评估、岗位名称同步及所选派生关系。", input_format="Excel（.xls/.xlsx）", columns=("岗位名称", "公司名称", "地址", "薪资范围", "所属行业", "岗位详情", "岗位编码", "岗位来源地址"), icon="i-lucide-file-spreadsheet"),
    "job_capability_evaluation": TaskSpec("存量岗位八维评估", "jobs", uses_llm=True, defaults={"scope": "missing", "capability_batch_size": 8}, description="按缺失、过期或全部范围重评非 inferred 岗位。", input_format="无需文件", icon="i-lucide-gauge"),
    "job_capability_result_import": TaskSpec("历史能力结果导入", "jobs", (FileSpec("file", frozenset({".jsonl"})),), description="导入经过严格校验的历史八维评估结果。", input_format="JSONL（每行一个 JSON）", columns=("job_key/job_id", "scores", "confidence", "evidence", "risk_flags"), icon="i-lucide-file-json-2"),
    "learning_resource_import": TaskSpec("学习资源导入", "curated", (FileSpec("file", CSV),), "snapshot", True, description="导入策展学习资源及岗位名称关联。", input_format="CSV（UTF-8）", columns=("resource_id", "job_name", "resource_name", "resource_url", "resource_type", "difficulty", "skill_tag"), icon="i-lucide-book-open"),
    "competition_import": TaskSpec("竞赛导入", "curated", (FileSpec("file", CSV),), "snapshot", True, description="导入策展竞赛及岗位名称关联。", input_format="CSV（UTF-8）", columns=("competition_id", "job_name", "competition_name", "official_url", "competition_type", "difficulty", "cap_tags", "skill_tags"), icon="i-lucide-trophy"),
    "job_promotion_import": TaskSpec("晋升路线导入", "curated", (FileSpec("file", CSV),), "snapshot", True, description="导入策展晋升路线，优先级高于自动路线。", input_format="CSV（UTF-8）", columns=("promotion_id", "job_title", "title", "promotion", "stage1", "stage2", "stage3", "stage3_job_title"), icon="i-lucide-trending-up"),
    "job_lateral_import": TaskSpec("横向换岗导入", "curated", (FileSpec("file", CSV),), "snapshot", True, description="导入策展的有向换岗关系。", input_format="CSV（UTF-8）", columns=("from_job_title", "to_job_title", "score", "rank", "track_from", "track_to", "cap_similarity", "rationale"), icon="i-lucide-git-compare-arrows"),
    "promotion_recommendation_import": TaskSpec("晋升推荐导入", "curated", (FileSpec("learning_file", CSV), FileSpec("competition_file", CSV)), "snapshot", True, description="在一个原子任务中导入学习资源与竞赛推荐关系。", input_format="两个 CSV（UTF-8）", columns=("promotion_id", "resource_id/competition_id", "stage", "rank", "score"), icon="i-lucide-waypoints"),
    "salary_normalization": TaskSpec("薪资规范化", "maintenance", defaults={"force": False}, description="用当前解析版本补齐或重算岗位薪资字段。", input_format="无需文件", icon="i-lucide-badge-dollar-sign"),
    "inferred_job_cleanup": TaskSpec("清理推断岗位", "maintenance", dangerous=True, description="固化并清理 inferred Job 与低频 JobTitle。", input_format="无需文件", icon="i-lucide-trash-2"),
    "graph_inverse": TaskSpec("恢复上一版属性", "maintenance", dangerous=True, description="从可恢复的成功任务创建，只恢复已经固化的旧属性。", input_format="由历史任务生成", icon="i-lucide-rotate-ccw"),
    "emergency_clear": TaskSpec("紧急清空图谱", "maintenance", dangerous=True, description="绕过普通任务规划的紧急全量清空。", input_format="专用二次确认接口", icon="i-lucide-triangle-alert"),
}

TASK_TYPES = frozenset(TASK_SPECS)
TASK_HANDLERS: dict[str, tuple[str | None, str | None]] = {
    "job_import": ("job_import", "job_import"),
    "job_capability_evaluation": ("job_capability_evaluation", "job_capability_evaluation"),
    "job_capability_result_import": ("job_capability_result_import", "job_capability_result_import"),
    "learning_resource_import": ("learning_resource_import", "learning_resource_import"),
    "competition_import": ("competition_import", "competition_import"),
    "job_promotion_import": ("job_promotion_import", "job_promotion_import"),
    "job_lateral_import": ("job_lateral_import", "job_lateral_import"),
    "promotion_recommendation_import": ("promotion_recommendation_import", "promotion_recommendation_import"),
    "salary_normalization": ("salary_normalization", "salary_normalization"),
    "inferred_job_cleanup": ("inferred_job_cleanup", "inferred_job_cleanup"),
    "graph_inverse": (None, "graph_inverse"),
    "emergency_clear": (None, None),
}


def task_spec(task_type: str) -> TaskSpec:
    try:
        return TASK_SPECS[task_type]
    except KeyError as exc:
        raise ValueError("不支持的任务类型") from exc


CATEGORY_LABELS = {"jobs": "岗位与能力", "curated": "策展数据", "maintenance": "图谱维护"}


def task_catalog() -> list[dict]:
    result = []
    for task_type, spec in TASK_SPECS.items():
        result.append({
            "task_type": task_type,
            "label": spec.label,
            "category": spec.category,
            "category_label": CATEGORY_LABELS.get(spec.category, spec.category),
            "description": spec.description,
            "input_format": spec.input_format,
            "columns": list(spec.columns),
            "icon": spec.icon,
            "default_mode": spec.default_mode,
            "supports_source": spec.supports_source,
            "uses_llm": spec.uses_llm,
            "dangerous": spec.dangerous,
            "defaults": dict(spec.defaults),
            "files": [{
                "role": item.role,
                "extensions": sorted(item.extensions),
                "required": item.required,
                "max_bytes": item.max_bytes,
            } for item in spec.files],
            "create_via": "reverse" if task_type == "graph_inverse" else "emergency" if task_type == "emergency_clear" else "tasks",
        })
    return result


def normalize_options(task_type: str, values: dict) -> dict:
    spec = task_spec(task_type)
    options = dict(spec.defaults)
    if task_type == "job_import":
        options.update(batch_size=max(1, min(int(values.get("batch_size") or 128), 1000)), capability_batch_size=max(1, min(int(values.get("capability_batch_size") or 8), 50)), generate_promotions=_bool(values.get("generate_promotions"), True), generate_lateral=_bool(values.get("generate_lateral"), True))
    elif task_type == "job_capability_evaluation":
        scope = str(values.get("scope") or "missing").lower()
        if scope not in {"missing", "stale", "all"}:
            raise ValueError("scope 仅支持 missing、stale 或 all")
        options.update(scope=scope, source_id=str(values.get("source_id") or "").strip() or None, capability_batch_size=max(1, min(int(values.get("capability_batch_size") or 8), 50)))
    elif task_type == "salary_normalization":
        options["force"] = _bool(values.get("force"), False)
    return options


def _bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
