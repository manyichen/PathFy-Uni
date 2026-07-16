"""Atomically apply reviewed graph task chunks through the sole production writer."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any
from uuid import uuid4

from app.domains.graph.constants import SOFT_SKILL_DIMS, normalize_text, parse_experience_years
from app.domains.graph.sync_service import _promotion_id
from app.domains.graph.task_registry import TASK_HANDLERS
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings
from app.infrastructure.salary import neo4j_salary_properties

GroupLoader = Callable[[str], Iterable[list[Any]]]


def _version(change: dict[str, Any]) -> int:
    return int(change.get("version", 1) or 1)


def _chunks(change: dict[str, Any], group: str, loader: GroupLoader | None) -> Iterator[list[Any]]:
    if loader is not None:
        yield from loader(group)
        return
    if "." in group:
        prefix, nested = group.split(".", 1)
        key = {"delete": "delete_manifest", "retained": "retained_manifest"}.get(prefix)
        container = change.get(key, {}) if key else {}
        rows = container.get(nested, []) if isinstance(container, dict) else []
    else:
        rows = change.get(group, [])
    if isinstance(rows, list) and rows:
        yield rows


def _job_write_rows(items: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        row, ai = item["row"], item.get("ai", {})
        salary = neo4j_salary_properties(normalize_text(row.get("salary")))
        soft = ai.get("soft_skills", {}) if isinstance(ai.get("soft_skills"), dict) else {}
        props = {
            **item.get("capability", {}),
            "title": normalize_text(row.get("name")),
            "company": normalize_text(row.get("company")),
            "location": normalize_text(row.get("location")),
            "salary": salary["salary"],
            "salary_norm": salary["salary_norm"],
            "salary_negotiable": salary["salary_negotiable"],
            "salary_parse_version": salary["salary_parse_version"],
            "salary_monthly_min": salary.get("salary_monthly_min"),
            "salary_monthly_max": salary.get("salary_monthly_max"),
            "salary_bonus_months": salary.get("salary_bonus_months"),
            "industry": normalize_text(row.get("industry")),
            "company_size": normalize_text(row.get("company_size")),
            "company_type": normalize_text(row.get("company_type")),
            "job_code": normalize_text(row.get("job_code")),
            "updated_date": normalize_text(row.get("updated_date")),
            "demand": normalize_text(row.get("demand")),
            "source_url": normalize_text(row.get("source_url")),
            "company_detail": normalize_text(row.get("company_detail")),
            "experience_text": normalize_text(ai.get("experience_req", "未知")),
            "experience_years": parse_experience_years(normalize_text(ai.get("experience_req", "未知"))),
            "internship_req": normalize_text(ai.get("internship_req", "未知")),
        }
        result.append({
            "job_key": item["job_key"],
            "fingerprint": item["fingerprint"],
            "props": props,
            "company": props["company"],
            "hard_skills": sorted({normalize_text(value) for value in ai.get("hard_skills", []) if normalize_text(value)}),
            "certificates": sorted({normalize_text(value) for value in ai.get("certificates", []) if normalize_text(value)}),
            "soft_skills": [{"name": dim, "level": normalize_text(soft.get(dim, "未知")) or "未知"} for dim in SOFT_SKILL_DIMS],
            "career_level": normalize_text(ai.get("experience_req", "未知")) or "未知",
        })
    return result


def _apply_job(tx, change: dict[str, Any], run_id: str, loader: GroupLoader | None = None) -> None:
    source_id = change["source_id"]
    for chunk in _chunks(change, "jobs", loader):
        tx.run(
            """UNWIND $rows AS item
            MERGE (j:Job {job_key:item.job_key}) SET j += item.props,
              j.import_fingerprint=item.fingerprint,j.import_source_id=$source,
              j.last_seen_run_id=$run,j.import_managed=true,j.last_imported_at=datetime()
            WITH j,item OPTIONAL MATCH (j)-[old:REQUIRES|BELONGS_TO]->(n)
              WHERE n:Skill OR n:Certificate OR n:SoftSkill OR n:CareerLevel OR n:Company
            DELETE old
            WITH j,item MERGE (company:Company {name:item.company}) MERGE (j)-[:BELONGS_TO]->(company)
            FOREACH (name IN item.hard_skills | MERGE (skill:Skill {name:name}) MERGE (j)-[:REQUIRES]->(skill))
            FOREACH (name IN item.certificates | MERGE (cert:Certificate {name:name}) MERGE (j)-[:REQUIRES]->(cert))
            FOREACH (soft IN item.soft_skills | MERGE (node:SoftSkill {name:soft.name}) MERGE (j)-[rel:REQUIRES]->(node) SET rel.level=soft.level)
            MERGE (level:CareerLevel {name:item.career_level}) MERGE (j)-[:BELONGS_TO]->(level)""",
            rows=_job_write_rows(chunk), source=source_id, run=run_id,
        )
    for chunk in _chunks(change, "input_keys", loader):
        tx.run(
            "UNWIND $keys AS key MATCH (j:Job {job_key:key}) SET j.last_seen_run_id=$run,j.import_source_id=$source,j.import_managed=true",
            keys=chunk, run=run_id, source=source_id,
        )
    if _version(change) == 1 and change.get("mode") == "snapshot":
        tx.run("MATCH (j:Job {import_source_id:$source,import_managed:true}) WHERE coalesce(j.last_seen_run_id,'')<>$run DETACH DELETE j", source=source_id, run=run_id)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.jobs", loader):
            tx.run("UNWIND $rows AS item MATCH (j:Job {job_key:item.job_key}) WHERE j.import_source_id=item.source_id DETACH DELETE j", rows=chunk)

    tx.run("MATCH (j:Job) WITH DISTINCT trim(j.title) AS name WHERE name<>'' MERGE (jt:JobTitle {name:name}) SET jt.generation_run_id=$run,jt.updated_at=datetime()", run=run_id)
    tx.run("MATCH (j:Job)-[r:HAS_TITLE]->(jt:JobTitle) WHERE coalesce(trim(j.title),'')<>jt.name DELETE r")
    tx.run("MATCH (j:Job),(jt:JobTitle) WHERE coalesce(trim(j.title),'')=jt.name MERGE (j)-[:HAS_TITLE]->(jt)")
    tx.run("""MATCH (jt:JobTitle) OPTIONAL MATCH (j:Job)-[:HAS_TITLE]->(jt)
      WITH jt,count(j) AS jobs,count(DISTINCT j.company) AS companies,count(DISTINCT j.job_code) AS codes
      SET jt.job_count=jobs,jt.company_count=companies,jt.job_code_count=codes,jt.updated_at=datetime()""")
    if _version(change) == 1:
        tx.run("MATCH (jt:JobTitle) WHERE coalesce(jt.generation_run_id,'')<>$run DETACH DELETE jt", run=run_id)
    else:
        for chunk in _chunks(change, "delete.job_titles", loader):
            tx.run("""UNWIND $rows AS item MATCH (jt:JobTitle {name:item.name})
              WHERE NOT EXISTS { MATCH (jt)-[r]-(n)
                WHERE coalesce(r.generation_source,'')='curated' OR coalesce(n.generation_source,'')='curated' }
              DETACH DELETE jt""", rows=chunk)

    source = "graph_task_llm"
    for chunk in _chunks(change, "promotions", loader):
        rows = [{**item, "promotion_id": _promotion_id(item["from_title"], item["to_title"])} for item in chunk]
        tx.run("""UNWIND $rows AS item MATCH (jt:JobTitle {name:item.from_title})
          OPTIONAL MATCH (existing:JobPromotion {promotion_id:item.promotion_id})
          WITH jt,item,existing WHERE existing IS NULL OR coalesce(existing.generation_source,'')<>'curated'
          MERGE (p:JobPromotion {promotion_id:item.promotion_id})
          SET p.from_title=item.from_title,p.to_title=item.to_title,p.title=coalesce(item.promotion_name,''),
            p.stage1=coalesce(item.stage1,''),p.stage2=coalesce(item.stage2,''),p.stage3=coalesce(item.stage3,''),
            p.stage3_job_title=coalesce(item.stage3_job_title,''),p.confidence=coalesce(item.confidence,0.0),
            p.rationale=coalesce(item.rationale,''),p.generation_source=$source,p.generation_run_id=$run,p.updated_at=datetime()
          MERGE (p)-[:FOR_JOB_TITLE]->(jt)""", rows=rows, source=source, run=run_id)
    if _version(change) == 1 and change.get("replace_auto_promotions", True):
        tx.run("MATCH (p:JobPromotion {generation_source:$source}) WHERE coalesce(p.generation_run_id,'')<>$run DETACH DELETE p", source=source, run=run_id)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.promotions", loader):
            tx.run("UNWIND $rows AS item MATCH (p:JobPromotion {promotion_id:item.promotion_id,generation_source:$source}) DETACH DELETE p", rows=chunk, source=source)
    rank = 0
    for chunk in _chunks(change, "lateral", loader):
        rows = []
        for item in chunk:
            rank += 1
            rows.append({**item, "rank": rank})
        tx.run("""UNWIND $rows AS item MATCH (a:JobTitle {name:item.from}),(b:JobTitle {name:item.to})
          OPTIONAL MATCH (a)-[existing:SIMILAR_FOR_LATERAL]->(b)
          WITH a,b,item,existing WHERE existing IS NULL OR coalesce(existing.generation_source,'')<>'curated'
          MERGE (a)-[r:SIMILAR_FOR_LATERAL]->(b)
          SET r.score=coalesce(item.score,0.0),r.rank=item.rank,r.track_from=coalesce(item.track_from,''),
            r.track_to=coalesce(item.track_to,''),r.cap_similarity=coalesce(item.cap_similarity,0.0),
            r.same_track=coalesce(item.same_track,false),r.rationale=coalesce(item.rationale,''),
            r.generation_source=$source,r.generation_run_id=$run,r.updated_at=datetime()""", rows=rows, source=source, run=run_id)
    if _version(change) == 1 and change.get("replace_auto_lateral", True):
        tx.run("MATCH ()-[r:SIMILAR_FOR_LATERAL {generation_source:$source}]->() WHERE coalesce(r.generation_run_id,'')<>$run DELETE r", source=source, run=run_id)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.lateral", loader):
            tx.run("""UNWIND $rows AS item MATCH (a:JobTitle {name:item.from})
              -[r:SIMILAR_FOR_LATERAL {generation_source:$source}]->(b:JobTitle {name:item.to}) DELETE r""", rows=chunk, source=source)


def _apply_resources(tx, change: dict[str, Any], run_id: str, loader: GroupLoader | None = None) -> None:
    source = change["source_id"]
    for chunk in _chunks(change, "items", loader):
        rows = [{**row, "props": {k: value for k, value in row.items() if k != "job_titles"}} for row in chunk]
        tx.run("""UNWIND $rows AS item MERGE (r:LearningResource {resource_id:item.resource_id}) SET r += item.props,
          r.import_source_id=$source,r.source_id=$source,r.generation_source='curated',r.source_priority=100,
          r.import_run_id=$run,r.last_task_run_id=$run,r.import_managed=true,r.updated_at=datetime()
          WITH r,item OPTIONAL MATCH (r)-[old:FOR_JOB_TITLE]->(:JobTitle) DELETE old
          WITH r,item UNWIND item.job_titles AS title MATCH (jt:JobTitle {name:title})
          MERGE (r)-[rel:FOR_JOB_TITLE]->(jt) SET rel.source_id=$source,rel.generation_source='curated',rel.source_priority=100""",
          rows=rows, source=source, run=run_id)
    if _version(change) == 1 and change.get("mode") == "snapshot":
        ids = [item["resource_id"] for chunk in _chunks(change, "items", None) for item in chunk]
        tx.run("MATCH (r:LearningResource {import_source_id:$source,import_managed:true}) WHERE NOT r.resource_id IN $ids DETACH DELETE r", source=source, ids=ids)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.learning_resources", loader):
            tx.run("UNWIND $rows AS item MATCH (r:LearningResource {resource_id:item.resource_id,import_source_id:$source,import_managed:true}) DETACH DELETE r", rows=chunk, source=source)


def _apply_competitions(tx, change: dict[str, Any], run_id: str, loader: GroupLoader | None = None) -> None:
    source = change["source_id"]
    for chunk in _chunks(change, "items", loader):
        rows = [{**row, "props": {k: value for k, value in row.items() if k != "job_titles"}} for row in chunk]
        tx.run("""UNWIND $rows AS item MERGE (c:Competition {competition_id:item.competition_id}) SET c += item.props,
          c.import_source_id=$source,c.source_id=$source,c.generation_source='curated',c.source_priority=100,
          c.import_run_id=$run,c.last_task_run_id=$run,c.import_managed=true,c.updated_at=datetime()
          WITH c,item OPTIONAL MATCH (c)-[old:FOR_JOB_TITLE]->(:JobTitle) DELETE old
          WITH c,item UNWIND item.job_titles AS title MATCH (jt:JobTitle {name:title})
          MERGE (c)-[rel:FOR_JOB_TITLE]->(jt) SET rel.source_id=$source,rel.generation_source='curated',rel.source_priority=100""",
          rows=rows, source=source, run=run_id)
    if _version(change) == 1 and change.get("mode") == "snapshot":
        ids = [item["competition_id"] for chunk in _chunks(change, "items", None) for item in chunk]
        tx.run("MATCH (c:Competition {import_source_id:$source,import_managed:true}) WHERE NOT c.competition_id IN $ids DETACH DELETE c", source=source, ids=ids)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.competitions", loader):
            tx.run("UNWIND $rows AS item MATCH (c:Competition {competition_id:item.competition_id,import_source_id:$source,import_managed:true}) DETACH DELETE c", rows=chunk, source=source)


def _apply_capabilities(tx, change: dict[str, Any], _run_id: str, loader: GroupLoader | None = None) -> None:
    for chunk in _chunks(change, "jobs", loader):
        tx.run("UNWIND $rows AS item MATCH (j:Job {job_key:item.job_key}) SET j += item.capability,j.cap_updated_at=datetime()", rows=chunk)


def _apply_promotions(tx, change: dict[str, Any], run_id: str, loader: GroupLoader | None = None) -> None:
    source = change.get("source_id") or "curated-promotions"
    for chunk in _chunks(change, "items", loader):
        tx.run("""UNWIND $rows AS item MERGE (p:JobPromotion {promotion_id:item.promotion_id}) SET p += item,
          p.generation_source='curated',p.source_id=$source,p.source_priority=100,p.last_task_run_id=$run,p.updated_at=datetime()
          WITH p,item OPTIONAL MATCH (p)-[old:FOR_JOB_TITLE]->(:JobTitle) DELETE old
          WITH p,item MATCH (jt:JobTitle {name:item.job_title}) MERGE (p)-[:FOR_JOB_TITLE]->(jt)""", rows=chunk, source=source, run=run_id)
    if _version(change) == 1 and change.get("mode") == "snapshot":
        ids = [item["promotion_id"] for chunk in _chunks(change, "items", None) for item in chunk]
        tx.run("MATCH (p:JobPromotion {generation_source:'curated',source_id:$source}) WHERE NOT p.promotion_id IN $ids DETACH DELETE p", source=source, ids=ids)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.promotions", loader):
            tx.run("UNWIND $rows AS item MATCH (p:JobPromotion {promotion_id:item.promotion_id,generation_source:'curated',source_id:$source}) DETACH DELETE p", rows=chunk, source=source)


def _apply_lateral_import(tx, change: dict[str, Any], run_id: str, loader: GroupLoader | None = None) -> None:
    source = change.get("source_id") or "curated-lateral"
    for chunk in _chunks(change, "items", loader):
        rows = [{**row, "props": {k: value for k, value in row.items() if k not in {"from_job_title", "to_job_title"}}} for row in chunk]
        tx.run("""UNWIND $rows AS item MATCH (a:JobTitle {name:item.from_job_title}),(b:JobTitle {name:item.to_job_title})
          MERGE (a)-[r:SIMILAR_FOR_LATERAL]->(b) SET r += item.props,r.generation_source='curated',
          r.source_id=$source,r.source_priority=100,r.last_task_run_id=$run,r.updated_at=datetime()""", rows=rows, source=source, run=run_id)
    if _version(change) == 1 and change.get("mode") == "snapshot":
        pairs = [f"{item['from_job_title']}\u0000{item['to_job_title']}" for chunk in _chunks(change, "items", None) for item in chunk]
        tx.run("MATCH (a:JobTitle)-[r:SIMILAR_FOR_LATERAL {generation_source:'curated',source_id:$source}]->(b:JobTitle) WHERE NOT (a.name+'\\u0000'+b.name) IN $pairs DELETE r", source=source, pairs=pairs)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.lateral", loader):
            tx.run("""UNWIND $rows AS item MATCH (a:JobTitle {name:item.from})
              -[r:SIMILAR_FOR_LATERAL {generation_source:'curated',source_id:$source}]->(b:JobTitle {name:item.to}) DELETE r""", rows=chunk, source=source)


def _apply_recommendations(tx, change: dict[str, Any], run_id: str, loader: GroupLoader | None = None) -> None:
    source = change.get("source_id") or "curated-promotion-recommendations"
    for chunk in _chunks(change, "resource_recommendations", loader):
        rows = [{**row, "props": {k: value for k, value in row.items() if k not in {"promotion_id", "resource_id"}}} for row in chunk]
        tx.run("""UNWIND $rows AS item MATCH (p:JobPromotion {promotion_id:item.promotion_id}),(r:LearningResource {resource_id:item.resource_id})
          MERGE (p)-[rel:RECOMMENDS_RESOURCE]->(r) SET rel += item.props,rel.generation_source='curated',
          rel.source_id=$source,rel.source_priority=100,rel.last_task_run_id=$run,rel.updated_at=datetime()""", rows=rows, source=source, run=run_id)
    for chunk in _chunks(change, "competition_recommendations", loader):
        rows = [{**row, "props": {k: value for k, value in row.items() if k not in {"promotion_id", "competition_id"}}} for row in chunk]
        tx.run("""UNWIND $rows AS item MATCH (p:JobPromotion {promotion_id:item.promotion_id}),(c:Competition {competition_id:item.competition_id})
          MERGE (p)-[rel:RECOMMENDS_COMPETITION]->(c) SET rel += item.props,rel.generation_source='curated',
          rel.source_id=$source,rel.source_priority=100,rel.last_task_run_id=$run,rel.updated_at=datetime()""", rows=rows, source=source, run=run_id)
    if _version(change) == 1 and change.get("mode") == "snapshot":
        resource_keys = [f"{item['promotion_id']}\u0000{item['resource_id']}" for chunk in _chunks(change, "resource_recommendations", None) for item in chunk]
        competition_keys = [f"{item['promotion_id']}\u0000{item['competition_id']}" for chunk in _chunks(change, "competition_recommendations", None) for item in chunk]
        tx.run("MATCH (p:JobPromotion)-[r:RECOMMENDS_RESOURCE {source_id:$source}]->(x:LearningResource) WHERE NOT (p.promotion_id+'\\u0000'+x.resource_id) IN $keys DELETE r", source=source, keys=resource_keys)
        tx.run("MATCH (p:JobPromotion)-[r:RECOMMENDS_COMPETITION {source_id:$source}]->(x:Competition) WHERE NOT (p.promotion_id+'\\u0000'+x.competition_id) IN $keys DELETE r", source=source, keys=competition_keys)
    elif _version(change) >= 2:
        for chunk in _chunks(change, "delete.resource_recommendations", loader):
            tx.run("""UNWIND $rows AS item MATCH (p:JobPromotion {promotion_id:item.promotion_id})
              -[r:RECOMMENDS_RESOURCE {source_id:$source}]->(x:LearningResource {resource_id:item.resource_id}) DELETE r""", rows=chunk, source=source)
        for chunk in _chunks(change, "delete.competition_recommendations", loader):
            tx.run("""UNWIND $rows AS item MATCH (p:JobPromotion {promotion_id:item.promotion_id})
              -[r:RECOMMENDS_COMPETITION {source_id:$source}]->(x:Competition {competition_id:item.competition_id}) DELETE r""", rows=chunk, source=source)


def _apply_salary(tx, change: dict[str, Any], _run_id: str, loader: GroupLoader | None = None) -> None:
    for chunk in _chunks(change, "jobs", loader):
        tx.run("UNWIND $rows AS item MATCH (j:Job {job_key:item.job_key}) SET j += item.new", rows=chunk)


def _apply_inferred_cleanup(tx, change: dict[str, Any], _run_id: str, loader: GroupLoader | None = None) -> None:
    for chunk in _chunks(change, "jobs", loader):
        tx.run("UNWIND $rows AS item MATCH (j:Job {job_key:item.job_key,source:'inferred'}) DETACH DELETE j", rows=chunk)
    tx.run("MATCH (jt:JobTitle) OPTIONAL MATCH (j:Job)-[:HAS_TITLE]->(jt) WITH jt,count(j) AS actual SET jt.job_count=actual")
    for chunk in _chunks(change, "job_titles", loader):
        tx.run("""UNWIND $rows AS item MATCH (jt:JobTitle {name:item.name})
          WHERE coalesce(jt.job_count,0)<2 AND NOT EXISTS { MATCH (jt)-[r]-(n)
            WHERE coalesce(r.generation_source,'')='curated' OR coalesce(n.generation_source,'')='curated' }
          DETACH DELETE jt""", rows=chunk)


def is_task_applied(task_uuid: str) -> bool:
    uri, user, password, database = neo4j_settings()
    if not password:
        return False
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        row = session.run("MATCH (c:GraphTaskCommit {task_uuid:$uuid}) RETURN count(c) AS total", uuid=task_uuid).single()
        return bool(row and int(row["total"]) > 0)


def ensure_graph_schema() -> None:
    """Idempotent startup check; never runs inside a task's apply transaction."""
    uri, user, password, database = neo4j_settings()
    if not password:
        raise RuntimeError("未配置 NEO4J_PASSWORD")
    driver = neo4j_driver(uri, user, password)
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


def apply_change_set(
    change: dict[str, Any], *, task_uuid: str, change_sha256: str,
    group_loader: GroupLoader | None = None,
) -> dict[str, Any]:
    uri, user, password, database = neo4j_settings()
    if not password:
        raise RuntimeError("未配置 NEO4J_PASSWORD")
    driver = neo4j_driver(uri, user, password)
    run_id = uuid4().hex
    if is_task_applied(task_uuid):
        return {"run_id": run_id, "kind": change.get("kind"), "already_applied": True}

    def apply(tx):
        kind = change.get("kind")
        handlers = {
            "job_import": _apply_job,
            "job_capability_evaluation": _apply_capabilities,
            "job_capability_result_import": _apply_capabilities,
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
        except KeyError as exc:
            raise ValueError(f"未知变更集类型: {kind}") from exc
        handler(tx, change, run_id, group_loader)
        tx.run("CREATE (c:GraphTaskCommit {task_uuid:$uuid,change_sha256:$sha,run_id:$run,applied_at:datetime()})", uuid=task_uuid, sha=change_sha256, run=run_id)

    with driver.session(database=database) as session:
        session.execute_write(apply)
    return {"run_id": run_id, "kind": change.get("kind")}
