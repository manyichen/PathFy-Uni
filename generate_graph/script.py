import argparse
import json
import os
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional

import pandas as pd
from google import genai
from ollama import Client as OllamaClient
from py2neo import Graph


DEFAULT_XLS_PATH = os.path.join("..", "datasets", "20260226105856_457.xls")
DEFAULT_BATCH_SIZE = 128
MAX_RETRIES = 5
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"

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

SYSTEM_PROMPT = """
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
3. experience_req / internship_req 为字符串，未提及填“未知”。
4. 不确定信息请给空数组或“未知”，不要编造细节。
5. 输入的连续文本（岗位详情、公司详情）必须完整理解后再抽取。
"""


def normalize_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", normalize_text(title)).lower()


def parse_experience_years(exp_text: str) -> float:
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


def normalize_ollama_base_url(base_url: str) -> str:
    url = normalize_text(base_url) or DEFAULT_OLLAMA_BASE_URL
    url = re.sub(r"/+$", "", url)
    if url.endswith("/v1"):
        url = url[:-3]
    return re.sub(r"^http://localhost(?=[:/]|$)", "http://127.0.0.1", url)


def build_llm_prompt(payload: List[Dict[str, Any]]) -> str:
    records_json = json.dumps(payload, ensure_ascii=False)
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"输入岗位数组 JSON:\n{records_json}\n\n"
        "请输出与输入 idx 一一对应的 records。"
    )


def parse_llm_records(raw_text: str, source_name: str) -> List[Dict[str, Any]]:
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict) or "records" not in parsed:
        raise ValueError(f"{source_name} 返回格式不符合预期，缺少 records 字段。")
    if not isinstance(parsed["records"], list):
        raise ValueError(f"{source_name} 返回 records 不是数组。")
    return parsed["records"]


def call_gemini_batch(client: genai.Client, model: str, payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prompt = build_llm_prompt(payload)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                },
            )
            return parse_llm_records(response.text, "Gemini")
        except Exception as exc:
            wait_seconds = attempt * 2
            print(f"[WARN] Gemini 调用失败，第 {attempt} 次: {exc}")
            if attempt == MAX_RETRIES:
                print("[WARN] 达到最大重试次数，当前批次将使用空结构兜底。")
                return []
            time.sleep(wait_seconds)
    return []


def call_ollama_batch(client: OllamaClient, model: str, payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prompt = build_llm_prompt(payload)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.generate(
                model=model,
                prompt=prompt,
                stream=False,
                format="json",
                options={"temperature": 0.1},
                think=False,
            )
            text = response.get("response", "")
            return parse_llm_records(text, "Ollama")
        except Exception as exc:
            wait_seconds = attempt * 2
            print(f"[WARN] Ollama 调用失败，第 {attempt} 次: {exc}")
            if attempt == MAX_RETRIES:
                print("[WARN] 达到最大重试次数，当前批次将使用空结构兜底。")
                return []
            time.sleep(wait_seconds)
    return []


def build_ai_payload(batch_df: pd.DataFrame) -> List[Dict[str, Any]]:
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


def merge_batch_to_neo4j(
    graph: Graph,
    batch_df: pd.DataFrame,
    ai_records: List[Dict[str, Any]],
    core_templates: set,
) -> None:
    idx_to_ai: Dict[int, Dict[str, Any]] = {}
    for item in ai_records:
        if isinstance(item, dict) and isinstance(item.get("idx"), int):
            idx_to_ai[item["idx"]] = item

    tx = graph.begin()

    for local_idx, row in batch_df.reset_index(drop=True).iterrows():
        ai_data = idx_to_ai.get(local_idx, {})
        job_title = normalize_text(row["name"])
        company_name = normalize_text(row["company"])
        exp_text = normalize_text(ai_data.get("experience_req", "未知"))
        demand = normalize_text(row["demand"])
        job_key = f"{normalize_title(job_title)}::{company_name.lower()}"

        tx.run(
            """
            MERGE (j:Job {job_key:$job_key})
            SET j.title=$title,
                j.company=$company,
                j.location=$location,
                j.salary=$salary,
                j.industry=$industry,
                j.company_size=$company_size,
                j.company_type=$company_type,
                j.job_code=$job_code,
                j.updated_date=$updated_date,
                j.experience_text=$experience_text,
                j.experience_years=$experience_years,
                j.internship_req=$internship_req,
                j.demand=$demand,
                j.source_url=$source_url,
                j.company_detail=$company_detail,
                j.is_core_template=$is_core_template
            """,
            job_key=job_key,
            title=job_title,
            company=company_name,
            location=normalize_text(row["location"]),
            salary=normalize_text(row["salary"]),
            industry=normalize_text(row["industry"]),
            company_size=normalize_text(row["company_size"]),
            company_type=normalize_text(row["company_type"]),
            job_code=normalize_text(row["job_code"]),
            updated_date=normalize_text(row["updated_date"]),
            experience_text=exp_text,
            experience_years=parse_experience_years(exp_text),
            internship_req=normalize_text(ai_data.get("internship_req", "未知")),
            demand=demand,
            source_url=normalize_text(row["source_url"]),
            company_detail=normalize_text(row["company_detail"]),
            is_core_template=normalize_title(job_title) in core_templates,
        )

        tx.run(
            """
            MERGE (c:Company {name:$company})
            WITH c
            MATCH (j:Job {job_key:$job_key})
            MERGE (j)-[:BELONGS_TO]->(c)
            """,
            company=company_name,
            job_key=job_key,
        )

        hard_skills = {
            normalize_text(x)
            for x in ai_data.get("hard_skills", [])
            if normalize_text(x)
        }
        for skill in hard_skills:
            tx.run(
                """
                MERGE (s:Skill {name:$name})
                WITH s
                MATCH (j:Job {job_key:$job_key})
                MERGE (j)-[:REQUIRES]->(s)
                """,
                name=skill,
                job_key=job_key,
            )

        certificates = ai_data.get("certificates", [])
        if isinstance(certificates, list):
            for cert in certificates:
                cert_name = normalize_text(cert)
                if not cert_name:
                    continue
                tx.run(
                    """
                    MERGE (c:Certificate {name:$name})
                    WITH c
                    MATCH (j:Job {job_key:$job_key})
                    MERGE (j)-[:REQUIRES]->(c)
                    """,
                    name=cert_name,
                    job_key=job_key,
                )

        soft_skills = ai_data.get("soft_skills", {})
        if isinstance(soft_skills, dict):
            for dim in ["innovation", "learning", "stress", "comm"]:
                level = normalize_text(soft_skills.get(dim, "未知")) or "未知"
                tx.run(
                    """
                    MERGE (s:SoftSkill {name:$name})
                    SET s.level=$level
                    WITH s
                    MATCH (j:Job {job_key:$job_key})
                    MERGE (j)-[:REQUIRES]->(s)
                    """,
                    name=dim,
                    level=level,
                    job_key=job_key,
                )

        tx.run(
            """
            MERGE (cl:CareerLevel {name:$level_name})
            WITH cl
            MATCH (j:Job {job_key:$job_key})
            MERGE (j)-[:BELONGS_TO]->(cl)
            """,
            level_name=exp_text or "未知",
            job_key=job_key,
        )

    graph.commit(tx)


def process_in_batches(
    df: pd.DataFrame,
    graph: Graph,
    llm_provider: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    gemini_client: Optional[genai.Client] = None,
    ollama_client: Optional[OllamaClient] = None,
    gemini_model: str = "gemini-2.5-flash",
    ollama_model: str = "qwen3.5:4b",
) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0。")

    title_counter = Counter(normalize_title(x) for x in df["name"])
    core_templates = {title for title, _ in title_counter.most_common(10)}

    total = len(df)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_df = df.iloc[start:end].copy()
        print(f"[INFO] 处理批次 {start}-{end - 1} / {total - 1}")

        payload = build_ai_payload(batch_df)
        if llm_provider == "gemini":
            if gemini_client is None:
                raise RuntimeError("llm_provider=gemini 时 gemini_client 不能为空。")
            ai_records = call_gemini_batch(gemini_client, gemini_model, payload)
        else:
            if ollama_client is None:
                raise RuntimeError("llm_provider=ollama 时 ollama_client 不能为空。")
            ai_records = call_ollama_batch(ollama_client, ollama_model, payload)

        try:
            merge_batch_to_neo4j(
                graph=graph,
                batch_df=batch_df,
                ai_records=ai_records,
                core_templates=core_templates,
            )
        except Exception as exc:
            print(f"[ERROR] 批次写入 Neo4j 失败: {exc}")
            continue


def load_excel_data(excel_path: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(excel_path)
    except ImportError as exc:
        raise RuntimeError("读取 .xls 需要安装依赖：pip install xlrd>=2.0.1") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"未找到数据文件: {excel_path}") from exc
    except Exception as exc:
        raise RuntimeError(f"读取 Excel 失败: {exc}") from exc

    missing_cols = [c for c in REQUIRED_CN_COLUMNS if c not in df.columns]
    if missing_cols:
        raise RuntimeError(f"Excel 缺少必要字段: {missing_cols}")

    return df.rename(columns=COLUMN_ALIASES)


def main() -> None:
    parser = argparse.ArgumentParser(description="招聘数据 ETL 与职业发展知识图谱构建")
    parser.add_argument("--excel-path", default=DEFAULT_XLS_PATH, help="招聘数据 Excel 路径（.xls）")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="批处理大小，建议 64/128/256")
    parser.add_argument("--clear-all", action="store_true", help="执行前清空 Neo4j 中全部数据")
    parser.add_argument("--llm-provider", choices=["gemini", "ollama"], default="gemini", help="大模型提供方")
    parser.add_argument("--gemini-model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), help="Gemini 模型名")
    parser.add_argument("--ollama-base-url", default=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL), help="Ollama 服务地址")
    parser.add_argument("--ollama-model", default=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"), help="Ollama 模型名")
    args = parser.parse_args()

    gemini_client: Optional[genai.Client] = None
    ollama_client: Optional[OllamaClient] = None
    if args.llm_provider == "gemini":
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise RuntimeError("llm_provider=gemini 时缺少 GEMINI_API_KEY 环境变量。")
        gemini_client = genai.Client(api_key=gemini_key)
    else:
        safe_ollama_base_url = normalize_ollama_base_url(args.ollama_base_url)
        if safe_ollama_base_url != args.ollama_base_url:
            print(f"[INFO] Ollama 地址已规范化: {args.ollama_base_url} -> {safe_ollama_base_url}")
        ollama_client = OllamaClient(host=safe_ollama_base_url)

    graph = Graph(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "neo4j123456")),
    )
    df = load_excel_data(args.excel_path)

    if args.clear_all:
        print("[INFO] 清空旧图谱数据...")
        graph.delete_all()

    print(f"[INFO] 数据总量: {len(df)}，批大小: {args.batch_size}，LLM: {args.llm_provider}")
    process_in_batches(
        df=df,
        graph=graph,
        llm_provider=args.llm_provider,
        batch_size=args.batch_size,
        gemini_client=gemini_client,
        ollama_client=ollama_client,
        gemini_model=args.gemini_model,
        ollama_model=args.ollama_model,
    )
    print("[INFO] 图谱构建完成。")


if __name__ == "__main__":
    main()
