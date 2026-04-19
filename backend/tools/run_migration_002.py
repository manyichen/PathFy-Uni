"""执行 migrations/002_student_resume_cap_conf.sql（幂等：列已存在则跳过）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pymysql
import pymysql.err

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    d: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def main() -> int:
    env = load_env(BACKEND_ROOT / ".env")
    sql_path = BACKEND_ROOT / "migrations" / "002_student_resume_cap_conf.sql"
    raw = sql_path.read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    sql = "\n".join(lines).strip()
    if not sql:
        print("empty migration sql", file=sys.stderr)
        return 1

    conn = pymysql.connect(
        host=env["MYSQL_HOST"],
        port=int(env.get("MYSQL_PORT", "3306")),
        user=env["MYSQL_USER"],
        password=env["MYSQL_PASSWORD"],
        database=env["MYSQL_DATABASE"],
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("OK: migration 002 applied (cap_conf_* columns added).")
        return 0
    except pymysql.err.OperationalError as ex:
        code = ex.args[0] if ex.args else 0
        if code == 1060:
            print("SKIP: columns already exist (Duplicate column name).")
            return 0
        print(f"ERR: {ex}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
