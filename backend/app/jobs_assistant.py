import json
import re
from typing import Any, Dict, List, Optional, Tuple

import jwt
from flask import Blueprint, current_app, jsonify, request
from openai import OpenAI

from .db import db_cursor
from .jobs import _driver, _neo4j_settings, _serialize_row

jobs_assistant_bp = Blueprint("jobs_assistant", __name__, url_prefix="/api/jobs/assistant")

ALLOWED_FILTER_KEYS = {
    "keywords",
    "locations",
    "company",
    "industry",
    "experience_min",
    "experience_max",
    "salary_text",
    "limit",
}


def _get_user_id_from_auth() -> Tuple[Optional[int], Optional[str]]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "未提供有效令牌"
    token = auth_header.replace("Bearer ", "", 1).strip()
    if not token:
        return None, "未提供有效令牌"
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None, "令牌无效或已过期"

    sub = payload.get("sub")
    try:
        user_id = int(sub) if sub is not None else None
    except (TypeError, ValueError):
        user_id = None
    if not user_id:
        return None, "令牌无效或已过期"
    return user_id, None


def _ensure_tables() -> None:
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_chat_sessions (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              user_id BIGINT UNSIGNED NOT NULL,
              title VARCHAR(120) NOT NULL DEFAULT '新对话',
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              last_message_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_ai_chat_sessions_user_id_last_message_at (user_id, last_message_at DESC),
              CONSTRAINT fk_ai_chat_sessions_user_id
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_chat_messages (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              session_id BIGINT UNSIGNED NOT NULL,
              role VARCHAR(16) NOT NULL,
              content TEXT NOT NULL,
              filters_json JSON NULL,
              result_job_ids_json JSON NULL,
              is_saved TINYINT(1) NOT NULL DEFAULT 0,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_ai_chat_messages_session_id_created_at (session_id, created_at ASC),
              KEY idx_ai_chat_messages_is_saved (is_saved),
              CONSTRAINT fk_ai_chat_messages_session_id
                FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def _coerce_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return default
    return default


def _clean_text_list(value: Any, max_items: int = 8) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text[:60])
        if len(out) >= max_items:
            break
    return out


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_filters(raw_filters: Dict[str, Any]) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    for key in ALLOWED_FILTER_KEYS:
        if key not in raw_filters:
            continue
        filters[key] = raw_filters[key]

    filters["keywords"] = _clean_text_list(filters.get("keywords"), max_items=8)
    filters["locations"] = _clean_text_list(filters.get("locations"), max_items=4)
    filters["company"] = _clean_text_list(filters.get("company"), max_items=3)
    filters["industry"] = _clean_text_list(filters.get("industry"), max_items=3)
    filters["salary_text"] = _clean_text_list(filters.get("salary_text"), max_items=3)

    exp_min = _safe_int(filters.get("experience_min"), -1)
    exp_max = _safe_int(filters.get("experience_max"), -1)
    if exp_min >= 0:
        filters["experience_min"] = exp_min
    else:
        filters.pop("experience_min", None)
    if exp_max >= 0:
        filters["experience_max"] = exp_max
    else:
        filters.pop("experience_max", None)

    limit = _safe_int(filters.get("limit"), 20)
    cfg_max = int(current_app.config.get("AI_MAX_RETURN_JOBS", 40))
    filters["limit"] = max(1, min(limit, max(1, cfg_max)))
    return filters


def _merge_filters(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(previous or {})
    for key, value in current.items():
        merged[key] = value
    return _normalize_filters(merged)


def _build_openai_client() -> OpenAI:
    api_key = current_app.config.get("ARK_API_KEY", "")
    if not api_key:
        raise RuntimeError("未配置 ARK_API_KEY")
    timeout = int(current_app.config.get("AI_LLM_TIMEOUT_SECONDS", 90))
    base_url = str(current_app.config.get("ARK_BASE_URL", "")).strip()
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def _strip_fenced_json(text: str) -> str:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()


def _llm_json_call(system_prompt: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = _build_openai_client()
    model = current_app.config.get("ARK_MODEL", "doubao-seed-2-0-mini-260215")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
        stream=False,
        response_format={"type": "json_object"},
    )
    content = (resp.choices[0].message.content or "").strip()
    content = _strip_fenced_json(content)
    data = json.loads(content)
    if not isinstance(data, dict):
        raise RuntimeError("模型返回结构不合法")
    return data


def _fallback_parse_filters(message: str) -> Dict[str, Any]:
    filters: Dict[str, Any] = {
        "keywords": [],
        "locations": [],
        "company": [],
        "industry": [],
        "salary_text": [],
        "limit": 20,
    }
    text = message.strip()
    if not text:
        return {"intent": "qa", "operation": "merge", "filters": filters}
    filters["keywords"] = [text[:30]]
    return {"intent": "both", "operation": "merge", "filters": filters}


def _parse_intent_filters(
    message: str,
    previous_filters: Dict[str, Any],
    context_messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        result = _llm_json_call(
            system_prompt=(
                "你是岗位检索条件解析器。"
                "仅输出 JSON 对象，不要输出解释。"
                "输出字段: intent, operation, filters。"
                "intent 仅允许 filter|qa|both。operation 仅允许 merge|replace。"
                "filters 只允许这些键: keywords,locations,company,industry,experience_min,experience_max,salary_text,limit。"
            ),
            payload={
                "message": message,
                "previous_filters": previous_filters,
                "context_messages": context_messages[-6:],
                "output_schema_example": {
                    "intent": "both",
                    "operation": "merge",
                    "filters": {
                        "keywords": ["科研人员"],
                        "locations": ["杭州"],
                        "company": [],
                        "industry": [],
                        "experience_min": 1,
                        "experience_max": 5,
                        "salary_text": ["2-3万"],
                        "limit": 20,
                    },
                },
            },
        )
    except Exception:
        result = _fallback_parse_filters(message)

    intent = str(result.get("intent") or "both").strip().lower()
    if intent not in {"filter", "qa", "both"}:
        intent = "both"
    operation = str(result.get("operation") or "merge").strip().lower()
    if operation not in {"merge", "replace"}:
        operation = "merge"

    filters = _normalize_filters(_coerce_json(result.get("filters"), {}))
    if operation == "replace":
        merged = filters
    else:
        merged = _merge_filters(previous_filters, filters)
    return {"intent": intent, "filters": merged, "operation": operation}


def _build_filter_cypher(filters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    where_parts = ["(j.source IS NULL OR trim(toString(j.source)) = '')"]
    params: Dict[str, Any] = {}

    keywords = filters.get("keywords") or []
    for idx, kw in enumerate(keywords):
        key = f"kw_{idx}"
        params[key] = str(kw).lower()
        where_parts.append(
            "("
            f"toLower(coalesce(j.title, j.name, '')) CONTAINS ${key} OR "
            f"toLower(coalesce(j.company, '')) CONTAINS ${key} OR "
            f"toLower(coalesce(j.location, '')) CONTAINS ${key} OR "
            f"toLower(coalesce(j.demand, '')) CONTAINS ${key} OR "
            f"toLower(coalesce(j.industry, '')) CONTAINS ${key}"
            ")"
        )

    locations = filters.get("locations") or []
    if locations:
        params["locations"] = [str(x).lower() for x in locations]
        where_parts.append("any(loc in $locations WHERE toLower(coalesce(j.location, '')) CONTAINS loc)")

    companies = filters.get("company") or []
    if companies:
        params["companies"] = [str(x).lower() for x in companies]
        where_parts.append("any(comp in $companies WHERE toLower(coalesce(j.company, '')) CONTAINS comp)")

    industries = filters.get("industry") or []
    if industries:
        params["industries"] = [str(x).lower() for x in industries]
        where_parts.append(
            "any(ind in $industries WHERE toLower(coalesce(j.industry, '')) CONTAINS ind)"
        )

    salary_text = filters.get("salary_text") or []
    if salary_text:
        params["salary_text"] = [str(x).lower() for x in salary_text]
        where_parts.append("any(s in $salary_text WHERE toLower(coalesce(j.salary, '')) CONTAINS s)")

    if "experience_min" in filters:
        params["experience_min"] = int(filters["experience_min"])
        where_parts.append("coalesce(toFloat(j.experience_years), 0.0) >= toFloat($experience_min)")

    if "experience_max" in filters:
        params["experience_max"] = int(filters["experience_max"])
        where_parts.append("coalesce(toFloat(j.experience_years), 0.0) <= toFloat($experience_max)")

    params["limit"] = int(filters.get("limit") or 20)
    where_clause = " AND ".join(where_parts)
    query = f"""
    MATCH (j:Job)
    WHERE {where_clause}
    WITH j,
      (coalesce(j.cap_req_theory, 0.0) +
       coalesce(j.cap_req_cross, 0.0) +
       coalesce(j.cap_req_practice, 0.0) +
       coalesce(j.cap_req_digital, 0.0) +
       coalesce(j.cap_req_innovation, 0.0) +
       coalesce(j.cap_req_teamwork, 0.0) +
       coalesce(j.cap_req_social, 0.0) +
       coalesce(j.cap_req_growth, 0.0)) AS total_score
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.salary, '薪资面议') AS salary,
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
      coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
      coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
      coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
      coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
      coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
      coalesce(j.cap_req_social, 0.0) AS cap_req_social,
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
      coalesce(j.cap_conf_theory, 0.0) AS cap_conf_theory,
      coalesce(j.cap_conf_cross, 0.0) AS cap_conf_cross,
      coalesce(j.cap_conf_practice, 0.0) AS cap_conf_practice,
      coalesce(j.cap_conf_digital, 0.0) AS cap_conf_digital,
      coalesce(j.cap_conf_innovation, 0.0) AS cap_conf_innovation,
      coalesce(j.cap_conf_teamwork, 0.0) AS cap_conf_teamwork,
      coalesce(j.cap_conf_social, 0.0) AS cap_conf_social,
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth
    ORDER BY total_score DESC, title ASC
    LIMIT $limit
    """
    return query, params


def _query_jobs(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    uri, user, password, database = _neo4j_settings()
    if not password:
        raise RuntimeError("缺少 NEO4J_PASSWORD")
    query, params = _build_filter_cypher(filters)
    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, params)]
    return [_serialize_row(row) for row in rows]


def _query_jobs_by_ids(job_ids: List[str]) -> List[Dict[str, Any]]:
    if not job_ids:
        return []
    uri, user, password, database = _neo4j_settings()
    if not password:
        return []
    query = """
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) IN $ids
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.salary, '薪资面议') AS salary,
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
      coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
      coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
      coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
      coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
      coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
      coalesce(j.cap_req_social, 0.0) AS cap_req_social,
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
      coalesce(j.cap_conf_theory, 0.0) AS cap_conf_theory,
      coalesce(j.cap_conf_cross, 0.0) AS cap_conf_cross,
      coalesce(j.cap_conf_practice, 0.0) AS cap_conf_practice,
      coalesce(j.cap_conf_digital, 0.0) AS cap_conf_digital,
      coalesce(j.cap_conf_innovation, 0.0) AS cap_conf_innovation,
      coalesce(j.cap_conf_teamwork, 0.0) AS cap_conf_teamwork,
      coalesce(j.cap_conf_social, 0.0) AS cap_conf_social,
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth
    """
    driver = _driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"ids": job_ids})]
    jobs = [_serialize_row(row) for row in rows]
    order = {job_id: i for i, job_id in enumerate(job_ids)}
    jobs.sort(key=lambda x: order.get(x["id"], 999999))
    return jobs


def _build_context_messages(session_id: int) -> List[Dict[str, Any]]:
    window = max(1, int(current_app.config.get("AI_CONTEXT_WINDOW", 6)))
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT role, content, filters_json
            FROM ai_chat_messages
            WHERE session_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (session_id, window * 2),
        )
        rows = cursor.fetchall()
    rows.reverse()
    result: List[Dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "role": row.get("role"),
                "content": row.get("content"),
                "filters": _coerce_json(row.get("filters_json"), {}),
            }
        )
    return result


def _build_answer_text(
    question: str,
    filters: Dict[str, Any],
    jobs: List[Dict[str, Any]],
    context_messages: List[Dict[str, Any]],
) -> str:
    summary_jobs = [
        {
            "title": j.get("title"),
            "company": j.get("company"),
            "location": j.get("location"),
            "salary": j.get("salary"),
            "score_avg": j.get("score_avg"),
        }
        for j in jobs[:8]
    ]
    try:
        result = _llm_json_call(
            system_prompt=(
                "你是岗位检索助手，请根据用户问题和筛选命中结果给出简明回答。"
                "仅输出 JSON：answer,bullet_points。"
                "answer 用简洁中文，bullet_points 最多 4 条。"
            ),
            payload={
                "question": question,
                "filters": filters,
                "matched_count": len(jobs),
                "matched_jobs": summary_jobs,
                "context_messages": context_messages[-6:],
            },
        )
        answer = str(result.get("answer") or "").strip()
        bullets = _clean_text_list(result.get("bullet_points"), max_items=4)
        if bullets:
            answer = answer + "\n" + "\n".join([f"- {b}" for b in bullets])
        if answer:
            return answer
    except Exception:
        pass

    if not jobs:
        return "本次没有筛到符合条件的岗位。建议放宽城市、经验或薪资条件后再试。"
    top = jobs[:3]
    lines = [f"已为你筛到 {len(jobs)} 个岗位，优先推荐："]
    for item in top:
        lines.append(
            f"- {item.get('title', '岗位')}｜{item.get('company', '未知公司')}｜{item.get('location', '未知地点')}｜{item.get('salary', '薪资面议')}"
        )
    lines.append("如果你愿意，我可以继续按“城市/薪资/经验/行业”任一条件进一步收窄。")
    return "\n".join(lines)


def _extract_previous_filters(session_id: int) -> Dict[str, Any]:
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT filters_json
            FROM ai_chat_messages
            WHERE session_id = %s AND role = 'assistant' AND filters_json IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id,),
        )
        row = cursor.fetchone()
    return _normalize_filters(_coerce_json((row or {}).get("filters_json"), {}))


def _create_or_load_session(user_id: int, session_id: Optional[int], first_text: str) -> int:
    with db_cursor() as (_, cursor):
        if session_id:
            cursor.execute(
                "SELECT id FROM ai_chat_sessions WHERE id = %s AND user_id = %s LIMIT 1",
                (session_id, user_id),
            )
            row = cursor.fetchone()
            if row:
                return int(row["id"])

        title = (first_text.strip() or "新对话")[:40]
        cursor.execute(
            """
            INSERT INTO ai_chat_sessions (user_id, title, last_message_at)
            VALUES (%s, %s, NOW())
            """,
            (user_id, title),
        )
        return int(cursor.lastrowid)


@jobs_assistant_bp.post("/chat")
def chat():
    user_id, err = _get_user_id_from_auth()
    if err:
        return jsonify({"ok": False, "message": err}), 401

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "message": "消息不能为空"}), 400
    if len(message) > 2000:
        return jsonify({"ok": False, "message": "消息过长，请控制在 2000 字以内"}), 400

    _ensure_tables()

    requested_session_id = payload.get("session_id")
    session_id = _create_or_load_session(
        user_id=user_id or 0,
        session_id=_safe_int(requested_session_id, 0) or None,
        first_text=message,
    )

    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO ai_chat_messages (session_id, role, content, created_at)
            VALUES (%s, 'user', %s, NOW())
            """,
            (session_id, message),
        )
        user_message_id = int(cursor.lastrowid)

    context_messages = _build_context_messages(session_id)
    previous_filters = _extract_previous_filters(session_id)
    parse_result = _parse_intent_filters(message, previous_filters, context_messages)
    merged_filters = parse_result["filters"]

    intent = parse_result["intent"]
    matched_jobs: List[Dict[str, Any]] = []
    if intent in {"filter", "both"}:
        matched_jobs = _query_jobs(merged_filters)

    answer_text = _build_answer_text(message, merged_filters, matched_jobs, context_messages)
    result_ids = [str(item.get("id")) for item in matched_jobs if item.get("id")]

    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO ai_chat_messages (
              session_id, role, content, filters_json, result_job_ids_json, is_saved, created_at
            ) VALUES (%s, 'assistant', %s, %s, %s, 0, NOW())
            """,
            (
                session_id,
                answer_text,
                json.dumps(merged_filters, ensure_ascii=False),
                json.dumps(result_ids, ensure_ascii=False),
            ),
        )
        assistant_message_id = int(cursor.lastrowid)
        cursor.execute(
            """
            UPDATE ai_chat_sessions
            SET last_message_at = NOW(), updated_at = NOW()
            WHERE id = %s AND user_id = %s
            """,
            (session_id, user_id),
        )

    return jsonify(
        {
            "ok": True,
            "data": {
                "session_id": session_id,
                "filters": merged_filters,
                "jobs": matched_jobs,
                "user_message": {
                    "id": user_message_id,
                    "role": "user",
                    "content": message,
                    "is_saved": False,
                },
                "assistant_message": {
                    "id": assistant_message_id,
                    "role": "assistant",
                    "content": answer_text,
                    "is_saved": False,
                },
            },
        }
    )


@jobs_assistant_bp.get("/sessions")
def list_sessions():
    user_id, err = _get_user_id_from_auth()
    if err:
        return jsonify({"ok": False, "message": err}), 401
    _ensure_tables()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT id, title, created_at, updated_at, last_message_at
            FROM ai_chat_sessions
            WHERE user_id = %s
            ORDER BY last_message_at DESC, id DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
    return jsonify({"ok": True, "data": {"sessions": rows}})


@jobs_assistant_bp.get("/sessions/<int:session_id>")
def session_detail(session_id: int):
    user_id, err = _get_user_id_from_auth()
    if err:
        return jsonify({"ok": False, "message": err}), 401
    _ensure_tables()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT id, title, created_at, updated_at, last_message_at
            FROM ai_chat_sessions
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (session_id, user_id),
        )
        session_row = cursor.fetchone()
        if not session_row:
            return jsonify({"ok": False, "message": "会话不存在"}), 404

        cursor.execute(
            """
            SELECT id, role, content, filters_json, result_job_ids_json, is_saved, created_at
            FROM ai_chat_messages
            WHERE session_id = %s
            ORDER BY id ASC
            """,
            (session_id,),
        )
        messages = cursor.fetchall()

    latest_ids: List[str] = []
    latest_filters: Dict[str, Any] = {}
    for row in reversed(messages):
        role = str(row.get("role") or "")
        if role != "assistant":
            continue
        ids = _coerce_json(row.get("result_job_ids_json"), [])
        if isinstance(ids, list) and ids:
            latest_ids = [str(x) for x in ids if str(x).strip()]
            latest_filters = _normalize_filters(_coerce_json(row.get("filters_json"), {}))
            break

    jobs = _query_jobs_by_ids(latest_ids)
    for row in messages:
        row["filters_json"] = _coerce_json(row.get("filters_json"), {})
        row["result_job_ids_json"] = _coerce_json(row.get("result_job_ids_json"), [])
        row["is_saved"] = bool(row.get("is_saved"))

    return jsonify(
        {
            "ok": True,
            "data": {
                "session": session_row,
                "messages": messages,
                "jobs": jobs,
                "filters": latest_filters,
            },
        }
    )


@jobs_assistant_bp.post("/messages/<int:message_id>/save")
def save_message(message_id: int):
    user_id, err = _get_user_id_from_auth()
    if err:
        return jsonify({"ok": False, "message": err}), 401
    _ensure_tables()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE ai_chat_messages m
            JOIN ai_chat_sessions s ON s.id = m.session_id
            SET m.is_saved = 1
            WHERE m.id = %s
              AND m.role = 'assistant'
              AND s.user_id = %s
            """,
            (message_id, user_id),
        )
        updated = cursor.rowcount
    if updated <= 0:
        return jsonify({"ok": False, "message": "消息不存在或无权限"}), 404
    return jsonify({"ok": True, "message": "已保存"})
