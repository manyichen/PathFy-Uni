import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from py2neo import Graph


SOURCE_TAG = "openai_lmstudio"
DEFAULT_BASE_URL = "http://121.249.146.100:1234/v1"
DEFAULT_MODEL = "qwen3.5:9b"
MAX_RETRIES = 3

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


@dataclass
class JobProfile:
    element_id: str
    company: str
    title: str
    experience_years: float
    location: str
    demand: str
    career_score: float


@dataclass
class PromotionEdge:
    from_id: str
    to_id: str
    company: str
    from_title: str
    to_title: str
    reason: str
    confidence: float


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", normalize_text(value)).lower()


def calc_seniority_boost(title: str) -> float:
    lowered = normalize_key(title)
    score = 0.0
    for keyword, weight in SENIORITY_WEIGHTS:
        if keyword in lowered:
            score += weight
    return score


def calc_career_score(title: str, experience_years: float) -> float:
    return (experience_years * 10.0) + calc_seniority_boost(title)


def parse_json_object(text: str) -> Dict[str, object]:
    raw = normalize_text(text)
    if not raw:
        raise ValueError("模型返回为空")

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", raw)
    if fenced:
        raw = fenced.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def fetch_jobs(graph: Graph, include_inferred: bool) -> List[JobProfile]:
    rows = graph.run(
        """
        MATCH (j:Job)
        WHERE coalesce(trim(toString(j.company)), '') <> ''
          AND coalesce(trim(toString(j.title)), trim(toString(j.name)), '') <> ''
          AND ($include_inferred = true OR coalesce(j.source, '') <> 'inferred')
        RETURN
          elementId(j) AS element_id,
          coalesce(j.company, '') AS company,
          coalesce(j.title, j.name) AS title,
          toFloat(coalesce(j.experience_years, 0.0)) AS experience_years,
          coalesce(j.location, '') AS location,
          coalesce(j.demand, '') AS demand
        """,
        include_inferred=include_inferred,
    )

    jobs: List[JobProfile] = []
    for row in rows:
        title = normalize_text(row["title"])
        company = normalize_text(row["company"])
        exp = float(row.get("experience_years") or 0.0)
        jobs.append(
            JobProfile(
                element_id=str(row["element_id"]),
                company=company,
                title=title,
                experience_years=exp,
                location=normalize_text(row.get("location")),
                demand=normalize_text(row.get("demand")),
                career_score=calc_career_score(title, exp),
            )
        )
    return jobs


def dedupe_titles(jobs: Iterable[JobProfile]) -> List[JobProfile]:
    best: Dict[str, JobProfile] = {}
    for job in jobs:
        key = normalize_key(job.title)
        old = best.get(key)
        if old is None or job.career_score > old.career_score:
            best[key] = job
    return list(best.values())


def build_company_prompt(company: str, jobs: List[JobProfile]) -> str:
    payload = [
        {
            "title": x.title,
            "experience_years": round(x.experience_years, 2),
            "location": x.location,
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
        "  \"edges\": [\n"
        "    {\n"
        "      \"from_title\": \"岗位A\",\n"
        "      \"to_title\": \"岗位B\",\n"
        "      \"reason\": \"简短原因\",\n"
        "      \"confidence\": 0.78\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"公司: {company}\n"
        f"岗位列表 JSON: {payload_json}\n"
    )


def ask_model_for_company_edges(
    client: OpenAI,
    model: str,
    company: str,
    jobs: List[JobProfile],
) -> List[Dict[str, object]]:
    prompt = build_company_prompt(company, jobs)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": "你是严谨的职业晋升路径分析助手。"},
                    {"role": "user", "content": prompt},
                ]
            )
            content = normalize_text(resp.choices[0].message.content)
            obj = parse_json_object(content)
            edges = obj.get("edges", []) if isinstance(obj, dict) else []
            if isinstance(edges, list):
                return [x for x in edges if isinstance(x, dict)]
            return []
        except Exception as exc:
            if attempt == MAX_RETRIES:
                print(f"[WARN] 公司 {company} 调用失败: {exc}")
                return []
            print(f"[WARN] 公司 {company} 调用失败，第 {attempt} 次重试: {exc}")

    return []


def build_edges_with_validation(
    company: str,
    jobs: List[JobProfile],
    model_edges: List[Dict[str, object]],
    min_confidence: float,
) -> List[PromotionEdge]:
    title_to_job = {normalize_key(x.title): x for x in jobs}

    edges: List[PromotionEdge] = []
    seen = set()
    for item in model_edges:
        from_title = normalize_text(item.get("from_title"))
        to_title = normalize_text(item.get("to_title"))
        reason = normalize_text(item.get("reason")) or "模型推断"

        try:
            confidence = float(item.get("confidence", 0.0))
        except Exception:
            confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))
        if confidence < min_confidence:
            continue

        src = title_to_job.get(normalize_key(from_title))
        dst = title_to_job.get(normalize_key(to_title))
        if not src or not dst:
            continue
        if src.element_id == dst.element_id:
            continue

        # Prevent obviously reversed or cyclic direction with a numeric sanity check.
        if dst.career_score <= src.career_score:
            continue

        pair_key = (src.element_id, dst.element_id)
        if pair_key in seen:
            continue
        seen.add(pair_key)

        edges.append(
            PromotionEdge(
                from_id=src.element_id,
                to_id=dst.element_id,
                company=company,
                from_title=src.title,
                to_title=dst.title,
                reason=reason,
                confidence=round(confidence, 4),
            )
        )

    return edges


def delete_existing_source_edges(graph: Graph) -> int:
    total_rows = graph.run(
        """
        MATCH ()-[r:VERTICAL_UP {source:$source}]->()
        RETURN count(r) AS total
        """,
        source=SOURCE_TAG,
    ).data()
    total = int((total_rows[0].get("total") if total_rows else 0) or 0)
    if total <= 0:
        return 0

    graph.run(
        """
        MATCH ()-[r:VERTICAL_UP {source:$source}]->()
        DELETE r
        """,
        source=SOURCE_TAG,
    )
    return total


def persist_edges(graph: Graph, edges: List[PromotionEdge]) -> int:
    tx = graph.begin()
    for e in edges:
        tx.run(
            """
            MATCH (a:Job) WHERE elementId(a) = $from_id
            MATCH (b:Job) WHERE elementId(b) = $to_id
            MERGE (a)-[r:VERTICAL_UP {source:$source}]->(b)
            SET r.reason = $reason,
                r.company = $company,
                r.confidence = $confidence,
                r.updated_at = datetime()
            """,
            from_id=e.from_id,
            to_id=e.to_id,
            source=SOURCE_TAG,
            reason=e.reason,
            company=e.company,
            confidence=e.confidence,
        )
    graph.commit(tx)
    return len(edges)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 OpenAI 兼容接口更新同公司晋升路径")

    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))

    parser.add_argument("--openai-base-url", default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL))

    parser.add_argument("--min-company-jobs", type=int, default=2)
    parser.add_argument("--max-jobs-per-company", type=int, default=10000)
    parser.add_argument("--max-companies", type=int, default=10000)
    parser.add_argument("--min-confidence", type=float, default=0.55)

    parser.add_argument("--include-inferred", action="store_true")
    parser.add_argument("--clear-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    if not args.neo4j_password:
        raise RuntimeError("缺少 Neo4j 密码，请设置 --neo4j-password 或环境变量 NEO4J_PASSWORD。")
    if not args.openai_api_key:
        raise RuntimeError("缺少 OpenAI API key，请设置 --openai-api-key 或环境变量 OPENAI_API_KEY。")

    graph = Graph(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    client = OpenAI(base_url=args.openai_base_url, api_key=args.openai_api_key)

    jobs = fetch_jobs(graph, include_inferred=args.include_inferred)
    company_groups: Dict[str, List[JobProfile]] = defaultdict(list)
    for job in jobs:
        company_groups[job.company].append(job)

    all_edges: List[PromotionEdge] = []
    checked_companies = 0
    for company, group in sorted(company_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if checked_companies >= max(1, args.max_companies):
            break

        compact_group = dedupe_titles(group)
        if len(compact_group) < max(2, args.min_company_jobs):
            continue

        checked_companies += 1
        subset = sorted(compact_group, key=lambda x: x.career_score)[: args.max_jobs_per_company]

        raw_edges = ask_model_for_company_edges(
            client=client,
            model=args.model,
            company=company,
            jobs=subset,
        )
        validated = build_edges_with_validation(
            company=company,
            jobs=subset,
            model_edges=raw_edges,
            min_confidence=max(0.0, min(1.0, args.min_confidence)),
        )
        all_edges.extend(validated)

        print(
            f"[INFO] {company}: 输入岗位 {len(subset)}，模型输出 {len(raw_edges)}，校验后 {len(validated)}"
        )

    print(f"[INFO] 可分析公司数: {checked_companies}")
    print(f"[INFO] 晋升关系候选总数: {len(all_edges)}")

    if args.dry_run:
        for edge in all_edges[:30]:
            if isinstance(edge, PromotionEdge):
                print(
                    f"[PREVIEW] {edge.company} | {edge.from_title} -> {edge.to_title} "
                    f"(conf={edge.confidence}, reason={edge.reason})"
                )
            elif isinstance(edge, dict):
                print(
                    "[PREVIEW] "
                    f"{edge.get('company', '未知公司')} | "
                    f"{edge.get('from_title', '未知岗位')} -> {edge.get('to_title', '未知岗位')} "
                    f"(conf={edge.get('confidence', 0)}, reason={edge.get('reason', '模型推断')})"
                )
        if len(all_edges) > 30:
            print(f"[PREVIEW] ... 其余 {len(all_edges) - 30} 条省略")
        print("[INFO] dry-run 模式，未写入数据库。")
        return

    if args.clear_existing:
        deleted = delete_existing_source_edges(graph)
        print(f"[INFO] 删除旧关系 source={SOURCE_TAG}: {deleted}")

    created = persist_edges(graph, all_edges)
    print(f"[INFO] 已写入/更新 VERTICAL_UP 关系: {created}")


if __name__ == "__main__":
    main()

