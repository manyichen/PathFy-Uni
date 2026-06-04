"""
根据 job_title_promotions + learning_resources + competitions 生成晋升推荐关联 CSV。

输出：
  datasets/promotion/promotion_learning_resources.csv
  datasets/promotion/promotion_competitions.csv

匹配逻辑见 datasets/promotion/job_title_promotion_recommendations_schema.md
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_MASTER = ROOT / "datasets" / "master"
DATA_PROMOTION = ROOT / "datasets" / "promotion"

# 岗位在竞赛 CSV 中无直链时，用同赛道 JobTitle 做竞赛池扩展
_COMP_JOB_ALIASES: dict[str, list[str]] = {
    "销售助理": ["BD经理", "商务专员", "大客户代表", "销售工程师"],
    "电话销售": ["BD经理", "商务专员"],
    "网络销售": ["BD经理", "商务专员"],
    "广告销售": ["BD经理", "商务专员"],
    "大客户代表": ["BD经理", "商务专员"],
    "商务专员": ["BD经理", "咨询顾问", "项目专员/助理"],
    "运营助理/专员": ["产品专员/助理", "内容审核"],
    "游戏运营": ["产品专员/助理", "内容审核"],
    "社区运营": ["产品专员/助理", "内容审核"],
    "销售运营": ["BD经理", "商务专员", "项目专员/助理"],
    "APP推广": ["产品专员/助理", "内容审核"],
    "游戏推广": ["产品专员/助理", "内容审核"],
    "招聘专员/助理": ["管培生/储备干部", "项目经理/主管"],
    "猎头顾问": ["管培生/储备干部", "咨询顾问"],
    "培训师": ["管培生/储备干部"],
    "储备干部": ["管培生/储备干部", "项目经理/主管"],
    "管培生/储备干部": ["项目经理/主管", "产品专员/助理"],
    "售后客服": ["内容审核"],
    "网络客服": ["内容审核"],
    "电话客服": ["内容审核"],
    "档案管理": ["资料管理", "项目专员/助理"],
    "资料管理": ["项目专员/助理", "项目经理/主管"],
    "质检员": ["质量管理/测试", "硬件测试"],
    "项目招投标": ["项目经理/主管", "BD经理", "商务专员"],
    "风电工程师": ["C/C++", "科研人员"],
}

INTERVIEW_RESOURCE_PREFIX = "job_interview"
INTERVIEW_PER_PROMOTION = 2
INTERVIEW_STAGE = 3

# 通用面试资源：keywords 命中晋级路径语境时加分；job_titles 为强匹配岗位
_INTERVIEW_META: dict[str, dict] = {
    "job_interview1": {
        "keywords": ["初级", "助理", "入门", "应届", "规划", "生涯"],
        "universal": True,
    },
    "job_interview2": {
        "keywords": ["群面", "网申", "offer", "单面", "笔试", "面试"],
        "universal": True,
    },
    "job_interview3": {
        "keywords": ["面试", "自我介绍", "紧张", "套路", "应届"],
        "universal": True,
    },
    "job_interview4": {
        "keywords": ["职场", "适应", "精英", "通关", "应聘"],
        "universal": True,
    },
    "job_interview5": {
        "keywords": ["简历", "模拟面试", "求职", "陷阱"],
        "job_titles": {"招聘专员/助理", "猎头顾问", "管培生/储备干部", "储备干部"},
    },
    "job_interview6": {
        "keywords": ["礼仪", "形象", "商务", "售前", "销售", "客服", "行政"],
        "job_titles": {
            "销售助理",
            "电话销售",
            "网络销售",
            "广告销售",
            "大客户代表",
            "BD经理",
            "商务专员",
            "行政专员/助理",
            "律师",
            "法务",
            "翻译",
            "英语翻译",
            "日语翻译",
        },
    },
    "job_interview7": {
        "keywords": ["沟通", "无领导", "讨论", "协调", "团队", "表达", "商务"],
        "job_titles": {
            "销售工程师",
            "实施工程师",
            "技术支持工程师",
            "咨询顾问",
            "项目经理/主管",
            "项目专员/助理",
            "产品专员/助理",
            "BD经理",
            "商务专员",
        },
    },
    "job_interview8": {
        "keywords": ["沟通", "面试", "心理", "紧张", "线上", "呈现", "求职力"],
        "universal": True,
    },
    "job_interview9": {
        "keywords": [
            "管理",
            "主管",
            "经理",
            "总监",
            "负责人",
            "人力",
            "招聘",
            "猎头",
            "培训",
            "管培",
            "储备",
            "质量经理",
            "qa",
            "运营",
            "行政",
        ],
        "job_titles": {
            "招聘专员/助理",
            "猎头顾问",
            "培训师",
            "管培生/储备干部",
            "储备干部",
            "项目经理/主管",
            "资料管理",
            "档案管理",
        },
    },
    "job_interview10": {
        "keywords": [
            "开发",
            "工程师",
            "架构",
            "测试",
            "java",
            "c++",
            "前端",
            "后端",
            "运维",
            "嵌入",
            "硬件",
            "科研",
            "算法",
            "编程",
            "python",
            "sdet",
            "sre",
            "网络",
            "系统",
            "软件",
            "技术",
            "数据",
        ],
        "job_titles": {
            "Java",
            "C/C++",
            "前端开发",
            "测试工程师",
            "软件测试",
            "硬件测试",
            "科研人员",
            "网络工程师",
            "系统工程师",
            "风电工程师",
            "质量管理/测试",
        },
        "anti_if_non_tech": True,
    },
}

_TECH_CONTEXT_MARKERS = (
    "开发",
    "工程师",
    "架构",
    "测试",
    "java",
    "c++",
    "前端",
    "后端",
    "运维",
    "嵌入",
    "硬件",
    "科研",
    "算法",
    "编程",
    "python",
    "sdet",
    "sre",
    "网络工程师",
    "系统",
    "软件",
    "技术专家",
    "可靠性",
)

_MGMT_CONTEXT_MARKERS = (
    "管理",
    "主管",
    "经理",
    "总监",
    "负责人",
    "leader",
    "qa主管",
    "质量经理",
    "项目总监",
    "产品总监",
    "技术负责人",
    "研发主管",
    "售前总监",
    "商务总监",
)

_ROUTE_KEYWORDS: dict[str, list[str]] = {
    "架构": ["架构", "算法", "数据结构", "系统设计", "Spring"],
    "SDET": ["自动化", "测试", "编程", "Java", "Python"],
    "自动化": ["自动化", "测试", "编程"],
    "管理": ["管理", "项目", "团队", "沟通"],
    "运维": ["Linux", "运维", "网络", "Docker"],
    "嵌入式": ["嵌入式", "C++", "单片机", "电路"],
    "售前": ["售前", "方案", "沟通", "产品"],
    "法务": ["法律", "法务", "合同"],
    "翻译": ["英语", "翻译", "日语"],
    "数据": ["数据", "统计", "分析", "SQL", "Python"],
    "增长": ["运营", "推广", "市场", "用户"],
    "质量": ["质量", "测试", "QA"],
}


def _split_jobs(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split("|") if p.strip()]


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _route_keywords(promo: dict) -> list[str]:
    text = _blob(promo.get("title"), promo.get("promotion"), promo.get("stage3"))
    keys: list[str] = []
    for k, hints in _ROUTE_KEYWORDS.items():
        if k.lower() in text:
            keys.extend(hints)
    return keys


def _stage_role(promo: dict, stage: int) -> str:
    if stage == 1:
        return str(promo.get("stage1") or "")
    if stage == 2:
        return str(promo.get("stage2") or "")
    return str(promo.get("stage3") or "")


def _preferred_difficulty(stage: int) -> set[str]:
    if stage == 1:
        return {"入门"}
    if stage == 2:
        return {"进阶"}
    return {"进阶", "高阶"}


def _score_lr(row: dict, promo: dict, stage: int) -> tuple[float, str]:
    role = _stage_role(promo, stage).lower()
    diff = (row.get("difficulty") or "").strip()
    pref = _preferred_difficulty(stage)
    score = 0.15
    reasons: list[str] = []

    if diff in pref:
        score += 0.28
        reasons.append(f"难度{diff}适配阶段{stage}")
    elif stage == 3 and diff == "入门":
        score += 0.05

    blob = _blob(row.get("skill_tag"), row.get("resource_name"), row.get("resource_desc"))
    for kw in _route_keywords(promo):
        if kw.lower() in blob:
            score += 0.12
            reasons.append(f"匹配路线关键词{kw}")
            break

    for token in re.split(r"[/\s、]+", role):
        t = token.strip().lower()
        if len(t) >= 2 and t in blob:
            score += 0.2
            reasons.append(f"贴合阶段目标「{role[:20]}」")
            break

    rtype = row.get("resource_type") or ""
    if stage == 1 and rtype == "视频课程":
        score += 0.08
    if stage == 3 and rtype in ("在线练习", "文档教程"):
        score += 0.06

    if not reasons:
        reasons.append("同 JobTitle 岗位资源池")
    return round(min(1.0, score), 4), "；".join(reasons[:2])


def _score_comp(row: dict, promo: dict, stage: int, matched_via: str) -> tuple[float, str]:
    diff = (row.get("difficulty") or "").strip()
    pref = _preferred_difficulty(stage)
    score = 0.2
    reasons = [matched_via]

    if diff in pref:
        score += 0.25
        reasons.append(f"难度{diff}")
    tags = _blob(row.get("cap_tags"), row.get("skill_tags"))
    for kw in _route_keywords(promo):
        if kw.lower() in tags:
            score += 0.15
            reasons.append(f"能力标签含{kw}")
            break
    if stage == 3:
        score += 0.08
    return round(min(1.0, score), 4), "；".join(reasons[:2])


def _index_resources(rows: list[dict]) -> dict[str, list[dict]]:
    by_job: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        for j in _split_jobs(row.get("job_name", "")):
            by_job[j].append(row)
    return by_job


def _interview_resource_pool(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if (row.get("resource_id") or "").strip().startswith(INTERVIEW_RESOURCE_PREFIX)
    ]


def _promo_context(promo: dict) -> str:
    return _blob(
        promo.get("job_title"),
        promo.get("title"),
        promo.get("promotion"),
        promo.get("stage1"),
        promo.get("stage2"),
        promo.get("stage3"),
        promo.get("stage3_job_title"),
        promo.get("notes"),
    )


def _has_tech_context(ctx: str) -> bool:
    return any(m in ctx for m in _TECH_CONTEXT_MARKERS)


def _has_mgmt_context(ctx: str) -> bool:
    return any(m in ctx for m in _MGMT_CONTEXT_MARKERS)


def _score_interview_lr(row: dict, promo: dict) -> tuple[float, str]:
    """按晋级路径语境为通用面试资源打分，避免仅因难度/类型固定选中同一两条。"""
    rid = (row.get("resource_id") or "").strip()
    meta = _INTERVIEW_META.get(rid, {})
    ctx = _promo_context(promo)
    jt = (promo.get("job_title") or "").strip()
    score = 0.18
    reasons: list[str] = []

    title_affinity = meta.get("job_titles") or set()
    if jt in title_affinity:
        score += 0.3
        reasons.append(f"适配岗位「{jt}」面试场景")

    hits = [kw for kw in meta.get("keywords", []) if kw.lower() in ctx]
    if hits:
        score += min(0.34, 0.11 * len(hits))
        reasons.append(f"贴合晋级路径「{hits[0]}」")

    res_blob = _blob(row.get("skill_tag"), row.get("resource_name"), row.get("resource_desc"))
    for kw in _route_keywords(promo):
        if kw.lower() in res_blob or kw.lower() in ctx:
            score += 0.12
            reasons.append(f"匹配路线能力「{kw}」")
            break

    if meta.get("universal") and not hits and jt not in title_affinity:
        score += 0.14
        reasons.append("通用求职面试基础")

    if meta.get("anti_if_non_tech") and not _has_tech_context(ctx):
        score -= 0.22
        if "技术" not in "；".join(reasons):
            reasons.append("非技术向晋级路径")

    if rid == "job_interview9" and _has_tech_context(ctx) and not _has_mgmt_context(ctx):
        score -= 0.14

    if rid == "job_interview6" and _has_tech_context(ctx) and not any(
        k in ctx for k in ("销售", "售前", "商务", "客服", "行政", "律师", "法务")
    ):
        score -= 0.08

    if not reasons:
        reasons.append("通用面试资源池")
    return round(min(1.0, max(0.05, score)), 4), "；".join(reasons[:3])


def _pick_top_interview(
    scored: list[tuple[float, dict, str]], n: int
) -> list[tuple[float, dict, str]]:
    """取 top N，并尽量覆盖不同 skill_tag，避免两条高度同质。"""
    scored.sort(key=lambda x: (-x[0], x[1].get("resource_id", "")))
    picked: list[tuple[float, dict, str]] = []
    used_tags: set[str] = set()
    for item in scored:
        if len(picked) >= n:
            break
        tag = (item[1].get("skill_tag") or item[1].get("resource_id") or "").strip()
        if picked and tag in used_tags:
            continue
        picked.append(item)
        used_tags.add(tag)
    for item in scored:
        if len(picked) >= n:
            break
        if item not in picked:
            picked.append(item)
    return picked[:n]


def _index_competitions(rows: list[dict]) -> dict[str, list[dict]]:
    by_job: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        for j in _split_jobs(row.get("job_name", "")):
            by_job[j].append(row)
    return by_job


def _comp_pool(job_title: str, stage3_jt: str, comp_by_job: dict) -> list[tuple[dict, str]]:
    seen: set[str] = set()
    out: list[tuple[dict, str]] = []
    titles = [job_title]
    if stage3_jt:
        titles.append(stage3_jt)
    titles.extend(_COMP_JOB_ALIASES.get(job_title, []))

    for t in titles:
        for row in comp_by_job.get(t, []):
            cid = row.get("competition_id", "")
            if cid and cid not in seen:
                seen.add(cid)
                via = "JobTitle直链" if t == job_title else f"关联赛道岗位「{t}」"
                out.append((row, via))
    return out


def build() -> tuple[list[dict], list[dict]]:
    promos = list(
        csv.DictReader((DATA_PROMOTION / "job_title_promotions.csv").open(encoding="utf-8-sig"))
    )
    lr_rows = list(csv.DictReader((DATA_MASTER / "learning_resources.csv").open(encoding="utf-8-sig")))
    comp_rows = list(csv.DictReader((DATA_MASTER / "competitions.csv").open(encoding="utf-8-sig")))
    lr_by_job = _index_resources(lr_rows)
    comp_by_job = _index_competitions(comp_rows)
    interview_pool = _interview_resource_pool(lr_rows)

    lr_out: list[dict] = []
    comp_out: list[dict] = []

    max_lr = {1: 5, 2: 5, 3: 4}
    interview_rank_start = max_lr[INTERVIEW_STAGE] + 1
    max_comp = {2: 2, 3: 3}

    for promo in promos:
        pid = promo["promotion_id"].strip()
        jt = promo["job_title"].strip()
        s3jt = (promo.get("stage3_job_title") or "").strip()
        pool_lr = lr_by_job.get(jt, [])

        for stage in (1, 2, 3):
            scored = []
            for row in pool_lr:
                s, rationale = _score_lr(row, promo, stage)
                scored.append((s, row, rationale))
            scored.sort(key=lambda x: (-x[0], x[1].get("resource_id", "")))
            for rank, (s, row, rationale) in enumerate(scored[: max_lr[stage]], 1):
                lr_out.append(
                    {
                        "promotion_id": pid,
                        "job_title": jt,
                        "stage": stage,
                        "stage_role": _stage_role(promo, stage),
                        "resource_id": row.get("resource_id", ""),
                        "resource_name": row.get("resource_name", ""),
                        "difficulty": row.get("difficulty", ""),
                        "resource_type": row.get("resource_type", ""),
                        "skill_tag": row.get("skill_tag", ""),
                        "score": s,
                        "rank": rank,
                        "rationale": rationale,
                    }
                )

        if interview_pool:
            scored_iv = [
                (*_score_interview_lr(row, promo), row)
                for row in interview_pool
            ]
            scored_iv = [(s, row, rationale) for s, rationale, row in scored_iv]
            for rank, (s, row, rationale) in enumerate(
                _pick_top_interview(scored_iv, INTERVIEW_PER_PROMOTION),
                interview_rank_start,
            ):
                lr_out.append(
                    {
                        "promotion_id": pid,
                        "job_title": jt,
                        "stage": INTERVIEW_STAGE,
                        "stage_role": _stage_role(promo, INTERVIEW_STAGE),
                        "resource_id": row.get("resource_id", ""),
                        "resource_name": row.get("resource_name", ""),
                        "difficulty": row.get("difficulty", ""),
                        "resource_type": row.get("resource_type", ""),
                        "skill_tag": row.get("skill_tag", ""),
                        "score": s,
                        "rank": rank,
                        "rationale": f"通用面试资源；{rationale}",
                    }
                )

        comp_pool = _comp_pool(jt, s3jt, comp_by_job)
        for stage in (2, 3):
            scored_c = []
            for row, via in comp_pool:
                s, rationale = _score_comp(row, promo, stage, via)
                scored_c.append((s, row, rationale))
            scored_c.sort(key=lambda x: (-x[0], x[1].get("competition_id", "")))
            for rank, (s, row, rationale) in enumerate(scored_c[: max_comp[stage]], 1):
                comp_out.append(
                    {
                        "promotion_id": pid,
                        "job_title": jt,
                        "stage": stage,
                        "stage_role": _stage_role(promo, stage),
                        "competition_id": row.get("competition_id", ""),
                        "competition_name": row.get("competition_name", ""),
                        "difficulty": row.get("difficulty", ""),
                        "competition_type": row.get("competition_type", ""),
                        "award_level": row.get("award_level", ""),
                        "score": s,
                        "rank": rank,
                        "match_via": rationale.split("；")[0] if rationale else "",
                        "rationale": rationale,
                    }
                )

    return lr_out, comp_out


def main() -> int:
    lr_out, comp_out = build()
    lr_fields = [
        "promotion_id",
        "job_title",
        "stage",
        "stage_role",
        "resource_id",
        "resource_name",
        "difficulty",
        "resource_type",
        "skill_tag",
        "score",
        "rank",
        "rationale",
    ]
    comp_fields = [
        "promotion_id",
        "job_title",
        "stage",
        "stage_role",
        "competition_id",
        "competition_name",
        "difficulty",
        "competition_type",
        "award_level",
        "score",
        "rank",
        "match_via",
        "rationale",
    ]
    lr_path = DATA_PROMOTION / "promotion_learning_resources.csv"
    comp_path = DATA_PROMOTION / "promotion_competitions.csv"
    with lr_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=lr_fields)
        w.writeheader()
        w.writerows(lr_out)
    with comp_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=comp_fields)
        w.writeheader()
        w.writerows(comp_out)

    promos = len(
        list(csv.DictReader((DATA_PROMOTION / "job_title_promotions.csv").open(encoding="utf-8-sig")))
    )
    with_comp = len({r["promotion_id"] for r in comp_out})
    interview_links = sum(
        1 for r in lr_out if (r.get("resource_id") or "").startswith(INTERVIEW_RESOURCE_PREFIX)
    )
    print(
        {
            "promotions": promos,
            "lr_links": len(lr_out),
            "interview_lr_links": interview_links,
            "comp_links": len(comp_out),
            "promotions_with_comp": with_comp,
            "promotions_without_comp": promos - with_comp,
            "lr_path": str(lr_path),
            "comp_path": str(comp_path),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
