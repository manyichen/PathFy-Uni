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


CSV = frozenset({".csv"})
TASK_SPECS: dict[str, TaskSpec] = {
    "job_import": TaskSpec("岗位 Excel 导入", "jobs", (FileSpec("file", frozenset({".xls", ".xlsx"})),), "merge", True, True, defaults={"batch_size": 128, "capability_batch_size": 8, "generate_promotions": True, "generate_lateral": True}),
    "job_capability_evaluation": TaskSpec("存量岗位八维评估", "jobs", uses_llm=True, defaults={"scope": "missing", "capability_batch_size": 8}),
    "job_capability_result_import": TaskSpec("历史能力结果导入", "jobs", (FileSpec("file", frozenset({".jsonl"})),)),
    "job_workstyle_import": TaskSpec("岗位工作环境画像导入", "jobs", (FileSpec("file", CSV),), "merge", True),
    "job_workstyle_evaluation": TaskSpec("存量岗位工作环境评估", "jobs", defaults={"scope": "missing"}),
    "learning_resource_import": TaskSpec("学习资源导入", "curated", (FileSpec("file", CSV),), "snapshot", True),
    "competition_import": TaskSpec("竞赛导入", "curated", (FileSpec("file", CSV),), "snapshot", True),
    "job_promotion_import": TaskSpec("晋升路线导入", "curated", (FileSpec("file", CSV),), "snapshot", True),
    "job_lateral_import": TaskSpec("横向换岗导入", "curated", (FileSpec("file", CSV),), "snapshot", True),
    "promotion_recommendation_import": TaskSpec("晋升推荐导入", "curated", (FileSpec("learning_file", CSV), FileSpec("competition_file", CSV)), "snapshot", True),
    "salary_normalization": TaskSpec("薪资规范化", "maintenance", defaults={"force": False}),
    "inferred_job_cleanup": TaskSpec("清理推断岗位", "maintenance", dangerous=True),
    "emergency_clear": TaskSpec("紧急清空图谱", "maintenance", dangerous=True),
}

TASK_TYPES = frozenset(TASK_SPECS)
TASK_HANDLERS: dict[str, tuple[str | None, str | None]] = {
    "job_import": ("job_import", "job_import"),
    "job_capability_evaluation": ("job_capability_evaluation", "job_capability_evaluation"),
    "job_capability_result_import": ("job_capability_result_import", "job_capability_result_import"),
    "job_workstyle_import": ("job_workstyle_import", "job_workstyle_import"),
    "job_workstyle_evaluation": ("job_workstyle_evaluation", "job_workstyle_evaluation"),
    "learning_resource_import": ("learning_resource_import", "learning_resource_import"),
    "competition_import": ("competition_import", "competition_import"),
    "job_promotion_import": ("job_promotion_import", "job_promotion_import"),
    "job_lateral_import": ("job_lateral_import", "job_lateral_import"),
    "promotion_recommendation_import": ("promotion_recommendation_import", "promotion_recommendation_import"),
    "salary_normalization": ("salary_normalization", "salary_normalization"),
    "inferred_job_cleanup": ("inferred_job_cleanup", "inferred_job_cleanup"),
    "emergency_clear": (None, None),
}


def task_spec(task_type: str) -> TaskSpec:
    try:
        return TASK_SPECS[task_type]
    except KeyError as exc:
        raise ValueError("不支持的任务类型") from exc


def normalize_options(task_type: str, values: dict) -> dict:
    spec = task_spec(task_type)
    options = dict(spec.defaults)
    if task_type == "job_import":
        options.update(batch_size=max(1, min(int(values.get("batch_size") or 128), 1000)), capability_batch_size=max(1, min(int(values.get("capability_batch_size") or 8), 50)), generate_promotions=_bool(values.get("generate_promotions"), True), generate_lateral=_bool(values.get("generate_lateral"), True))
    elif task_type in {"job_capability_evaluation", "job_workstyle_evaluation"}:
        scope = str(values.get("scope") or "missing").lower()
        if scope not in {"missing", "stale", "all"}:
            raise ValueError("scope 仅支持 missing、stale 或 all")
        options.update(scope=scope, source_id=str(values.get("source_id") or "").strip() or None)
        if task_type == "job_capability_evaluation":
            options["capability_batch_size"] = max(1, min(int(values.get("capability_batch_size") or 8), 50))
    elif task_type == "salary_normalization":
        options["force"] = _bool(values.get("force"), False)
    return options


def _bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
