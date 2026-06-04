"""
根据 JobTitle 能力画像、职业赛道、晋升互指计算水平换岗相似关系，导出 CSV。

信号（加权）：
  - 岗位八维能力画像余弦相似（Neo4j Job 聚合，可选）
  - 同职业赛道加分
  - 晋升路线 stage3 指向另一 JobTitle 时加分

输出：
  datasets/master/job_title_lateral_transfer.csv

用法：
  python tools/csv/build_job_title_lateral_similarity.py
  python tools/csv/build_job_title_lateral_similarity.py --top 10 --min-score 0.18
"""
from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "datasets" / "master"
PROMOTION = ROOT / "datasets" / "promotion"
OUT_CSV = MASTER / "job_title_lateral_transfer.csv"
load_dotenv(ROOT / "backend" / ".env")

CAP_KEYS = (
    "cap_req_theory",
    "cap_req_cross",
    "cap_req_practice",
    "cap_req_digital",
    "cap_req_innovation",
    "cap_req_teamwork",
    "cap_req_social",
    "cap_req_growth",
)

TRACK_GROUPS: dict[str, list[str]] = {
    "技术研发": [
        "Java",
        "C/C++",
        "前端开发",
        "科研人员",
        "网络工程师",
        "系统工程师",
        "风电工程师",
    ],
    "测试质量": [
        "测试工程师",
        "软件测试",
        "硬件测试",
        "质量管理/测试",
        "质检员",
    ],
    "实施运维": ["实施工程师", "技术支持工程师"],
    "产品项目": [
        "产品专员/助理",
        "项目经理/主管",
        "项目专员/助理",
        "项目招投标",
        "咨询顾问",
    ],
    "市场销售": [
        "销售助理",
        "电话销售",
        "网络销售",
        "广告销售",
        "大客户代表",
        "BD经理",
        "商务专员",
        "销售工程师",
        "销售运营",
    ],
    "运营增长": [
        "运营助理/专员",
        "游戏运营",
        "社区运营",
        "APP推广",
        "游戏推广",
        "内容审核",
    ],
    "人力培训": [
        "招聘专员/助理",
        "猎头顾问",
        "培训师",
        "管培生/储备干部",
        "储备干部",
    ],
    "法务知产": ["律师", "律师助理", "法务专员/助理", "知识产权/专利代理"],
    "语言翻译": ["英语翻译", "日语翻译"],
    "客服支持": ["售后客服", "网络客服", "电话客服"],
    "行政档案": ["档案管理", "资料管理"],
    "数据分析": ["统计员"],
}

WEIGHT_CAP = 0.65
WEIGHT_TRACK = 0.25
WEIGHT_PROMO = 0.10


def _cosine(va: list[float], vb: list[float]) -> float:
    dot = sum(x * y for x, y in zip(va, vb))
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(x * x for x in vb))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _title_to_track() -> dict[str, str]:
    out: dict[str, str] = {}
    for track, titles in TRACK_GROUPS.items():
        for t in titles:
            out[t] = track
    return out


def _load_titles() -> list[str]:
    path = MASTER / "job_title_record_counts.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r["job_title"].strip() for r in csv.DictReader(f) if r.get("job_title")]


def _load_promotion_lateral_pairs() -> set[tuple[str, str]]:
    path = PROMOTION / "job_title_promotions.csv"
    pairs: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            src = (row.get("job_title") or "").strip()
            tgt = (row.get("stage3_job_title") or "").strip()
            if src and tgt and src != tgt:
                pairs.add((src, tgt))
                pairs.add((tgt, src))
    return pairs


def _fetch_cap_profiles(titles: list[str]) -> dict[str, list[float]]:
    password = os.getenv("NEO4J_PASSWORD", "")
    if not password:
        return {}
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return {}

    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "neo4j")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    avg_exprs = ", ".join(f"avg(coalesce(j.{k}, 0.0)) AS {k}" for k in CAP_KEYS)
    query = f"""
    MATCH (j:Job)-[:HAS_TITLE]->(jt:JobTitle)
    WHERE jt.name IN $titles
    RETURN jt.name AS title, {avg_exprs}
    """
    driver = GraphDatabase.driver(uri, auth=(user, password))
    out: dict[str, list[float]] = {}
    try:
        with driver.session(database=database) as session:
            for row in session.run(query, {"titles": titles}):
                rec = dict(row)
                title = str(rec.get("title") or "").strip()
                if title:
                    out[title] = [float(rec.get(k) or 0.0) for k in CAP_KEYS]
    finally:
        driver.close()
    return out


def _rationale(*, cap_sim: float, same_track: bool, promo_link: bool) -> str:
    parts: list[str] = []
    if cap_sim >= 0.75:
        parts.append("能力画像高度相近")
    elif cap_sim >= 0.55:
        parts.append("能力画像较为接近")
    if same_track:
        parts.append("同职业赛道")
    if promo_link:
        parts.append("晋升终点岗位互相关联")
    if not parts:
        parts.append("能力画像或赛道有一定相似")
    return "；".join(parts[:3])


def build(*, top_n: int, min_score: float) -> list[dict]:
    titles = _load_titles()
    title_track = _title_to_track()
    promo_pairs = _load_promotion_lateral_pairs()
    cap_by = _fetch_cap_profiles(titles)

    rows: list[dict] = []
    for src in titles:
        scored: list[tuple[float, str, dict]] = []
        va = cap_by.get(src, [0.0] * len(CAP_KEYS))

        for dst in titles:
            if src == dst:
                continue
            vb = cap_by.get(dst, [0.0] * len(CAP_KEYS))
            cap_sim = _cosine(va, vb) if cap_by else 0.0
            same_track = title_track.get(src) == title_track.get(dst) and src in title_track
            promo_link = (src, dst) in promo_pairs

            score = (
                WEIGHT_CAP * cap_sim
                + (WEIGHT_TRACK if same_track else 0.0)
                + (WEIGHT_PROMO if promo_link else 0.0)
            )
            if score < min_score:
                continue

            meta = {
                "cap_sim": cap_sim,
                "same_track": same_track,
                "promo_link": promo_link,
            }
            scored.append((round(score, 4), dst, meta))

        scored.sort(key=lambda x: (-x[0], x[1]))
        for rank, (score, dst, meta) in enumerate(scored[:top_n], 1):
            rows.append(
                {
                    "from_job_title": src,
                    "to_job_title": dst,
                    "score": score,
                    "rank": rank,
                    "track_from": title_track.get(src, ""),
                    "track_to": title_track.get(dst, ""),
                    "cap_similarity": round(meta["cap_sim"], 4),
                    "same_track": "1" if meta["same_track"] else "0",
                    "promotion_linked": "1" if meta["promo_link"] else "0",
                    "rationale": _rationale(**meta),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 JobTitle 水平换岗相似关系 CSV")
    parser.add_argument("--top", type=int, default=8, help="每个来源岗位保留相似目标数")
    parser.add_argument("--min-score", type=float, default=0.15, help="最低相似分")
    args = parser.parse_args()

    rows = build(top_n=args.top, min_score=args.min_score)
    fields = [
        "from_job_title",
        "to_job_title",
        "score",
        "rank",
        "track_from",
        "track_to",
        "cap_similarity",
        "same_track",
        "promotion_linked",
        "rationale",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    from_titles = len({r["from_job_title"] for r in rows})
    print(
        {
            "output": str(OUT_CSV),
            "edges": len(rows),
            "from_job_titles": from_titles,
            "top_per_title": args.top,
            "min_score": args.min_score,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
