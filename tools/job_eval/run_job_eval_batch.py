import argparse
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from neo4j import GraphDatabase
from openai import OpenAI


DIM_KEYS = [
    "cap_req_theory",
    "cap_req_cross",
    "cap_req_practice",
    "cap_req_digital",
    "cap_req_innovation",
    "cap_req_teamwork",
    "cap_req_social",
    "cap_req_growth",
]

CONF_KEYS = [
    "cap_conf_theory",
    "cap_conf_cross",
    "cap_conf_practice",
    "cap_conf_digital",
    "cap_conf_innovation",
    "cap_conf_teamwork",
    "cap_conf_social",
    "cap_conf_growth",
]

# 与 DIM_KEYS / CONF_KEYS 顺序一一对应，用于解析模型误用的短键名
_SHORT_TO_REQ = {
    "theory": "cap_req_theory",
    "cross": "cap_req_cross",
    "practice": "cap_req_practice",
    "digital": "cap_req_digital",
    "innovation": "cap_req_innovation",
    "teamwork": "cap_req_teamwork",
    "social": "cap_req_social",
    "growth": "cap_req_growth",
}
_SHORT_TO_CONF = {k: v.replace("cap_req_", "cap_conf_") for k, v in _SHORT_TO_REQ.items()}
_REQ_TO_CONF = dict(zip(DIM_KEYS, CONF_KEYS))

# 《能力画像图谱-职业评估依据（最终版）》中与 8 维相关的定义、计分要点与禁忌（压缩版，随 payload 发给模型）
EVAL_SPEC_COMPACT = """
【总框架】Score(j,k)=100*(a*S_skill+b*S_text+c*S_graph+d*S_level)，子分归一化到[0,1]，总分截断[0,100]；默认 a=0.45,b=0.30,c=0.15,d=0.10。
证据类型：S_skill=REQUIRES+维度映射；S_text=JD/职责语义；S_graph=连接/跨域/迁移(TRANSFER_TO/VERTICAL_UP等)；S_level=岗位层级。
【八维定义与锚点】cap_req_theory 专业理论知识(学科深度/方法论/抽象理解) 锚点80+高理论门槛 60-79理论应用并重 40-59基础理论 0-39弱理论。
cap_req_cross 交叉学科广度(整合/复合问题) 看技能簇覆盖与跨域信号。
cap_req_practice 专业实践技能(落地/交付/工具链) 看年限、闭环技能、交付类表述。
cap_req_digital 数字素养(工具/数据/编程与AI) 看语言工具覆盖与熟练度词。
cap_req_innovation 创新创业(新方案/0-1/优化探索) 看创新职责与结果导向信号。
cap_req_teamwork 团队协作(沟通/跨团队/组织配合) 看协同词与管理/主导信号。
cap_req_social 社会实践网络(行业链接/外部协作) 看客户渠道生态商务及对外职责。
cap_req_growth 学习与发展潜力(学习敏捷/适应变化/可持续成长) 看学习词与迁移晋升结构。
【等级】0-39低 40-59中 60-79较高 80-100核心高要求。
【置信度】Conf≈0.5*证据覆盖+0.3*ai自行判断+0.2*数据多元性;Conf<0.6 表示证据不足仅供参考。须与 scores 逐维对应输出 cap_conf_*。
【禁忌与偏差控制】禁止无证据编造 JD 或技能；不得因行业热词单独抬分；同义技能勿重复计分；证据冲突须在 risk_flags 说明；仅使用输入 job 中可核对字段与 skills，勿引用输入中不存在的字段。
【公司方向与八维偏重】先阅读 job.company、job.company_detail、job.company_type，用一句话概括「公司方向/赛道」（如技术研发、教育培训、互联网平台、销售驱动、制造交付等），不得编造三字段之外的公司事实。
据此对八维给出相对「评估侧重」：在 0–100 打分时，对与方向强相关的维度可适当抬高、对弱相关维度相对压低，且必须与 job.demand、job.title、skills 交叉印证；禁止仅凭公司名或融资类型堆砌高分；描述模糊时降低相关 cap_conf_*。
侧重参考（可交叉，非互斥）：①研发/科研/硬科技→cap_req_theory、cap_req_innovation、cap_req_digital 为主，cap_req_practice 次之。②教育/知识服务/内容→cap_req_theory、cap_req_social、cap_req_growth 为主，cap_req_digital 次之。③互联网产品/平台/运营/数据→cap_req_digital、cap_req_cross、cap_req_teamwork 为主，cap_req_innovation 次之。④销售/市场/渠道/商务→cap_req_social、cap_req_practice、cap_req_teamwork 为主，cap_req_cross 次之。⑤生产/供应链/交付实施→cap_req_practice、cap_req_teamwork 为主，cap_req_theory 次之。⑥company_type 仅作组织节奏辅助信号，须与岗位证据一致才可微调。
evidence 中至少一条用一句话点明公司方向与八维偏重的对应（勿复述 company_detail 长文）。
【规模薪资与工作价值含量】读 company_size、salary，以月薪 1 万为参照做价值档位辅助；须与 demand/title/skills 一致才可同向微调八维；空/面议在 evidence 或 risk_flags 用一句话说明。
【数据多元性】技能、demand、图结构、公司信息等多源越少 cap_conf_* 越低。
【证据与风险文风】evidence 总数≤8，每条为极短依据：点明字段名+结论即可，单条中文≤40字，禁止大段粘贴 JD/公司简介。risk_flags 总数≤8，每项中文≤35字，写结论不写散文。
""".strip()


def load_dotenv_if_exists(env_path: str) -> None:
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass
class AppConfig:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    deepseek_api_key: str
    dashscope_api_key: str
    primary_provider: str
    review_provider: str
    review_conf_threshold: float
    cap_version: str


def get_config() -> AppConfig:
    return AppConfig(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        primary_provider=os.getenv("PRIMARY_PROVIDER", "deepseek").strip().lower(),
        review_provider=os.getenv("REVIEW_PROVIDER", "qwen").strip().lower(),
        review_conf_threshold=float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.60")),
        cap_version=os.getenv("CAP_VERSION", "v1.0.0-pilot200"),
    )


def _llm_http_timeout_seconds() -> float:
    """单次 chat.completions 请求超时（秒）；过小易中断，过大便于慢网络。"""
    return float(os.getenv("LLM_TIMEOUT_SECONDS", "180"))


def build_openai_client(provider: str, cfg: AppConfig) -> Tuple[OpenAI, str]:
    timeout = _llm_http_timeout_seconds()
    if provider == "deepseek":
        if not cfg.deepseek_api_key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY")
        client = OpenAI(
            api_key=cfg.deepseek_api_key,
            base_url="https://api.deepseek.com",
            timeout=timeout,
        )
        return client, "deepseek-chat"
    if provider == "qwen":
        if not cfg.dashscope_api_key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY")
        client = OpenAI(
            api_key=cfg.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=timeout,
        )
        return client, "qwen3.6-plus"
    raise RuntimeError(f"未知 provider: {provider}")


def _job_key_is_inferred(job: Dict[str, Any]) -> bool:
    """job_key 以 inferred 结尾时视为推断占位岗，不调用大模型。"""
    jk = str(job.get("job_key") or "").strip()
    return jk.endswith("inferred")


def build_inferred_zero_result(job_id: str) -> Dict[str, Any]:
    """推断岗：全 0 分、全 0 置信度、依据为无，不调 API。"""
    return {
        "job_id": job_id,
        "scores": {k: 0.0 for k in DIM_KEYS},
        "confidence": {k: 0.0 for k in CONF_KEYS},
        "evidence": [{"依据": "无", "说明": "job_key 以 inferred 结尾，跳过模型评估"}],
        "risk_flags": ["no_llm:job_key_suffix_inferred"],
        "fusion": {"strategy": "inferred_zero_no_llm"},
    }


def _strip_markdown_json_fence(text: str) -> str:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _json_objectify(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    return value


def _dict_to_evidence_list(d: Dict[str, Any]) -> List[Any]:
    """把模型误输出的 evidence 对象转成数组。"""
    for key in ("items", "evidences", "evidence", "list", "details", "points", "records"):
        nested = d.get(key)
        if isinstance(nested, list):
            return nested
    out: List[Any] = []
    for k, v in d.items():
        if isinstance(v, (str, int, float, bool)):
            out.append({"field": str(k), "detail": v})
        elif isinstance(v, dict):
            row: Dict[str, Any] = {"field": str(k)}
            row.update(v)
            out.append(row)
        elif isinstance(v, list):
            out.append({"field": str(k), "items": v})
    return out if out else [d]


def _coerce_evidence_to_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("[") or s.startswith("{"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return _dict_to_evidence_list(parsed)
            except json.JSONDecodeError:
                pass
        return [{"text": s}]
    if isinstance(value, dict):
        return _dict_to_evidence_list(value)
    return [{"value": value}]


def _coerce_risk_flags_to_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return [s]
    if isinstance(value, dict):
        nested = value.get("flags") or value.get("risk_flags") or value.get("items")
        if isinstance(nested, list):
            return nested
        return [json.dumps(value, ensure_ascii=False)]
    return [str(value)]


def normalize_llm_eval_dict(result: Dict[str, Any]) -> None:
    """把常见模型偏差（嵌套一层、scores/confidence 为 JSON 字符串）修成 validate_result 可接受的形状。"""
    inner_keys = (
        "result",
        "data",
        "output",
        "evaluation",
        "payload",
        "response",
        "analysis",
    )
    for k in inner_keys:
        inner = result.get(k)
        if not isinstance(inner, dict):
            continue
        scores_inner = _json_objectify(inner.get("scores"))
        conf_inner = _json_objectify(inner.get("confidence"))
        if not isinstance(scores_inner, dict) or not isinstance(conf_inner, dict):
            continue
        inner = {**inner, "scores": scores_inner, "confidence": conf_inner}
        for field in ("scores", "confidence", "evidence", "risk_flags", "job_id"):
            if field not in inner:
                continue
            cur = result.get(field)
            inner_v = inner[field]
            if field in ("scores", "confidence"):
                if not isinstance(cur, dict):
                    result[field] = inner_v
            elif field in ("evidence", "risk_flags"):
                if not isinstance(cur, list) and isinstance(inner_v, list):
                    result[field] = inner_v
                elif cur in (None, [], "") and inner_v not in (None, "", []):
                    result[field] = inner_v
            elif cur in (None, [], "") and inner_v not in (None, "", []):
                result[field] = inner_v
        break

    for fld in ("scores", "confidence"):
        fixed = _json_objectify(result.get(fld))
        if isinstance(fixed, dict):
            result[fld] = fixed

    _normalize_scores_confidence_inplace(result)
    _normalize_evidence_risk_flags_inplace(result)


def _normalize_evidence_risk_flags_inplace(result: Dict[str, Any]) -> None:
    """evidence / risk_flags 必须是数组；兼容 JSON 字符串、单对象、字典等。"""
    raw_ev = result.get("evidence")
    raw_rf = result.get("risk_flags")
    ev = _coerce_evidence_to_list(raw_ev)
    rf = _coerce_risk_flags_to_list(raw_rf)
    touched = (ev is not raw_ev) or (rf is not raw_rf)
    result["evidence"] = ev
    result["risk_flags"] = rf
    if touched:
        tag = "evidence_or_risk_flags_shape_normalized"
        if tag not in rf:
            result["risk_flags"] = list(rf) + [tag]


def _fold_canonical_keys(d: Dict[str, Any], canonical: List[str]) -> Dict[str, Any]:
    """把仅大小写/首尾空格不同的键补一条规范键（不删原键，便于调试）。"""
    merged = dict(d)
    lower_lookup = {str(k).strip().lower(): k for k in d}
    for c in canonical:
        if c in merged:
            continue
        lk = c.lower()
        if lk in lower_lookup:
            orig = lower_lookup[lk]
            merged[c] = merged.get(orig)
    return merged


def _normalize_scores_confidence_inplace(result: Dict[str, Any]) -> None:
    """补全 scores/confidence 的 8 个规范键；兼容列表顺序、短键名、误把 cap_req 写在 confidence 里等情况。"""
    scores_any = result.get("scores")
    conf_any = result.get("confidence")

    if isinstance(scores_any, list) and len(scores_any) == len(DIM_KEYS):
        try:
            result["scores"] = {DIM_KEYS[i]: scores_any[i] for i in range(len(DIM_KEYS))}
        except (TypeError, ValueError, IndexError):
            pass
        scores_any = result.get("scores")

    if isinstance(conf_any, list) and len(conf_any) == len(CONF_KEYS):
        try:
            result["confidence"] = {CONF_KEYS[i]: float(conf_any[i]) for i in range(len(CONF_KEYS))}
        except (TypeError, ValueError, IndexError):
            pass
        conf_any = result.get("confidence")

    if not isinstance(scores_any, dict) or not isinstance(conf_any, dict):
        return

    scores: Dict[str, Any] = _fold_canonical_keys(dict(scores_any), DIM_KEYS)
    conf: Dict[str, Any] = _fold_canonical_keys(dict(conf_any), CONF_KEYS)

    touched = False

    for short, req in _SHORT_TO_REQ.items():
        if req not in scores and short in scores:
            try:
                scores[req] = float(scores[short])
                touched = True
            except (TypeError, ValueError):
                pass

    for sk, ck in _SHORT_TO_CONF.items():
        if ck not in conf and sk in conf:
            try:
                v = float(conf[sk])
            except (TypeError, ValueError):
                continue
            if 0 <= v <= 1:
                conf[ck] = v
                touched = True

    for rk, ck in _REQ_TO_CONF.items():
        if ck in conf:
            continue
        if rk not in conf:
            continue
        try:
            v = float(conf[rk])
        except (TypeError, ValueError):
            continue
        if 0 <= v <= 1:
            conf[ck] = v
            touched = True

    for ck in CONF_KEYS:
        if ck in conf:
            continue
        conf[ck] = 0.55
        touched = True

    if touched:
        rf = result.setdefault("risk_flags", [])
        if isinstance(rf, list) and "scores_confidence_keys_normalized" not in rf:
            rf.append("scores_confidence_keys_normalized")

    result["scores"] = scores
    result["confidence"] = conf


def _eval_rules_block() -> Dict[str, Any]:
    return {
        "score_range": [0, 100],
        "confidence_range": [0, 1],
        "must_ground_on_evidence": True,
        "must_output_json_only": True,
        "dimensions": DIM_KEYS,
        "confidence_keys": CONF_KEYS,
        "evidence_max_items": 8,
        "evidence_each_max_chars_cn": 40,
        "risk_flags_max_items": 8,
        "risk_flags_each_max_chars_cn": 35,
        "output_style": "简短凝练，禁止冗长复述输入文本",
    }


def build_prompt_payload(job_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task": (
            "根据 job 与 evaluation_spec、rules 评估八维；evidence、risk_flags 须简短凝练（见 rules 条数与字数上限）。"
            "结合公司方向与规模/薪资（1万月薪基准）做合理调整，输出 JSON。"
        ),
        "evaluation_spec": EVAL_SPEC_COMPACT,
        "rules": _eval_rules_block(),
        "job": job_payload,
    }


REVIEW_TASK_TEXT = (
    "你是评估复核员。输入含 job、evaluation_spec、rules、primary_assessment。"
    "对照 job 与规范判断初评是否合理；不合理则修正 scores/confidence、重写为简短 evidence/risk_flags（遵守 rules 条数与字数上限）；合理可微调。"
    "输出 JSON：job_id、scores、confidence、evidence、risk_flags。risk_flags 追加一条≤20字复核结论如「复核:合理」或「复核:已调分」。"
)


def build_review_payload(job_payload: Dict[str, Any], primary_result: Dict[str, Any]) -> Dict[str, Any]:
    """复核请求：在初评相同证据包上附带 primary 的完整评估结果，供 review 模型判断并必要时修正。"""
    snapshot = {
        "scores": primary_result.get("scores"),
        "confidence": primary_result.get("confidence"),
        "evidence": primary_result.get("evidence"),
        "risk_flags": primary_result.get("risk_flags"),
    }
    return {
        "task_review": REVIEW_TASK_TEXT,
        "evaluation_spec": EVAL_SPEC_COMPACT,
        "rules": _eval_rules_block(),
        "job": job_payload,
        "primary_assessment": snapshot,
    }


def llm_json_eval(
    client: OpenAI,
    model: str,
    payload: Dict[str, Any],
    provider: str,
) -> Dict[str, Any]:
    system_prompt = (
        "你是职业能力画像评估器。"
        "严格只输出 JSON 对象，不得输出 markdown/解释文字。"
        "必须遵守 user 消息中的 evaluation_spec（八维定义、计分框架、公司方向与八维偏重、禁忌）与 rules；只能引用 job 内可核对字段与 skills，禁止编造不存在的 JD/技能/边。"
        "输出字段必须包含: job_id,scores,confidence,evidence,risk_flags。"
        "其中 scores 与 confidence 必须是 JSON 对象(键为字符串、值为数字)，不得使用字符串嵌套另一层 JSON。"
        "scores 的键必须与输入 rules.dimensions 完全一致；confidence 的键必须与 rules.confidence_keys 完全一致（8 个 cap_conf_*）。"
        "evidence 与 risk_flags 必须是 JSON 数组；须简短凝练，遵守 user.rules 中 evidence/risk_flags 的条数与单条字数上限，禁止长段复述 job 原文。"
    )
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "stream": False,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    if provider == "qwen":
        kwargs["extra_body"] = {"enable_thinking": False}
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    text = _strip_markdown_json_fence(text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise RuntimeError("模型返回顶层不是 JSON 对象")
    normalize_llm_eval_dict(data)
    return data


def llm_json_review_eval(
    client: OpenAI,
    model: str,
    payload: Dict[str, Any],
    provider: str,
) -> Dict[str, Any]:
    """复核专用：携带 primary_assessment，要求判断合理性并在不合理时修正，输出结构同初评。"""
    system_prompt = (
        "你是职业能力画像复核评估器。"
        "严格只输出 JSON 对象，不得输出 markdown/解释文字。"
        "你必须阅读 user 消息中的 primary_assessment（初评结果）与 job（图谱证据，含公司字段与 evaluation_spec 中的公司方向-八维偏重），并遵守 evaluation_spec、rules。"
        "先判断初评是否合理；不合理则修正 scores/confidence/evidence/risk_flags，合理则可小幅优化。"
        "只能引用 job 内可核对字段与 skills，禁止编造不存在的 JD/技能/边。"
        "输出字段必须包含: job_id,scores,confidence,evidence,risk_flags。"
        "scores 与 confidence 必须为 JSON 对象，键分别与 rules.dimensions、rules.confidence_keys 完全一致；"
        "evidence 与 risk_flags 必须为 JSON 数组，且须简短凝练，遵守 rules 中条数与单条字数上限。"
    )
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "stream": False,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    if provider == "qwen":
        kwargs["extra_body"] = {"enable_thinking": False}
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    text = _strip_markdown_json_fence(text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise RuntimeError("复核返回顶层不是 JSON 对象")
    normalize_llm_eval_dict(data)
    return data


def validate_result(result: Dict[str, Any], job_id: str) -> Tuple[bool, str]:
    required_top = {"job_id", "scores", "confidence", "evidence", "risk_flags"}
    if not required_top.issubset(result.keys()):
        return False, f"缺少顶层字段: {required_top - set(result.keys())}"
    if str(result["job_id"]) != str(job_id):
        return False, "job_id 不匹配"

    scores = result["scores"]
    conf = result["confidence"]
    if not isinstance(scores, dict) or not isinstance(conf, dict):
        return False, "scores/confidence 必须是对象"

    for k in DIM_KEYS:
        if k not in scores:
            return False, f"缺少 score: {k}"
        v = float(scores[k])
        if v < 0 or v > 100:
            return False, f"score 越界: {k}={v}"
        scores[k] = round(v, 2)

    for k in CONF_KEYS:
        if k not in conf:
            return False, f"缺少 confidence: {k}"
        v = float(conf[k])
        if v < 0 or v > 1:
            return False, f"confidence 越界: {k}={v}"
        conf[k] = round(v, 4)

    if not isinstance(result["evidence"], list):
        return False, "evidence 必须是数组"
    if not isinstance(result["risk_flags"], list):
        return False, "risk_flags 必须是数组"
    return True, ""


def needs_review(result: Dict[str, Any], threshold: float) -> bool:
    conf = result.get("confidence", {})
    for k in CONF_KEYS:
        if float(conf.get(k, 0)) < threshold:
            return True
    return False


def merge_results(primary: Dict[str, Any], review: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(primary)
    merged["scores"] = {}
    merged["confidence"] = {}
    for k in DIM_KEYS:
        p = float(primary["scores"][k])
        r = float(review["scores"][k])
        merged["scores"][k] = round(0.4 * p + 0.6 * r, 2)
    for k in CONF_KEYS:
        p = float(primary["confidence"][k])
        r = float(review["confidence"][k])
        merged["confidence"][k] = round(max(p, r), 4)
    merged["evidence"] = (review.get("evidence") or [])[:8] or (primary.get("evidence") or [])[:8]
    merged["risk_flags"] = sorted(list(set((primary.get("risk_flags") or []) + (review.get("risk_flags") or []))))
    merged["fusion"] = {
        "strategy": "0.4_primary_0.6_review",
        "review_had_primary": True,
    }
    return merged


def fetch_jobs_payload(driver: Any, db: str, limit: int, skip: int = 0) -> List[Dict[str, Any]]:
    # 与 write_back_scores 中 job_id 的 coalesce 链保持一致；尽量带出 Job 上常见招聘字段供 LLM 使用
    # skip：跳过前若干条（与 JOB_EVAL_START 对应，START=1 时 skip=0）
    query = """
    MATCH (j:Job)
    WITH j ORDER BY coalesce(j.job_key, j.job_code, coalesce(j.name, j.title), elementId(j)) ASC
    SKIP $skip
    LIMIT $limit
    OPTIONAL MATCH (j)-[r:REQUIRES]->(s)
    WITH j, collect({
      skill_name: coalesce(s.name, '(unknown)'),
      weight: 1.0,
      source: coalesce(r.source, '')
    }) AS skills
    OPTIONAL MATCH (j)-[:TRANSFER_TO]->(j2:Job)
    WITH j, skills, count(j2) AS transfer_edge_count
    OPTIONAL MATCH (j)-[:VERTICAL_UP]->(j3:Job)
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS job_id,
      coalesce(j.job_key, '') AS job_key,
      coalesce(j.job_code, '') AS job_code,
      coalesce(j.name, j.title, '') AS name,
      coalesce(j.title, '') AS title,
      coalesce(j.company, '') AS company,
      coalesce(j.company_detail, '') AS company_detail,
      coalesce(j.company_size, '') AS company_size,
      coalesce(j.company_type, '') AS company_type,
      coalesce(j.demand, '') AS demand,
      coalesce(j.experience_text, '') AS experience_text,
      j.experience_years AS experience_years,
      coalesce(j.industry, '') AS industry,
      coalesce(j.internship_req, '') AS internship_req,
      j.is_core_template AS is_core_template,
      coalesce(j.salary, '') AS salary,
      coalesce(j.location, '') AS location,
      coalesce(j.source_url, '') AS source_url,
      transfer_edge_count,
      count(j3) AS vertical_edge_count,
      skills
    """
    with driver.session(database=db) as session:
        rows = session.run(query, {"limit": int(limit), "skip": max(0, int(skip))})
        return [dict(r) for r in rows]


def write_back_scores(driver, db: str, result: Dict[str, Any], cap_version: str) -> None:
    evidence = result.get("evidence", [])
    risk_flags = result.get("risk_flags", [])

    if not isinstance(evidence, list):
        evidence = [evidence]
    if not isinstance(risk_flags, list):
        risk_flags = [risk_flags]

    evidence_texts = []
    for item in evidence:
        if isinstance(item, str):
            text = item.strip()
        else:
            text = json.dumps(item, ensure_ascii=False)
        if text:
            evidence_texts.append(text[:500])

    risk_texts = []
    for item in risk_flags:
        if isinstance(item, str):
            text = item.strip()
        else:
            text = json.dumps(item, ensure_ascii=False)
        if text:
            risk_texts.append(text[:500])

    query = """
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    SET
      j.cap_req_theory = $cap_req_theory,
      j.cap_req_cross = $cap_req_cross,
      j.cap_req_practice = $cap_req_practice,
      j.cap_req_digital = $cap_req_digital,
      j.cap_req_innovation = $cap_req_innovation,
      j.cap_req_teamwork = $cap_req_teamwork,
      j.cap_req_social = $cap_req_social,
      j.cap_req_growth = $cap_req_growth,
      j.cap_conf_theory = $cap_conf_theory,
      j.cap_conf_cross = $cap_conf_cross,
      j.cap_conf_practice = $cap_conf_practice,
      j.cap_conf_digital = $cap_conf_digital,
      j.cap_conf_innovation = $cap_conf_innovation,
      j.cap_conf_teamwork = $cap_conf_teamwork,
      j.cap_conf_social = $cap_conf_social,
      j.cap_conf_growth = $cap_conf_growth,
      j.cap_evidence = $cap_evidence,
      j.cap_risk_flags = $cap_risk_flags,
      j.cap_version = $cap_version,
      j.cap_updated_at = datetime()
    """
    params = {"job_id": str(result["job_id"]), "cap_version": cap_version}
    params.update(result["scores"])
    params.update(result["confidence"])
    params["cap_evidence"] = evidence_texts[:16]
    params["cap_risk_flags"] = risk_texts[:32]
    with driver.session(database=db) as session:
        session.run(query, params)


def _process_job_worker(
    idx: int,
    total: int,
    job: Dict[str, Any],
    cfg: AppConfig,
    need_llm: bool,
    primary_client: Any,
    primary_model: str,
    review_client: Any,
    review_model: str,
    dry_run: bool,
    driver: Any,
    neo4j_db: str,
    cap_version: str,
    log_lock: threading.Lock,
) -> Dict[str, Any]:
    """处理单条岗位（线程池内调用）。返回 idx、ok、jsonl 一行、是否触发复核等。"""
    job_id = str(job["job_id"])
    reviewed = 0
    try:
        if _job_key_is_inferred(job):
            with log_lock:
                print(
                    f"[{idx}/{total}] 跳过 LLM（job_key 以 inferred 结尾），输出全零占位 {job_id}",
                    flush=True,
                )
            final_result = build_inferred_zero_result(job_id)
            valid0, msg0 = validate_result(final_result, job_id)
            if not valid0:
                raise RuntimeError(f"推断占位结果校验失败: {msg0}")
        else:
            if primary_client is None or review_client is None:
                raise RuntimeError("需要调用 LLM 但未初始化客户端")
            payload = build_prompt_payload(job)
            with log_lock:
                print(
                    f"[{idx}/{total}] 调用 primary({cfg.primary_provider})，等待响应… {job_id}",
                    flush=True,
                )
            primary_result = llm_json_eval(
                client=primary_client,
                model=primary_model,
                payload=payload,
                provider=cfg.primary_provider,
            )
            primary_result["job_id"] = job_id
            valid, msg = validate_result(primary_result, job_id)
            if not valid:
                raise RuntimeError(f"primary 校验失败: {msg}")

            final_result = primary_result
            if needs_review(primary_result, cfg.review_conf_threshold):
                reviewed = 1
                review_payload = build_review_payload(job, primary_result)
                with log_lock:
                    print(
                        f"[{idx}/{total}] 调用 review({cfg.review_provider})（含 primary 结果复核），等待响应… {job_id}",
                        flush=True,
                    )
                review_result = llm_json_review_eval(
                    client=review_client,
                    model=review_model,
                    payload=review_payload,
                    provider=cfg.review_provider,
                )
                review_result["job_id"] = job_id
                valid2, msg2 = validate_result(review_result, job_id)
                if valid2:
                    final_result = merge_results(primary_result, review_result)
                else:
                    primary_result.setdefault("risk_flags", []).append(f"review_invalid:{msg2}")
                    final_result = primary_result

        if not dry_run:
            write_back_scores(driver, neo4j_db, final_result, cap_version)

        line = json.dumps(final_result, ensure_ascii=False)
        return {
            "idx": idx,
            "ok": True,
            "line": line,
            "reviewed": reviewed,
            "job_id": job_id,
        }
    except Exception as exc:
        err = {"job_id": job_id, "error": str(exc), "ts": datetime.now(timezone.utc).isoformat()}
        with log_lock:
            print(f"[{idx}/{total}] 失败: {job_id} -> {exc}", file=sys.stderr, flush=True)
        return {
            "idx": idx,
            "ok": False,
            "line": json.dumps(err, ensure_ascii=False),
            "reviewed": 0,
            "job_id": job_id,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="职业能力画像批量评估（条数与起点可由 .env 控制）")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="处理条数；不设则读 JOB_EVAL_LIMIT，未配置时默认 200",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="从第几条开始（1-based，含该条）；不设则读 JOB_EVAL_START，未配置时默认 1",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅生成结果文件，不写回Neo4j")
    parser.add_argument("--env", type=str, default=".env", help="环境变量文件路径")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="并发线程数（1=串行）；不设则从环境变量 JOB_EVAL_WORKERS 读取，未设置时默认 3；过大易触发 API 限流",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=f"job_eval_results_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl",
        help="输出jsonl文件",
    )
    args = parser.parse_args()

    load_dotenv_if_exists(args.env)
    if args.workers is not None:
        workers = max(1, min(int(args.workers), 32))
    else:
        workers = max(1, min(int(os.getenv("JOB_EVAL_WORKERS", "3")), 32))
    if args.limit is not None:
        batch_limit = max(1, int(args.limit))
    else:
        batch_limit = max(1, int(os.getenv("JOB_EVAL_LIMIT", "200")))
    if args.start is not None:
        batch_start = max(1, int(args.start))
    else:
        batch_start = max(1, int(os.getenv("JOB_EVAL_START", "1")))
    batch_skip = batch_start - 1
    cfg = get_config()

    if not cfg.neo4j_password:
        print("缺少 NEO4J_PASSWORD，无法连接图数据库", file=sys.stderr)
        return 1

    driver = GraphDatabase.driver(cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password))
    jobs = fetch_jobs_payload(driver, cfg.neo4j_database, batch_limit, batch_skip)
    if not jobs:
        print("未获取到 Job 数据，请检查 Neo4j 连接或标签。", file=sys.stderr)
        return 1

    need_llm = any(not _job_key_is_inferred(j) for j in jobs)
    primary_client = review_client = None
    primary_model = review_model = ""
    if need_llm:
        primary_client, primary_model = build_openai_client(cfg.primary_provider, cfg)
        review_client, review_model = build_openai_client(cfg.review_provider, cfg)

    print(
        f"开始处理 {len(jobs)} 条岗位（START={batch_start} LIMIT={batch_limit} SKIP={batch_skip}），workers={workers}，need_llm={need_llm} "
        f"primary={cfg.primary_provider} review={cfg.review_provider} "
        f"(LLM_TIMEOUT_SECONDS={_llm_http_timeout_seconds():.0f}s)",
        flush=True,
    )

    log_lock = threading.Lock()
    outcomes: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _process_job_worker,
                idx,
                len(jobs),
                job,
                cfg,
                need_llm,
                primary_client,
                primary_model,
                review_client,
                review_model,
                args.dry_run,
                driver,
                cfg.neo4j_database,
                cfg.cap_version,
                log_lock,
            )
            for idx, job in enumerate(jobs, start=1)
        ]
        for fut in as_completed(futures):
            outcomes.append(fut.result())

    outcomes.sort(key=lambda x: int(x["idx"]))
    ok_count = sum(1 for o in outcomes if o["ok"])
    fail_count = len(outcomes) - ok_count
    review_count = sum(int(o.get("reviewed", 0)) for o in outcomes)

    with open(args.output, "w", encoding="utf-8") as fw:
        for o in outcomes:
            fw.write(o["line"] + "\n")

    driver.close()
    print(
        f"处理完成: success={ok_count}, review={review_count}, fail={fail_count}, "
        f"workers={workers}, start={batch_start}, limit={batch_limit}, output={args.output}, dry_run={args.dry_run}"
    )
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

