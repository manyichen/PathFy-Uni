"""按需联网：岗位公开信息摘要（用户点击触发，JobTitle 缓存）。"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

import requests
from flask import current_app

from app.domains.report.llm import _call_openai_compatible
from app.domains.report.utils import truthy
from app.infrastructure.llm import strip_json_fence
from app.infrastructure.privacy import redact_payload

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_CACHE_DIR = _BACKEND_ROOT / "private_cache" / "track_public_info"


def _cache_path(job_title: str) -> Path:
    key = hashlib.sha256(job_title.strip().lower().encode("utf-8")).hexdigest()[:32]
    return _CACHE_DIR / f"{key}.json"


def _cache_ttl_days() -> int:
    try:
        return int(current_app.config.get("CAREER_PUBLIC_INFO_CACHE_DAYS", 14))
    except RuntimeError:
        return 14


def _max_summary_chars() -> int:
    try:
        return int(current_app.config.get("CAREER_PUBLIC_INFO_MAX_SUMMARY_CHARS", 300))
    except RuntimeError:
        return 300


def _max_search_input_chars() -> int:
    try:
        return int(current_app.config.get("CAREER_PUBLIC_SEARCH_MAX_CHARS", 1200))
    except RuntimeError:
        return 1200


def _read_cache(job_title: str) -> Dict[str, Any] | None:
    path = _cache_path(job_title)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expires = str(data.get("expires_at") or "")
    if expires:
        try:
            if datetime.utcnow() > datetime.strptime(expires, "%Y-%m-%d %H:%M:%S"):
                return None
        except ValueError:
            pass
    return data


def _write_cache(job_title: str, payload: Dict[str, Any]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(job_title)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")


def _truncate(text: str, limit: int) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(t) <= limit:
        return t
    return t[: max(0, limit - 1)].rstrip() + "…"


def _search_snippets(job_title: str) -> tuple[str, str]:
    """返回 (snippets_text, provider_name)。控制检索输入/输出长度。"""
    query = _truncate(f"{job_title} 招聘 就业 岗位 趋势", 80)
    max_in = _max_search_input_chars()

    api_key = str(current_app.config.get("SERPER_API_KEY") or "").strip()
    if api_key:
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 5, "gl": "cn", "hl": "zh-cn"},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            parts: List[str] = []
            for item in (data.get("organic") or [])[:5]:
                if not isinstance(item, dict):
                    continue
                title = _truncate(item.get("title"), 60)
                snippet = _truncate(item.get("snippet"), 120)
                link = str(item.get("link") or "")[:200]
                parts.append(f"- {title} | {snippet} | {link}")
            if parts:
                return _truncate("\n".join(parts), max_in), "serper"
        except requests.RequestException:
            pass

    # 无 Serper 时使用 Jina Reader 搜索（单次 GET，限制响应长度）
    try:
        url = f"https://s.jina.ai/{quote(query)}"
        resp = requests.get(
            url,
            headers={"Accept": "text/plain", "X-Respond-With": "no-content"},
            timeout=25,
        )
        if resp.status_code == 200 and resp.text.strip():
            return _truncate(resp.text, max_in), "jina_reader"
    except requests.RequestException:
        pass

    return "", "none"


def _summarize_with_deepseek(job_title: str, snippets: str) -> Dict[str, Any]:
    api_key = str(current_app.config.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        return {
            "ok": False,
            "reason": "missing DEEPSEEK_API_KEY",
            "summary": "",
            "sources": [],
        }
    max_chars = _max_summary_chars()
    model = str(current_app.config.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat")
    timeout = float(current_app.config.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    user_prompt = (
        f"岗位类别：{job_title}\n"
        f"检索摘录（已截断）：\n{snippets or '（无检索结果）'}\n\n"
        "请仅根据摘录写一段中文摘要，说明近期公开信息中与该岗位相关的动态。"
        f"摘要不超过{max_chars}字。"
        "禁止输出任何 0-100 分、指数、百分比排名。"
        "输出 JSON："
        '{"summary":"...","sources":[{"title":"...","url":"..."}]}，sources 最多 3 条且 url 必须来自摘录。'
    )
    system_prompt = (
        "你是职业信息整理助手。只归纳已有摘录，不编造数据，不输出评分数值。"
    )
    try:
        text = _call_openai_compatible(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model=model,
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
        parsed = json.loads(strip_json_fence(text))
        if not isinstance(parsed, dict):
            raise ValueError("invalid_json")
        summary = _truncate(parsed.get("summary"), max_chars)
        sources: List[Dict[str, str]] = []
        for s in parsed.get("sources") or []:
            if not isinstance(s, dict):
                continue
            sources.append(
                {
                    "title": _truncate(s.get("title"), 80),
                    "url": str(s.get("url") or "")[:300],
                }
            )
            if len(sources) >= 3:
                break
        return {"ok": True, "summary": summary, "sources": sources, "model": model}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "reason": str(exc),
            "summary": "",
            "sources": [],
        }


def fetch_public_info_for_job_title(job_title: str, *, force_refresh: bool = False) -> Dict[str, Any]:
    """
    按 JobTitle 获取外部公开信息摘要。
    默认读缓存；force_refresh=True 时跳过缓存重新检索。
    """
    title = str(job_title or "").strip()
    if not title:
        return {"ok": False, "message": "job_title 不能为空"}

    if not truthy(current_app.config.get("CAREER_ENABLE_PUBLIC_INFO", True)):
        return {"ok": False, "message": "外部公开信息功能已关闭"}

    if not force_refresh:
        cached = _read_cache(title)
        if cached:
            cached["ok"] = True
            cached["from_cache"] = True
            return cached

    snippets, provider = _search_snippets(title)
    if not snippets:
        has_serper = bool(str(current_app.config.get("SERPER_API_KEY") or "").strip())
        if not has_serper:
            hint = (
                "联网检索未成功（已尝试免费通道，可能受网络影响）。"
                "摘要仍由 DeepSeek 生成，但需先拿到网页检索结果；"
                "可在 backend/.env 配置 SERPER_API_KEY 提高成功率，或稍后重试。"
                "说明：DeepSeek API（含 deepseek-chat / deepseek-v4-flash）本身不提供联网搜索，"
                "换模型 ID 不能替代检索服务。"
            )
        else:
            hint = "检索未返回可用内容，请稍后重试或检查 SERPER 配额。"
        return {
            "ok": False,
            "message": hint,
            "job_title": title,
            "search_provider": provider,
        }

    llm = _summarize_with_deepseek(title, snippets)
    if not llm.get("ok"):
        return {
            "ok": False,
            "message": llm.get("reason") or "摘要生成失败",
            "job_title": title,
            "search_provider": provider,
        }

    now = datetime.utcnow()
    expires = now + timedelta(days=_cache_ttl_days())
    payload = {
        "ok": True,
        "job_title": title,
        "summary": llm.get("summary") or "",
        "sources": llm.get("sources") or [],
        "search_provider": provider,
        "llm_model": llm.get("model"),
        "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"),
        "from_cache": False,
        "disclaimer": "外部公开信息摘要，非本系统测算；仅供参考",
        "input_chars": len(snippets),
    }
    _write_cache(title, {k: v for k, v in payload.items() if k != "ok"})
    return payload
