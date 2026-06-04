#!/usr/bin/env python3
"""校验 competitions.csv 中 official_url 是否可访问。"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "datasets" / "master" / "competitions.csv"
TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def check_url(url: str) -> tuple[bool, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            code = getattr(resp, "status", resp.getcode())
            if 200 <= code < 400:
                return True, str(code)
            return False, str(code)
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig", newline="")))
    ok_count = 0
    for row in rows:
        rid = row.get("competition_id", "?")
        url = (row.get("official_url") or "").strip()
        if not url:
            print(f"[FAIL] {rid}\t(empty url)\t{row.get('competition_name','')}")
            continue
        ok, detail = check_url(url)
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {rid}\t{detail}\t{url}")
        if ok:
            ok_count += 1
    total = len(rows)
    print(f"\n{ok_count}/{total} URLs reachable")
    return 0 if ok_count == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
