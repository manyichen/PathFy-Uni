"""执行 migrations/005_match_runs.sql（建表语句幂等）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pymysql

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def split_sql(sql: str) -> list[str]:
    stmts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        if s.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
    if buf:
        stmt = "\n".join(buf).strip()
        if stmt:
            stmts.append(stmt)
    return stmts


def main() -> int:
    env = load_env(BACKEND_ROOT / ".env")
    sql_path = BACKEND_ROOT / "migrations" / "005_match_runs.sql"
    statements = split_sql(sql_path.read_text(encoding="utf-8"))
    if not statements:
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
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()
        print("OK: migration 005 applied.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERR: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
