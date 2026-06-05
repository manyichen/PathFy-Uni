"""Graph ETL 域：常量、Prompt 模板、工具函数。"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ============================================================
# Excel 列映射
# ============================================================

REQUIRED_CN_COLUMNS = [
    "岗位名称",
    "地址",
    "薪资范围",
    "公司名称",
    "所属行业",
    "公司规模",
    "公司类型",
    "岗位编码",
    "岗位详情",
    "更新日期",
    "公司详情",
    "岗位来源地址",
]

COLUMN_ALIASES = {
    "岗位名称": "name",
    "地址": "location",
    "薪资范围": "salary",
    "公司名称": "company",
    "所属行业": "industry",
    "公司规模": "company_size",
    "公司类型": "company_type",
    "岗位编码": "job_code",
    "岗位详情": "demand",
    "更新日期": "updated_date",
    "公司详情": "company_detail",
    "岗位来源地址": "source_url",
}

# ============================================================
# LLM Prompt 模板
# ============================================================

JOB_EXTRACTION_SYSTEM_PROMPT = """
你是招聘数据结构化专家。请基于输入岗位数组进行批量抽取与推断，并严格返回 JSON。

返回格式（必须为 JSON 对象）:
{
  "records": [
    {
      "idx": 0,
      "hard_skills": ["Python", "Kubernetes"],
      "soft_skills": {
        "innovation": "中",
        "learning": "高",
        "stress": "中",
        "comm": "高"
      },
      "certificates": ["AWS Certified Solutions Architect"],
      "experience_req": "1-3年",
      "internship_req": "可实习6个月"
    }
  ]
}

约束:
1. hard_skills / certificates 必须是字符串数组。
2. soft_skills 必须包含 innovation, learning, stress, comm 四个字段，值为低/中/高。
3. experience_req / internship_req 为字符串，未提及填"未知"。
4. 不确定信息请给空数组或"未知"，不要编造细节。
5. 输入的连续文本（岗位详情、公司详情）必须完整理解后再抽取。
"""

PROMOTION_SYSTEM_PROMPT = "你是严谨的职业晋升路径分析助手。"


def build_company_prompt(company: str, jobs: List[Dict[str, Any]]) -> str:
    """构建晋升边推断的每公司 Prompt。"""
    import json

    payload = [
        {
            "title": x["title"],
            "experience_years": round(float(x.get("experience_years", 0)), 2),
            "location": x.get("location", ""),
        }
        for x in jobs
    ]
    payload_json = json.dumps(payload, ensure_ascii=False)

    return (
        "你是招聘职业路径分析专家。请在同一家公司内部，根据岗位标题和经验要求，"
        "推断合理的晋升边（from_title -> to_title）。\n"
        "要求:\n"
        "1. 只能使用输入列表中的岗位标题。\n"
        "2. 只能输出同公司内部的晋升，不要横向转岗。\n"
        "3. 输出应避免循环，优先形成层级清晰的路径。\n"
        "4. 每条边给出简短 reason 和 0~1 confidence。\n"
        "5. 若无法判断，返回空数组。\n\n"
        "返回 JSON 对象，格式必须严格如下:\n"
        "{\n"
        '  "edges": [\n'
        "    {\n"
        '      "from_title": "岗位A",\n'
        '      "to_title": "岗位B",\n'
        '      "reason": "简短原因",\n'
        '      "confidence": 0.78\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"公司: {company}\n"
        f"岗位列表 JSON: {payload_json}\n"
    )


# ============================================================
# 职级权重 & 生涯评分
# ============================================================

SENIORITY_WEIGHTS: List[Tuple[str, float]] = [
    ("实习", -2.0),
    ("助理", -1.5),
    ("初级", -1.0),
    ("junior", -1.0),
    ("中级", 0.5),
    ("高级", 2.0),
    ("资深", 2.5),
    ("专家", 3.0),
    ("主管", 3.0),
    ("经理", 3.5),
    ("manager", 3.5),
    ("负责人", 4.0),
    ("lead", 4.0),
    ("总监", 5.0),
    ("director", 5.0),
    ("vp", 6.0),
    ("chief", 6.0),
]

# ============================================================
# 常量
# ============================================================

SOURCE_TAG = "openai_lmstudio"
DEFAULT_BATCH_SIZE = 128
MAX_RETRIES = 5
CORE_TEMPLATE_COUNT = 10
SOFT_SKILL_DIMS = ["innovation", "learning", "stress", "comm"]


# ============================================================
# 数据类
# ============================================================

@dataclass
class JobProfile:
    """岗位画像（从 Neo4j 读取后用于晋升推断）。"""
    job_key: str
    title: str
    company: str
    experience_years: float
    location: str
    demand: str
    career_score: float


@dataclass
class PromotionEdge:
    """晋升边。"""
    from_key: str
    to_key: str
    company: str
    from_title: str
    to_title: str
    reason: str
    confidence: float


# ============================================================
# 文本工具函数
# ============================================================

def normalize_text(value: Any) -> str:
    """安全地把任意值转成去空白字符串。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def normalize_title(title: str) -> str:
    """岗位标题归一化：去空白 + 小写。"""
    return re.sub(r"\s+", "", normalize_text(title)).lower()


def normalize_key(value: str) -> str:
    """通用归一化键：去空白 + 小写。"""
    return re.sub(r"\s+", "", normalize_text(value)).lower()


def parse_experience_years(exp_text: str) -> float:
    """从经验文本中提取数值年份。"""
    exp_text = normalize_text(exp_text)
    if not exp_text:
        return 0.0
    if "应届" in exp_text or "不限" in exp_text:
        return 0.0
    if "1年以内" in exp_text:
        return 0.5
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", exp_text)]
    if not nums:
        return 0.0
    return sum(nums) / len(nums)


def calc_seniority_boost(title: str) -> float:
    """根据标题关键词计算职级加分。"""
    lowered = normalize_key(title)
    score = 0.0
    for keyword, weight in SENIORITY_WEIGHTS:
        if keyword in lowered:
            score += weight
    return score


def calc_career_score(title: str, experience_years: float) -> float:
    """综合经验年限 + 职级关键词计算生涯得分。"""
    return (experience_years * 10.0) + calc_seniority_boost(title)


# ============================================================
# 批量提取辅助
# ============================================================

def build_ai_payload(batch_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """将一个批次的 DataFrame 转为 LLM 输入 payload。"""
    payload = []
    for i, row in batch_df.reset_index(drop=True).iterrows():
        payload.append(
            {
                "idx": i,
                "job_name": normalize_text(row["name"]),
                "location": normalize_text(row["location"]),
                "salary": normalize_text(row["salary"]),
                "company": normalize_text(row["company"]),
                "industry": normalize_text(row["industry"]),
                "company_size": normalize_text(row["company_size"]),
                "company_type": normalize_text(row["company_type"]),
                "job_code": normalize_text(row["job_code"]),
                "job_detail": normalize_text(row["demand"]),
                "updated_date": normalize_text(row["updated_date"]),
                "company_detail": normalize_text(row["company_detail"]),
                "source_url": normalize_text(row["source_url"]),
            }
        )
    return payload


def compute_core_templates(df: pd.DataFrame, top_n: int = CORE_TEMPLATE_COUNT) -> set:
    """按归一化标题频率取 top_n 作为核心模板岗位。"""
    title_counter = Counter(normalize_title(x) for x in df["name"])
    return {title for title, _ in title_counter.most_common(top_n)}
