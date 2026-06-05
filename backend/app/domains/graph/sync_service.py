"""Graph ETL 域：图谱智能生成 — LLM 自动推断晋升/换岗/学习资源/竞赛。"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, List

from app.domains.graph.services import _build_graph_llm_client, _llm_model
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings


# ============================================================
# Prompt 模板
# ============================================================

PROMOTION_PATH_SYSTEM = """你是职业发展路径专家。请根据输入的岗位名称列表，推断合理的晋升路径。

返回 JSON 对象：
{
  "paths": [
    {
      "from_title": "初级前端工程师",
      "to_title": "高级前端工程师",
      "promotion_name": "前端晋升路径",
      "stage1": "掌握 HTML/CSS/JS 基础，能独立完成页面开发",
      "stage2": "掌握 React/Vue 框架，理解组件化开发",
      "stage3": "具备架构设计能力，能主导前端项目",
      "stage3_job_title": "前端架构师",
      "confidence": 0.85,
      "rationale": "技能递进清晰，市场常见晋升路径"
    }
  ]
}

约束：
1. 只使用输入列表中存在的岗位名称。
2. 晋升方向必须合理（技能/职级递进）。
3. 每个路径给出 3 个阶段描述和最终目标岗位。
4. confidence 0~1，低于 0.5 的不要输出。
5. 找不到合适路径返回空数组。"""

LATERAL_SYSTEM = """你是职业转岗分析专家。请评估两个岗位之间的横向转岗可行性。

返回 JSON 对象：
{
  "pairs": [
    {
      "from": "后端开发工程师",
      "to": "数据分析师",
      "score": 0.72,
      "track_from": "技术研发",
      "track_to": "数据科学",
      "cap_similarity": 0.65,
      "same_track": false,
      "rationale": "两者都需要编程和逻辑思维，但数据分析偏统计和业务理解"
    }
  ]
}

约束：
1. score 0~1 综合评估转岗可行性。
2. track_from/track_to 用简短中文描述职业赛道。
3. cap_similarity 评估能力维度重叠度。
4. 只输出有实际转岗可能性的配对（score > 0.4）。"""

LEARNING_RESOURCE_SYSTEM = """你是学习资源推荐专家。请为一个岗位推荐合适的学习资源。

返回 JSON 对象：
{
  "resources": [
    {
      "resource_name": "React 官方文档",
      "resource_desc": "React 框架的权威学习资料，涵盖 hooks、状态管理、路由等核心概念",
      "resource_type": "文档",
      "difficulty": "中级",
      "skill_tag": "前端开发"
    }
  ]
}

约束：
1. resource_type 为：文档/课程/书籍/项目/认证。
2. difficulty 为：入门/初级/中级/高级。
3. skill_tag 为最相关的技能标签。
4. 每个岗位推荐 3-6 个资源，覆盖不同方向和难度。"""

COMPETITION_SYSTEM = """你是竞赛推荐专家。请为一个岗位推荐相关的学科竞赛。

返回 JSON 对象：
{
  "competitions": [
    {
      "competition_name": "全国大学生数学建模竞赛",
      "competition_desc": "三人组队在 72 小时内完成实际问题建模与求解",
      "competition_type": "学科竞赛",
      "organizer": "中国工业与应用数学学会",
      "target_audience": "本科生",
      "team_mode": "3人组队",
      "frequency": "每年一次",
      "difficulty": "高",
      "cap_tags": "数学建模,编程,论文写作",
      "skill_tags": "MATLAB,Python,算法",
      "award_level": "国家级"
    }
  ]
}

约束：
1. cap_tags 和 skill_tags 用逗号分隔。
2. 每个岗位推荐 2-4 个竞赛。
3. 优先推荐国家级、有含金量的竞赛。"""


# ============================================================
# LLM 调用辅助
# ============================================================

def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if t.startswith("```"):
        return t.replace("```json", "").replace("```", "").strip()
    return t


def _call_llm_json(system_prompt: str, user_content: str, *, label: str = "") -> dict:
    """通用 LLM JSON 调用，带重试。"""
    client = _build_graph_llm_client()
    model = _llm_model()

    for attempt in range(1, 6):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                timeout=60.0,
            )
            content = _strip_json_fence((resp.choices[0].message.content or "").strip())
            return json.loads(content)
        except Exception as exc:
            if attempt == 5:
                print(f"[WARN] {label} LLM 调用失败: {exc}")
                return {}
            wait = attempt * 2
            print(f"[WARN] {label} LLM 重试 {attempt}: {exc}")
            time.sleep(wait)
    return {}


# ============================================================
# Neo4j 读取辅助
# ============================================================

def _get_driver():
    uri, user, password, database = neo4j_settings()
    return neo4j_driver(uri, user, password), database


def fetch_all_job_titles(driver, database) -> List[str]:
    """获取所有 :JobTitle 名称列表。"""
    with driver.session(database=database) as session:
        rows = session.run("MATCH (jt:JobTitle) RETURN jt.name AS name ORDER BY jt.job_count DESC")
        return [r["name"] for r in rows]


def fetch_all_job_titles_with_counts(driver, database) -> List[Dict[str, Any]]:
    """获取 :JobTitle 名称和数量。"""
    with driver.session(database=database) as session:
        rows = session.run(
            "MATCH (jt:JobTitle) RETURN jt.name AS name, jt.job_count AS cnt ORDER BY cnt DESC"
        )
        return [{"name": r["name"], "count": r["cnt"]} for r in rows]


def _parse_confidence(value: Any) -> float:
    """把 LLM 返回的置信度安全解析到 0~1。"""
    if value is None:
        return 0.0

    is_percent = False
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return 0.0
        if raw.endswith("%"):
            is_percent = True
            raw = raw[:-1].strip()
    else:
        raw = value

    try:
        number = float(raw)
    except (TypeError, ValueError):
        return 0.0

    if is_percent or number > 1:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def _promotion_id(from_title: str, to_title: str) -> str:
    """基于起止岗位名生成稳定 promotion_id。"""
    digest = hashlib.sha1(f"{from_title}\0{to_title}".encode("utf-8")).hexdigest()
    return f"promotion_{digest[:16]}"


# ============================================================
# 1. 岗位名称实体同步
# ============================================================

def sync_job_titles(*, dry_run: bool = False) -> Dict[str, Any]:
    """从 :Job.title 聚合创建 :JobTitle 节点和 HAS_TITLE 关系。"""
    driver, database = _get_driver()

    # 聚合
    with driver.session(database=database) as session:
        result = session.run(
            """
            MATCH (j:Job)
            WHERE coalesce(trim(j.title), '') <> ''
            WITH trim(j.title) AS t, count(j) AS cnt
            RETURN t, cnt
            ORDER BY cnt DESC
            """
        )
        titles = [{"name": r["t"], "count": r["cnt"]} for r in result]

    if dry_run:
        return {"dry_run": True, "title_count": len(titles), "sample": titles[:10]}

    # 写入
    created_jt = 0
    created_rel = 0
    with driver.session(database=database) as session:
        # 创建唯一约束
        try:
            session.run(
                "CREATE CONSTRAINT job_title_name IF NOT EXISTS "
                "FOR (jt:JobTitle) REQUIRE jt.name IS UNIQUE"
            )
        except Exception:
            pass  # 约束已存在

        for t in titles:
            session.run(
                """
                MERGE (jt:JobTitle {name: $name})
                SET jt.job_count = $cnt
                """,
                name=t["name"],
                cnt=t["count"],
            )
            created_jt += 1

        # HAS_TITLE 关系
        session.run(
            """
            MATCH (j:Job), (jt:JobTitle)
            WHERE coalesce(trim(j.title), '') = jt.name
              AND NOT (j)-[:HAS_TITLE]->(jt)
            MERGE (j)-[:HAS_TITLE]->(jt)
            """
        )
        result = session.run(
            "MATCH ()-[r:HAS_TITLE]->() RETURN count(r) AS cnt"
        )
        created_rel = int(result.single()["cnt"])

    return {
        "dry_run": False,
        "title_count": len(titles),
        "created_jobtitle_nodes": created_jt,
        "has_title_relationships": created_rel,
    }


# ============================================================
# 2. 晋升路径生成
# ============================================================

def generate_promotion_paths(*, dry_run: bool = False) -> Dict[str, Any]:
    """LLM 推断 JobTitle 间的晋升路径。"""
    driver, database = _get_driver()
    titles = fetch_all_job_titles(driver, database)
    valid_titles = {str(t).strip() for t in titles if str(t).strip()}
    if len(titles) < 2:
        return {"error": "JobTitle 数量不足（需要至少 2 个）", "dry_run": dry_run}

    # 分批发送给 LLM（每批 30 个标题）
    batch_size = 30
    all_paths: List[Dict[str, Any]] = []

    for start in range(0, len(titles), batch_size):
        batch = titles[start : start + batch_size]
        payload = json.dumps({"job_titles": batch}, ensure_ascii=False)
        result = _call_llm_json(
            PROMOTION_PATH_SYSTEM,
            payload,
            label=f"晋升路径 batch {start // batch_size + 1}",
        )
        paths = result.get("paths", [])
        if isinstance(paths, list):
            all_paths.extend([p for p in paths if isinstance(p, dict)])

    if dry_run:
        return {
            "dry_run": True,
            "titles_scanned": len(titles),
            "candidate_paths": len(all_paths),
            "preview": all_paths[:20],
        }

    # 写入 Neo4j
    created = 0
    with driver.session(database=database) as session:
        try:
            session.run(
                "CREATE CONSTRAINT job_promotion_id IF NOT EXISTS "
                "FOR (p:JobPromotion) REQUIRE p.promotion_id IS UNIQUE"
            )
        except Exception:
            pass

        for p in all_paths:
            from_t = (p.get("from_title") or "").strip()
            to_t = (p.get("to_title") or "").strip()
            if (
                not from_t
                or not to_t
                or from_t == to_t
                or from_t not in valid_titles
                or to_t not in valid_titles
            ):
                continue
            confidence = _parse_confidence(p.get("confidence"))
            if confidence < 0.5:
                continue
            pid = _promotion_id(from_t, to_t)
            session.run(
                """
                MATCH (jt:JobTitle {name: $from_title})
                MERGE (pr:JobPromotion {promotion_id: $pid})
                SET pr.name = $pid,
                    pr.from_title = $from_title,
                    pr.to_title = $to_title,
                    pr.title = $promotion_name,
                    pr.stage1 = $stage1,
                    pr.stage2 = $stage2,
                    pr.stage3 = $stage3,
                    pr.stage3_job_title = $stage3_job,
                    pr.confidence = $confidence,
                    pr.rationale = $rationale
                WITH pr, jt
                MERGE (pr)-[:FOR_JOB_TITLE]->(jt)
                """,
                pid=pid,
                from_title=from_t,
                to_title=to_t,
                promotion_name=str(p.get("promotion_name", "")),
                stage1=str(p.get("stage1", "")),
                stage2=str(p.get("stage2", "")),
                stage3=str(p.get("stage3", "")),
                stage3_job=str(p.get("stage3_job_title", "")),
                confidence=confidence,
                rationale=str(p.get("rationale", "")),
            )
            created += 1

    return {
        "dry_run": False,
        "titles_scanned": len(titles),
        "candidate_paths": len(all_paths),
        "created_promotions": created,
    }


# ============================================================
# 3. 换岗关系生成
# ============================================================

def generate_lateral_transfers(*, dry_run: bool = False) -> Dict[str, Any]:
    """LLM 推断 JobTitle 间的横向转岗关系。"""
    driver, database = _get_driver()
    titles = fetch_all_job_titles(driver, database)
    if len(titles) < 2:
        return {"error": "JobTitle 数量不足", "dry_run": dry_run}

    # 取 top 50 高频岗位做配对
    top_titles = titles[:50]
    all_pairs: List[Dict[str, Any]] = []

    for i in range(0, len(top_titles), 15):
        batch = top_titles[i : i + 15]
        payload = json.dumps(
            {"job_titles": batch, "task": "评估这些岗位两两之间的横向转岗可行性"},
            ensure_ascii=False,
        )
        result = _call_llm_json(
            LATERAL_SYSTEM,
            payload,
            label=f"换岗关系 batch {i // 15 + 1}",
        )
        pairs = result.get("pairs", [])
        if isinstance(pairs, list):
            all_pairs.extend([p for p in pairs if isinstance(p, dict)])

    if dry_run:
        return {
            "dry_run": True,
            "titles_considered": len(top_titles),
            "candidate_pairs": len(all_pairs),
            "preview": all_pairs[:20],
        }

    # 写入 Neo4j
    created = 0
    with driver.session(database=database) as session:
        # 清旧边
        session.run("MATCH ()-[r:SIMILAR_FOR_LATERAL]->() DELETE r")

        for rank, p in enumerate(all_pairs, 1):
            frm = (p.get("from") or "").strip()
            to = (p.get("to") or "").strip()
            if not frm or not to or frm == to:
                continue
            session.run(
                """
                MATCH (a:JobTitle {name: $from})
                MATCH (b:JobTitle {name: $to})
                MERGE (a)-[r:SIMILAR_FOR_LATERAL]->(b)
                SET r.score = $score,
                    r.rank = $rank,
                    r.track_from = $track_from,
                    r.track_to = $track_to,
                    r.cap_similarity = $cap_sim,
                    r.same_track = $same_track,
                    r.rationale = $rationale
                """,
                **{
                    "from": frm, "to": to,
                    "score": float(p.get("score", 0)),
                    "rank": rank,
                    "track_from": str(p.get("track_from", "")),
                    "track_to": str(p.get("track_to", "")),
                    "cap_sim": float(p.get("cap_similarity", 0)),
                    "same_track": bool(p.get("same_track", False)),
                    "rationale": str(p.get("rationale", "")),
                },
            )
            created += 1

    return {
        "dry_run": False,
        "titles_considered": len(top_titles),
        "candidate_pairs": len(all_pairs),
        "created_relationships": created,
    }


# ============================================================
# 4. 学习资源生成
# ============================================================

def generate_learning_resources(*, dry_run: bool = False) -> Dict[str, Any]:
    """LLM 为 JobTitle 推荐学习资源。"""
    driver, database = _get_driver()
    titles_with_counts = fetch_all_job_titles_with_counts(driver, database)

    # 只处理有足够岗位数的标题（>=2），取前 30 个
    eligible = [t for t in titles_with_counts if t["count"] >= 2][:30]
    all_resources: List[Dict[str, Any]] = []

    for t in eligible:
        user_content = json.dumps(
            {"job_title": t["name"], "job_count": t["count"]},
            ensure_ascii=False,
        )
        result = _call_llm_json(
            LEARNING_RESOURCE_SYSTEM,
            user_content,
            label=f"学习资源 {t['name']}",
        )
        resources = result.get("resources", [])
        if isinstance(resources, list):
            for r in resources:
                if isinstance(r, dict):
                    r["_for_title"] = t["name"]
            all_resources.extend([r for r in resources if isinstance(r, dict)])

    if dry_run:
        return {
            "dry_run": True,
            "titles_processed": len(eligible),
            "candidate_resources": len(all_resources),
            "preview": [{"title": r["_for_title"], "name": r.get("resource_name", "")} for r in all_resources[:20]],
        }

    # 写入 Neo4j
    created = 0
    with driver.session(database=database) as session:
        try:
            session.run(
                "CREATE CONSTRAINT learning_resource_id IF NOT EXISTS "
                "FOR (lr:LearningResource) REQUIRE lr.resource_id IS UNIQUE"
            )
        except Exception:
            pass

        for r in all_resources:
            rid = f"lr_{r['_for_title']}_{r.get('resource_name', '')}".replace(" ", "_").replace("/", "_")[:191]
            session.run(
                """
                MERGE (lr:LearningResource {resource_id: $rid})
                SET lr.resource_name = $name,
                    lr.resource_desc = $desc,
                    lr.resource_type = $type,
                    lr.difficulty = $diff,
                    lr.skill_tag = $skill,
                    lr.source = 'llm_generated'
                WITH lr
                MATCH (jt:JobTitle {name: $title})
                MERGE (lr)-[:FOR_JOB_TITLE]->(jt)
                """,
                rid=rid,
                name=str(r.get("resource_name", "")),
                desc=str(r.get("resource_desc", "")),
                type=str(r.get("resource_type", "")),
                diff=str(r.get("difficulty", "")),
                skill=str(r.get("skill_tag", "")),
                title=r["_for_title"],
            )
            created += 1

    return {
        "dry_run": False,
        "titles_processed": len(eligible),
        "candidate_resources": len(all_resources),
        "created_resources": created,
    }


# ============================================================
# 5. 竞赛生成
# ============================================================

def generate_competitions(*, dry_run: bool = False) -> Dict[str, Any]:
    """LLM 为 JobTitle 推荐竞赛。"""
    driver, database = _get_driver()
    titles_with_counts = fetch_all_job_titles_with_counts(driver, database)
    eligible = [t for t in titles_with_counts if t["count"] >= 2][:30]
    all_competitions: List[Dict[str, Any]] = []

    for t in eligible:
        user_content = json.dumps(
            {"job_title": t["name"], "job_count": t["count"]},
            ensure_ascii=False,
        )
        result = _call_llm_json(
            COMPETITION_SYSTEM,
            user_content,
            label=f"竞赛 {t['name']}",
        )
        comps = result.get("competitions", [])
        if isinstance(comps, list):
            for c in comps:
                if isinstance(c, dict):
                    c["_for_title"] = t["name"]
            all_competitions.extend([c for c in comps if isinstance(c, dict)])

    if dry_run:
        return {
            "dry_run": True,
            "titles_processed": len(eligible),
            "candidate_competitions": len(all_competitions),
            "preview": [{"title": c["_for_title"], "name": c.get("competition_name", "")} for c in all_competitions[:20]],
        }

    created = 0
    with driver.session(database=database) as session:
        try:
            session.run(
                "CREATE CONSTRAINT competition_id IF NOT EXISTS "
                "FOR (c:Competition) REQUIRE c.competition_id IS UNIQUE"
            )
        except Exception:
            pass

        for c in all_competitions:
            cid = f"comp_{c['_for_title']}_{c.get('competition_name', '')}".replace(" ", "_").replace("/", "_")[:191]
            session.run(
                """
                MERGE (comp:Competition {competition_id: $cid})
                SET comp.competition_name = $name,
                    comp.competition_desc = $desc,
                    comp.competition_type = $type,
                    comp.organizer = $organizer,
                    comp.target_audience = $audience,
                    comp.team_mode = $team,
                    comp.frequency = $freq,
                    comp.difficulty = $diff,
                    comp.cap_tags = $cap_tags,
                    comp.skill_tags = $skill_tags,
                    comp.award_level = $award
                WITH comp
                MATCH (jt:JobTitle {name: $title})
                MERGE (comp)-[:FOR_JOB_TITLE]->(jt)
                """,
                cid=cid,
                name=str(c.get("competition_name", "")),
                desc=str(c.get("competition_desc", "")),
                type=str(c.get("competition_type", "")),
                organizer=str(c.get("organizer", "")),
                audience=str(c.get("target_audience", "")),
                team=str(c.get("team_mode", "")),
                freq=str(c.get("frequency", "")),
                diff=str(c.get("difficulty", "")),
                cap_tags=str(c.get("cap_tags", "")),
                skill_tags=str(c.get("skill_tags", "")),
                award=str(c.get("award_level", "")),
                title=c["_for_title"],
            )
            created += 1

    return {
        "dry_run": False,
        "titles_processed": len(eligible),
        "candidate_competitions": len(all_competitions),
        "created_competitions": created,
    }
