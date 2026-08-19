"""Atomically apply a reviewed graph task change set."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.domains.graph.constants import SOFT_SKILL_DIMS, normalize_text, parse_experience_years
from app.domains.graph.sync_service import _generated_id, _promotion_id
from app.domains.graph.task_registry import TASK_HANDLERS
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings
from app.infrastructure.salary import neo4j_salary_properties


def _apply_job(tx, change: dict[str, Any], run_id: str) -> None:
    source_id = change["source_id"]
    for item in change.get("jobs", []):
        row, ai, key = item["row"], item.get("ai", {}), item["job_key"]
        sal = neo4j_salary_properties(normalize_text(row.get("salary")))
        capability = item.get("capability", {})
        tx.run(
            """MERGE (j:Job {job_key:$key}) SET j += $props,
               j.import_fingerprint=$fingerprint,j.import_source_id=$source,
               j.last_seen_run_id=$run,j.import_managed=true,j.last_imported_at=datetime()""",
            key=key, fingerprint=item["fingerprint"], source=source_id, run=run_id,
            props={**capability, "title": normalize_text(row.get("name")), "company": normalize_text(row.get("company")),
                   "location": normalize_text(row.get("location")), "salary": sal["salary"],
                   "salary_norm": sal["salary_norm"], "salary_negotiable": sal["salary_negotiable"],
                   "salary_parse_version": sal["salary_parse_version"], "salary_monthly_min": sal.get("salary_monthly_min"),
                   "salary_monthly_max": sal.get("salary_monthly_max"), "salary_bonus_months": sal.get("salary_bonus_months"),
                   "industry": normalize_text(row.get("industry")), "company_size": normalize_text(row.get("company_size")),
                   "company_type": normalize_text(row.get("company_type")), "job_code": normalize_text(row.get("job_code")),
                   "updated_date": normalize_text(row.get("updated_date")), "demand": normalize_text(row.get("demand")),
                   "source_url": normalize_text(row.get("source_url")), "company_detail": normalize_text(row.get("company_detail")),
                   "experience_text": normalize_text(ai.get("experience_req", "未知")),
                   "experience_years": parse_experience_years(normalize_text(ai.get("experience_req", "未知"))),
                   "internship_req": normalize_text(ai.get("internship_req", "未知"))},
        )
        tx.run("MATCH (j:Job {job_key:$key})-[r:REQUIRES|BELONGS_TO]->(n) WHERE n:Skill OR n:Certificate OR n:SoftSkill OR n:CareerLevel OR n:Company DELETE r", key=key)
        tx.run("MERGE (c:Company {name:$name}) WITH c MATCH (j:Job {job_key:$key}) MERGE (j)-[:BELONGS_TO]->(c)", name=normalize_text(row.get("company")), key=key)
        for skill in sorted({normalize_text(x) for x in ai.get("hard_skills", []) if normalize_text(x)}):
            tx.run("MERGE (s:Skill {name:$name}) WITH s MATCH (j:Job {job_key:$key}) MERGE (j)-[:REQUIRES]->(s)", name=skill, key=key)
        for cert in sorted({normalize_text(x) for x in ai.get("certificates", []) if normalize_text(x)}):
            tx.run("MERGE (c:Certificate {name:$name}) WITH c MATCH (j:Job {job_key:$key}) MERGE (j)-[:REQUIRES]->(c)", name=cert, key=key)
        soft = ai.get("soft_skills", {}) if isinstance(ai.get("soft_skills", {}), dict) else {}
        for dim in SOFT_SKILL_DIMS:
            tx.run("MERGE (s:SoftSkill {name:$name}) WITH s MATCH (j:Job {job_key:$key}) MERGE (j)-[r:REQUIRES]->(s) SET r.level=$level", name=dim, level=normalize_text(soft.get(dim, "未知")) or "未知", key=key)
        level = normalize_text(ai.get("experience_req", "未知")) or "未知"
        tx.run("MERGE (c:CareerLevel {name:$name}) WITH c MATCH (j:Job {job_key:$key}) MERGE (j)-[:BELONGS_TO]->(c)", name=level, key=key)

    tx.run("UNWIND $keys AS key MATCH (j:Job {job_key:key}) SET j.last_seen_run_id=$run,j.import_source_id=$source,j.import_managed=true", keys=change.get("input_keys", []), run=run_id, source=source_id)
    if change.get("mode") == "snapshot":
        tx.run("MATCH (j:Job {import_source_id:$source,import_managed:true}) WHERE coalesce(j.last_seen_run_id,'')<>$run DETACH DELETE j", source=source_id, run=run_id)

    tx.run("MATCH (j:Job) WITH trim(j.title) AS name,count(j) AS count,count(DISTINCT j.company) AS companies,count(DISTINCT coalesce(j.job_code,'')) AS codes WHERE name<>'' MERGE (jt:JobTitle {name:name}) SET jt.job_count=count,jt.company_count=companies,jt.job_code_count=codes,jt.generation_run_id=$run,jt.updated_at=datetime()", run=run_id)
    tx.run("MATCH (jt:JobTitle) WHERE coalesce(jt.generation_run_id,'')<>$run DETACH DELETE jt", run=run_id)
    tx.run("MATCH (j:Job)-[r:HAS_TITLE]->(jt:JobTitle) WHERE coalesce(trim(j.title),'')<>jt.name DELETE r")
    tx.run("MATCH (j:Job),(jt:JobTitle) WHERE coalesce(trim(j.title),'')=jt.name MERGE (j)-[:HAS_TITLE]->(jt)")

    source = "graph_task_llm"
    for p in change.get("promotions", []):
        frm, to = p["from_title"], p["to_title"]
        tx.run("""MATCH (jt:JobTitle {name:$frm}) OPTIONAL MATCH (existing:JobPromotion {promotion_id:$id})
          WITH jt,existing WHERE existing IS NULL OR coalesce(existing.generation_source,'') <> 'curated'
          MERGE (pr:JobPromotion {promotion_id:$id})
          SET pr.from_title=$frm,pr.to_title=$to,pr.title=$title,pr.stage1=$s1,pr.stage2=$s2,
          pr.stage3=$s3,pr.stage3_job_title=$s3job,pr.confidence=$confidence,pr.rationale=$rationale,
          pr.generation_source=$source,pr.generation_run_id=$run,pr.updated_at=datetime()
          WITH jt,pr MERGE (pr)-[:FOR_JOB_TITLE]->(jt)""", id=_promotion_id(frm, to), frm=frm, to=to,
          title=str(p.get("promotion_name", "")), s1=str(p.get("stage1", "")), s2=str(p.get("stage2", "")),
          s3=str(p.get("stage3", "")), s3job=str(p.get("stage3_job_title", "")), confidence=float(p.get("confidence", 0)),
          rationale=str(p.get("rationale", "")), source=source, run=run_id)
    if change.get("version", 1) == 1 or change.get("replace_auto_promotions", True):
        tx.run("MATCH (p:JobPromotion {generation_source:$source}) WHERE coalesce(p.generation_run_id,'')<>$run DETACH DELETE p", source=source, run=run_id)
    for rank, p in enumerate(change.get("lateral", []), 1):
        tx.run("""MATCH (a:JobTitle {name:$frm}),(b:JobTitle {name:$to})
          OPTIONAL MATCH (a)-[existing:SIMILAR_FOR_LATERAL]->(b)
          WITH a,b,existing WHERE existing IS NULL OR coalesce(existing.generation_source,'') <> 'curated'
          MERGE (a)-[r:SIMILAR_FOR_LATERAL]->(b)
          SET r.score=$score,r.rank=$rank,r.track_from=$tf,r.track_to=$tt,r.cap_similarity=$cap,
          r.same_track=$same,r.rationale=$why,r.generation_source=$source,r.generation_run_id=$run,r.updated_at=datetime()""",
          frm=p["from"],to=p["to"],score=float(p.get("score",0)),rank=rank,tf=str(p.get("track_from","")),tt=str(p.get("track_to","")),
          cap=float(p.get("cap_similarity",0)),same=bool(p.get("same_track",False)),why=str(p.get("rationale","")),source=source,run=run_id)
    if change.get("version", 1) == 1 or change.get("replace_auto_lateral", True):
        tx.run("MATCH ()-[r:SIMILAR_FOR_LATERAL {generation_source:$source}]->() WHERE coalesce(r.generation_run_id,'')<>$run DELETE r", source=source, run=run_id)


def _apply_resources(tx, change: dict[str, Any], run_id: str) -> None:
    source = change["source_id"]; ids = []
    for row in change["items"]:
        rid = row["resource_id"]; ids.append(rid)
        tx.run("""MERGE (r:LearningResource {resource_id:$id}) SET r += $props,
          r.import_source_id=$source,r.source_id=$source,r.generation_source='curated',r.source_priority=100,
          r.import_run_id=$run,r.last_task_run_id=$run,r.import_managed=true,r.updated_at=datetime()
          WITH r OPTIONAL MATCH (r)-[old:FOR_JOB_TITLE]->(:JobTitle) DELETE old""", id=rid, source=source, run=run_id,
          props={k:v for k,v in row.items() if k != "job_titles"})
        tx.run("UNWIND $titles AS title MATCH (r:LearningResource {resource_id:$id}),(jt:JobTitle {name:title}) MERGE (r)-[rel:FOR_JOB_TITLE]->(jt) SET rel.source_id=$source,rel.generation_source='curated',rel.source_priority=100", titles=row["job_titles"], id=rid, source=source)
    if change.get("mode") == "snapshot": tx.run("MATCH (r:LearningResource {import_source_id:$source,import_managed:true}) WHERE NOT r.resource_id IN $ids DETACH DELETE r", source=source, ids=ids)


def _apply_competitions(tx, change: dict[str, Any], run_id: str) -> None:
    source = change["source_id"]; ids = []
    for row in change["items"]:
        cid = row["competition_id"]; ids.append(cid)
        tx.run("""MERGE (c:Competition {competition_id:$id}) SET c += $props,
          c.import_source_id=$source,c.source_id=$source,c.generation_source='curated',c.source_priority=100,
          c.import_run_id=$run,c.last_task_run_id=$run,c.import_managed=true,c.updated_at=datetime()
          WITH c OPTIONAL MATCH (c)-[old:FOR_JOB_TITLE]->(:JobTitle) DELETE old""", id=cid, source=source, run=run_id,
          props={k:v for k,v in row.items() if k != "job_titles"})
        tx.run("UNWIND $titles AS title MATCH (c:Competition {competition_id:$id}),(jt:JobTitle {name:title}) MERGE (c)-[rel:FOR_JOB_TITLE]->(jt) SET rel.source_id=$source,rel.generation_source='curated',rel.source_priority=100", titles=row["job_titles"], id=cid, source=source)
    if change.get("mode") == "snapshot": tx.run("MATCH (c:Competition {import_source_id:$source,import_managed:true}) WHERE NOT c.competition_id IN $ids DETACH DELETE c", source=source, ids=ids)


def _apply_capabilities(tx, change: dict[str, Any], _run_id: str) -> None:
    for item in change.get("jobs", []):
        tx.run("MATCH (j:Job {job_key:$key}) SET j += $props,j.cap_updated_at=datetime()", key=item["job_key"], props=item["capability"])


def _apply_workstyles(tx, change: dict[str, Any], run_id: str) -> None:
    for item in change.get("items", []):
        if item.get("target_type") == "job":
            query = "MATCH (n:Job {job_key:$id}) SET n += $props,n.workstyle_updated_at=datetime(),n.workstyle_last_task_run_id=$run"
        else:
            query = "MATCH (n:JobTitle {name:$id}) SET n += $props,n.workstyle_updated_at=datetime(),n.workstyle_last_task_run_id=$run"
        tx.run(query, id=item["target_id"], props=item["properties"], run=run_id)


def _apply_promotions(tx, change: dict[str, Any], run_id: str) -> None:
    source = change.get("source_id") or "curated-promotions"; ids = []
    for row in change.get("items", []):
        pid = row["promotion_id"]; ids.append(pid)
        tx.run("""MERGE (p:JobPromotion {promotion_id:$id}) SET p += $props,
          p.generation_source='curated',p.source_id=$source,p.source_priority=100,
          p.last_task_run_id=$run,p.updated_at=datetime()
          WITH p OPTIONAL MATCH (p)-[old:FOR_JOB_TITLE]->(:JobTitle) DELETE old
          WITH p MATCH (jt:JobTitle {name:$title}) MERGE (p)-[:FOR_JOB_TITLE]->(jt)""",
          id=pid, props=row, source=source, run=run_id, title=row["job_title"])
    if change.get("mode") == "snapshot":
        tx.run("MATCH (p:JobPromotion {generation_source:'curated',source_id:$source}) WHERE NOT p.promotion_id IN $ids DETACH DELETE p", source=source, ids=ids)


def _apply_lateral_import(tx, change: dict[str, Any], run_id: str) -> None:
    source = change.get("source_id") or "curated-lateral"; pairs = []
    for row in change.get("items", []):
        frm, to = row["from_job_title"], row["to_job_title"]; pairs.append(f"{frm}\u0000{to}")
        props = {k: v for k, v in row.items() if k not in {"from_job_title", "to_job_title"}}
        tx.run("""MATCH (a:JobTitle {name:$from_title}),(b:JobTitle {name:$to_title})
          MERGE (a)-[r:SIMILAR_FOR_LATERAL]->(b) SET r += $props,r.generation_source='curated',
          r.source_id=$source,r.source_priority=100,r.last_task_run_id=$run,r.updated_at=datetime()""",
          from_title=frm, to_title=to, props=props, source=source, run=run_id)
    if change.get("mode") == "snapshot":
        tx.run("MATCH (a:JobTitle)-[r:SIMILAR_FOR_LATERAL {generation_source:'curated',source_id:$source}]->(b:JobTitle) WHERE NOT (a.name+'\\u0000'+b.name) IN $pairs DELETE r", source=source, pairs=pairs)


def _apply_recommendations(tx, change: dict[str, Any], run_id: str) -> None:
    source = change.get("source_id") or "curated-promotion-recommendations"
    resource_keys, competition_keys = [], []
    for row in change.get("resource_recommendations", []):
        key = f"{row['promotion_id']}\u0000{row['resource_id']}"; resource_keys.append(key)
        props = {k: v for k, v in row.items() if k not in {"promotion_id", "resource_id"}}
        tx.run("""MATCH (p:JobPromotion {promotion_id:$promotion_id}),(r:LearningResource {resource_id:$resource_id})
          MERGE (p)-[rel:RECOMMENDS_RESOURCE]->(r) SET rel += $props,rel.generation_source='curated',
          rel.source_id=$source,rel.source_priority=100,rel.last_task_run_id=$run,rel.updated_at=datetime()""",
          promotion_id=row["promotion_id"], resource_id=row["resource_id"], props=props, source=source, run=run_id)
    for row in change.get("competition_recommendations", []):
        key = f"{row['promotion_id']}\u0000{row['competition_id']}"; competition_keys.append(key)
        props = {k: v for k, v in row.items() if k not in {"promotion_id", "competition_id"}}
        tx.run("""MATCH (p:JobPromotion {promotion_id:$promotion_id}),(c:Competition {competition_id:$competition_id})
          MERGE (p)-[rel:RECOMMENDS_COMPETITION]->(c) SET rel += $props,rel.generation_source='curated',
          rel.source_id=$source,rel.source_priority=100,rel.last_task_run_id=$run,rel.updated_at=datetime()""",
          promotion_id=row["promotion_id"], competition_id=row["competition_id"], props=props, source=source, run=run_id)
    if change.get("mode") == "snapshot":
        tx.run("MATCH (p:JobPromotion)-[r:RECOMMENDS_RESOURCE {source_id:$source}]->(x:LearningResource) WHERE NOT (p.promotion_id+'\\u0000'+x.resource_id) IN $keys DELETE r", source=source, keys=resource_keys)
        tx.run("MATCH (p:JobPromotion)-[r:RECOMMENDS_COMPETITION {source_id:$source}]->(x:Competition) WHERE NOT (p.promotion_id+'\\u0000'+x.competition_id) IN $keys DELETE r", source=source, keys=competition_keys)


def _apply_salary(tx, change: dict[str, Any], _run_id: str) -> None:
    for item in change.get("jobs", []):
        tx.run("MATCH (j:Job {job_key:$key}) SET j += $props", key=item["job_key"], props=item["new"])


def _apply_inferred_cleanup(tx, change: dict[str, Any], _run_id: str) -> None:
    keys = [x["job_key"] for x in change.get("jobs", []) if x.get("job_key")]
    titles = [x["name"] for x in change.get("job_titles", []) if x.get("name")]
    tx.run("UNWIND $keys AS key MATCH (j:Job {job_key:key,source:'inferred'}) DETACH DELETE j", keys=keys)
    tx.run("MATCH (jt:JobTitle) OPTIONAL MATCH (j:Job)-[:HAS_TITLE]->(jt) WITH jt,count(j) AS actual SET jt.job_count=actual")
    tx.run("UNWIND $titles AS name MATCH (jt:JobTitle {name:name}) WHERE coalesce(jt.job_count,0)<2 DETACH DELETE jt", titles=titles)


def is_task_applied(task_uuid: str) -> bool:
    uri, user, password, database = neo4j_settings()
    if not password: return False
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        row = session.run("MATCH (c:GraphTaskCommit {task_uuid:$uuid}) RETURN count(c) AS total", uuid=task_uuid).single()
        return bool(row and int(row["total"]) > 0)


def _ensure_constraints(driver, database: str) -> None:
    constraints = (
        ("job_key", "Job", "job_key"), ("company_name", "Company", "name"),
        ("skill_name", "Skill", "name"), ("certificate_name", "Certificate", "name"),
        ("soft_skill_name", "SoftSkill", "name"), ("career_level_name", "CareerLevel", "name"),
        ("job_title_name", "JobTitle", "name"), ("job_promotion_id", "JobPromotion", "promotion_id"),
        ("learning_resource_id", "LearningResource", "resource_id"),
        ("competition_id", "Competition", "competition_id"),
        ("graph_task_commit_uuid", "GraphTaskCommit", "task_uuid"),
    )
    with driver.session(database=database) as session:
        for name, label, prop in constraints:
            session.run(f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")


def apply_change_set(change: dict[str, Any], *, task_uuid: str, change_sha256: str) -> dict[str, Any]:
    uri, user, password, database = neo4j_settings()
    if not password: raise RuntimeError("未配置 NEO4J_PASSWORD")
    driver = neo4j_driver(uri, user, password); run_id = uuid4().hex
    if is_task_applied(task_uuid): return {"run_id": run_id, "kind": change.get("kind"), "already_applied": True}
    _ensure_constraints(driver, database)
    def apply(tx):
        kind = change.get("kind")
        handlers = {
            "job_import": _apply_job,
            "job_capability_evaluation": _apply_capabilities,
            "job_capability_result_import": _apply_capabilities,
            "job_workstyle_import": _apply_workstyles,
            "job_workstyle_evaluation": _apply_workstyles,
            "learning_resource_import": _apply_resources,
            "competition_import": _apply_competitions,
            "job_promotion_import": _apply_promotions,
            "job_lateral_import": _apply_lateral_import,
            "promotion_recommendation_import": _apply_recommendations,
            "salary_normalization": _apply_salary,
            "inferred_job_cleanup": _apply_inferred_cleanup,
        }
        try:
            handler_key = TASK_HANDLERS[str(kind)][1]
            handler = handlers[str(handler_key)]
        except KeyError as exc: raise ValueError(f"未知变更集类型: {kind}") from exc
        handler(tx, change, run_id)
        tx.run("CREATE (c:GraphTaskCommit {task_uuid:$uuid,change_sha256:$sha,run_id:$run,applied_at:datetime()})", uuid=task_uuid, sha=change_sha256, run=run_id)
    with driver.session(database=database) as session: session.execute_write(apply)
    return {"run_id": run_id, "kind": change.get("kind")}
