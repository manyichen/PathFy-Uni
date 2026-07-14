from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.domains.settings.defaults_v1 import DEFAULT_SETTINGS_V1


@dataclass(frozen=True)
class SettingField:
    key: str
    label: str
    group: str
    kind: str
    minimum: float | None = None
    maximum: float | None = None
    options: tuple[str, ...] = ()
    advanced: bool = False


def _i(key, label, group, lo, hi, advanced=False): return SettingField(key, label, group, "int", lo, hi, advanced=advanced)
def _f(key, label, group, lo, hi, advanced=False): return SettingField(key, label, group, "float", lo, hi, advanced=advanced)
def _b(key, label, group): return SettingField(key, label, group, "bool")
def _s(key, label, group, *options): return SettingField(key, label, group, "string", options=tuple(options))


FIELDS = (
    _i("AI_MAX_RETURN_JOBS", "助手最多返回岗位", "jobs", 1, 100),
    _i("AI_CONTEXT_WINDOW", "助手上下文轮数", "jobs", 1, 20),
    _i("AI_LLM_TIMEOUT_SECONDS", "助手超时（秒）", "jobs", 10, 300),
    _i("MATCH_PREVIEW_MAX_SCAN", "匹配扫描软上限", "match", 100, 8000),
    _i("MATCH_TOP_K_RETURN", "匹配返回数量", "match", 1, 100),
    _i("MATCH_LLM_POOL_K", "精排候选池", "match", 5, 100),
    _f("MATCH_COARSE_SHAPE_WEIGHT", "能力形态权重", "match", 0, 1, True),
    _f("MATCH_GAP_SOFT_MARGIN_FIT", "稳妥匹配容差", "match", 0, 30, True),
    _f("MATCH_GAP_SOFT_MARGIN_STRETCH", "冲刺匹配容差", "match", 0, 30, True),
    _f("MATCH_STRETCH_MATCH_SCORE_FLOOR", "冲刺最低匹配分", "match", 0, 100, True),
    _f("MATCH_STRETCH_SORT_W_MATCH", "冲刺匹配分权重", "match", 0, 1, True),
    _f("MATCH_STRETCH_SORT_W_JOB_AVG", "冲刺岗位强度权重", "match", 0, 1, True),
    _s("MATCH_DEEPSEEK_MODEL", "匹配精排模型", "match", "deepseek-v4-flash", "deepseek-v4-pro"),
    _i("MATCH_LLM_TIMEOUT_SECONDS", "匹配精排超时（秒）", "match", 10, 300),
    _s("CAREER_DEEPSEEK_MODEL", "报告规划模型", "career", "deepseek-v4-flash", "deepseek-v4-pro"),
    _s("CAREER_ARK_MODEL", "报告文案模型", "career", "doubao-seed-2-0-lite-260215", "doubao-seed-2-0-mini-260215"),
    _i("CAREER_LLM_TIMEOUT_SECONDS", "报告模型超时（秒）", "career", 10, 300),
    _i("CAREER_LLM_MAX_RETRIES", "报告模型重试", "career", 1, 8),
    _f("CAREER_REVIEW_EXTRACT_TEMPERATURE", "复盘提取温度", "career", 0, 1, True),
    _b("CAREER_ENABLE_COPYWRITER", "启用报告文案", "career"),
    _b("CAREER_ENABLE_PER_TARGET_COPYWRITER", "启用分岗文案", "career"),
    _b("CAREER_ENABLE_REPLAN_LLM", "启用自动重规划", "career"),
    _b("CAREER_ENABLE_TREND_AUGMENT", "启用趋势增强", "career"),
    _b("CAREER_ENABLE_PUBLIC_INFO", "启用公开信息", "career"),
    _i("CAREER_PUBLIC_INFO_CACHE_DAYS", "公开信息缓存天数", "career", 1, 90),
    _i("CAREER_PUBLIC_INFO_MAX_SUMMARY_CHARS", "公开信息摘要长度", "career", 100, 1000),
    _i("CAREER_PUBLIC_SEARCH_MAX_CHARS", "公开检索文本长度", "career", 200, 4000),
    _b("CAREER_ENABLE_GRAPH_RECOMMENDATIONS", "启用图谱推荐", "career"),
    _b("CAREER_ENABLE_RECOMMENDATION_LLM", "启用推荐精排", "career"),
    _b("CAREER_ENABLE_PLAN_CUSTOMIZATION", "启用计划定制", "career"),
    _i("CAREER_LR_POOL_PER_TARGET", "学习资源候选数", "career", 1, 50),
    _i("CAREER_COMP_POOL_PER_TARGET", "竞赛候选数", "career", 1, 30),
    _i("CAREER_LR_PER_TARGET", "默认学习资源数", "career", 1, 20),
    _i("CAREER_COMP_PER_TARGET", "默认竞赛数", "career", 0, 10),
    _s("GRAPH_LLM_MODEL", "图谱抽取模型", "graph", "doubao-seed-2-0-mini-260215", "doubao-seed-2-0-lite-260215", "deepseek-v4-flash"),
    _i("GRAPH_BATCH_SIZE", "图谱抽取批大小", "graph", 1, 500),
    _i("GRAPH_MAX_RETRIES", "图谱调用重试", "graph", 1, 10),
    _i("GRAPH_LLM_TIMEOUT_SECONDS", "图谱调用超时（秒）", "graph", 10, 600),
    _f("GRAPH_PROMOTION_MIN_CONFIDENCE", "晋升关系最低置信度", "graph", 0, 1),
    _f("GRAPH_CAP_REVIEW_CONFIDENCE_THRESHOLD", "八维复核阈值", "graph", 0, 1),
    _s("GRAPH_CAP_PRIMARY_PROVIDER", "八维主评 Provider", "graph", "deepseek"),
    _s("GRAPH_CAP_PRIMARY_MODEL", "八维主评模型", "graph", "deepseek-v4-flash", "deepseek-v4-pro"),
    _s("GRAPH_CAP_REVIEW_PROVIDER", "八维复核 Provider", "graph", "qwen"),
    _s("GRAPH_CAP_REVIEW_MODEL", "八维复核模型", "graph", "qwen3.6-plus"),
    _i("GRAPH_CAP_LLM_TIMEOUT_SECONDS", "八维评估超时（秒）", "graph", 10, 600),
    _i("GRAPH_CAP_MAX_RETRIES", "八维评估重试", "graph", 1, 10),
    _i("GRAPH_CAPABILITY_BATCH_SIZE", "默认八维评估批大小", "graph", 1, 50),
    _b("PLATFORM_ALLOW_EXTERNAL_LLM", "允许外部 LLM", "privacy"),
    _b("PLATFORM_ALLOW_MATCH_LLM", "允许匹配 AI 精排", "privacy"),
    _b("PLATFORM_ALLOW_REPORT_LLM", "允许报告 AI 增强", "privacy"),
)
FIELD_MAP = {field.key: field for field in FIELDS}


USER_DEFAULTS = {
    "theme": "system", "hue": "192", "allow_external_llm": True,
    "default_match_goal": "fit", "default_refine_with_llm": False, "match_result_count": 30,
    "report_public_info": True, "report_copywriter": True, "report_auto_replan": True,
    "report_graph_recommendations": True, "report_recommendation_llm": True,
    "learning_resource_count": 6, "competition_count": 3,
}


def definitions() -> list[dict[str, Any]]:
    return [asdict(field) for field in FIELDS]


def validate_settings(values: dict[str, Any], *, require_complete: bool = True, hard_scan_cap: int = 8000) -> dict[str, Any]:
    unknown = set(values) - set(FIELD_MAP)
    if unknown: raise ValueError(f"未知设置: {', '.join(sorted(unknown))}")
    if require_complete and set(values) != set(FIELD_MAP):
        missing = set(FIELD_MAP) - set(values); raise ValueError(f"缺少设置: {', '.join(sorted(missing))}")
    out: dict[str, Any] = {}
    for key, raw in values.items():
        field = FIELD_MAP[key]
        if field.kind == "bool":
            if not isinstance(raw, bool): raise ValueError(f"{field.label} 必须为布尔值")
            value = raw
        elif field.kind == "int":
            if isinstance(raw, bool): raise ValueError(f"{field.label} 必须为整数")
            value = int(raw)
        elif field.kind == "float":
            if isinstance(raw, bool): raise ValueError(f"{field.label} 必须为数字")
            value = float(raw)
        else: value = str(raw)
        if field.options and value not in field.options: raise ValueError(f"{field.label} 不在允许列表")
        if field.minimum is not None and value < field.minimum: raise ValueError(f"{field.label} 不能小于 {field.minimum}")
        if field.maximum is not None and value > field.maximum: raise ValueError(f"{field.label} 不能大于 {field.maximum}")
        out[key] = value
    if out.get("MATCH_PREVIEW_MAX_SCAN", 0) > hard_scan_cap: raise ValueError("匹配扫描软上限不能超过环境硬上限")
    if "MATCH_STRETCH_SORT_W_MATCH" in out and "MATCH_STRETCH_SORT_W_JOB_AVG" in out:
        if abs(out["MATCH_STRETCH_SORT_W_MATCH"] + out["MATCH_STRETCH_SORT_W_JOB_AVG"] - 1) > 0.001:
            raise ValueError("冲刺排序的两个权重之和必须为 1")
    return out


def validate_preferences(values: dict[str, Any]) -> dict[str, Any]:
    unknown = set(values) - set(USER_DEFAULTS)
    if unknown: raise ValueError(f"未知偏好: {', '.join(sorted(unknown))}")
    out = dict(values)
    if "theme" in out and out["theme"] not in {"system", "light", "dark"}: raise ValueError("主题值无效")
    if "hue" in out and str(out["hue"]) not in {"150", "192", "220", "270"}: raise ValueError("主题色值无效")
    if "default_match_goal" in out and out["default_match_goal"] not in {"fit", "stretch"}: raise ValueError("默认匹配目标无效")
    for key in ("allow_external_llm", "default_refine_with_llm", "report_public_info", "report_copywriter", "report_auto_replan", "report_graph_recommendations", "report_recommendation_llm"):
        if key in out and not isinstance(out[key], bool): raise ValueError(f"{key} 必须为布尔值")
    for key, lo, hi in (("match_result_count", 1, 100), ("learning_resource_count", 1, 20), ("competition_count", 0, 10)):
        if key in out:
            out[key] = int(out[key])
            if not lo <= out[key] <= hi: raise ValueError(f"{key} 超出允许范围")
    if "hue" in out: out["hue"] = str(out["hue"])
    return out
