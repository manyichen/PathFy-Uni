#!/usr/bin/env python3
"""深度校验 learning_resources CSV：HTTP 状态 + 页面是否为有效课程/文档（非 404 空壳）。"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "datasets" / "learning_resources_java.csv"
TIMEOUT = 25
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

DEAD_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"页面不存在",
        r"页面未找到",
        r"找不到页面",
        r"课程已下线",
        r"课程不存在",
        r"该课程已关闭",
        r"courseNotFound",
        r"访问的页面不存在",
    ]
]

MOOC_ALIVE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"课程详情",
        r"课程概述",
        r"spContent=",
        r"课程大纲",
        r"授课目标",
    ]
]

MOOC_DEAD_TITLE_HINTS = [
    "优质在线课程学习平台",
    "首页_中国大学MOOC",
]


def fetch(url: str) -> tuple[int | None, str, str | None]:
    req = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
    )
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            code = getattr(resp, "status", resp.getcode())
            raw = resp.read(200_000)
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w-]+)", ct, re.I)
            if m:
                charset = m.group(1)
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return code, text, resp.geturl()
    except HTTPError as exc:
        try:
            body = exc.read(50_000).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return exc.code, body, url
    except URLError as exc:
        return None, "", str(exc.reason)
    except Exception as exc:  # noqa: BLE001
        return None, "", str(exc)


def title_of(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    return m.group(1).strip() if m else ""


def analyze(url: str, html: str, code: int | None) -> tuple[bool, str]:
    if code is None:
        return False, f"网络错误: {html or 'unknown'}"
    if code >= 400:
        return False, f"HTTP {code}"

    for pat in DEAD_PATTERNS:
        if pat.search(html[:12000]):
            return False, f"命中失效特征: {pat.pattern}"

    title = title_of(html)

    if "icourse163.org" in url:
        if any(h in title for h in MOOC_DEAD_TITLE_HINTS):
            return False, f"MOOC 空壳页 title={title[:40]}"
        if not any(p.search(html) for p in MOOC_ALIVE_PATTERNS):
            if not re.search(r"_.*MOOC", title):
                return False, f"无课程内容信号 title={title[:40]}"
        return True, f"HTTP {code} + MOOC课程页"

    if "spring-doc.cn" in url:
        if "Spring Boot" not in html and "spring-boot" not in html.lower():
            return False, "Spring 文档页无 Boot 内容"
        return True, f"HTTP {code} + Spring文档"

    if "acwing.com" in url:
        if "AcWing" not in html and "acwing" not in html.lower():
            return False, "AcWing 页面异常"
        return True, f"HTTP {code} + AcWing"

    if "developer.aliyun.com" in url:
        if "Java" not in html and "java" not in html.lower():
            return False, "阿里云页无 Java 相关内容"
        return True, f"HTTP {code} + 阿里云专题"

    if len(html) < 500:
        return False, "页面内容过短"

    return True, f"HTTP {code}"


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path.is_file():
        print(f"文件不存在: {csv_path}", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        rows.extend(csv.DictReader(f))

    ok_count = 0
    for row in rows:
        rid = row.get("resource_id", "?")
        url = (row.get("resource_url") or "").strip()
        code, html, final_url = fetch(url)
        ok, detail = analyze(url, html, code)
        status = "OK" if ok else "FAIL"
        redirect = f" -> {final_url}" if final_url and final_url != url else ""
        print(f"[{status}] {rid}\t{detail}{redirect}\t{url}")
        if ok:
            ok_count += 1

    total = len(rows)
    print(f"\n{ok_count}/{total} URLs look alive")
    return 0 if ok_count == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
