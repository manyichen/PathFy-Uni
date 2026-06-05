# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PathFy-Uni is a career planning agent for university students: resume → capability portrait (8-dimension) → job exploration → person-job matching → career report → periodic review. It's a university course/competition project.

## Commands

```bash
# Backend (Flask, port 5000)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py                         # dev server

# Frontend (Astro + Svelte, port 4321, /api → Flask proxy)
cd frontend
pnpm install
pnpm dev                              # dev server
pnpm build                            # static build → dist/
pnpm check                            # type-check (astro check)

# Tests (no external services needed)
cd backend
pip install -r requirements-dev.txt
pytest tests/ -q                      # all tests
pytest tests/test_match_coarse.py -q  # single test file

# Graph ETL (Neo4j job graph from recruitment data)
cd generate_graph
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# See generate_graph/README.md for full pipeline
```

Prerequisites: Python 3.11+, Node 18+, pnpm, MySQL 8, Neo4j. Copy `backend/.env.example` → `backend/.env` with real DB creds and API keys.

## Architecture

### Backend (`backend/app/`)

```
core/               Config (env vars), JWT auth (Bearer tokens), unified error handling
db/                 MySQL connection & transactions (PyMySQL, no ORM)
infrastructure/     Cross-domain: Neo4j driver, LLM clients (Ark/DeepSeek/DashScope), Baidu OCR, salary parsing
domains/            Business domains as Flask Blueprints:
  auth/             Register, login, token refresh
  profile/          Resume upload → OCR → 8-dimension scores
  personality/      MBTI test questions & submission
  jobs/             Job search, detail, transition analysis, AI assistant chat
  match/            Person-job matching (Pearson correlation + LLM refinement)
  report/           Career report generation, review cycles, auto-replanning
  graph/            Job graph ETL: Excel import → LLM extraction → Neo4j, promotion edge generation
schemas/            Response contract TypedDicts (reference only)
utils.py            Resume scoring utilities, radar chart helpers
```

- Domains communicate via `infrastructure/` or service modules; routers never import each other directly.
- The app factory is `create_app()` in `backend/app/__init__.py`; `run.py` imports and runs it.

### Frontend (`frontend/src/`)

```
pages/              Astro file-based routes (one .astro per page)
components/         Svelte 5 components, organized by domain (auth/, home/, jobs/, match/, etc.)
lib/api/            Per-domain API clients (auth.ts, jobs.ts, match.ts, report.ts, etc.)
lib/api/http.ts     Shared HTTP helpers with auth header injection
lib/features/       Non-HTTP client logic (e.g., auth/session.ts for token management)
lib/                UI utilities: radar-geometry.ts, profile-portrait-ui.ts
```

Import conventions:
- API calls → `@/lib/api/<domain>` (e.g., `@/lib/api/jobs`)
- Auth state → `@/lib/features/auth/session` (`getToken`, `saveAuth`, etc.)
- Auth API calls → `@/lib/api/auth` (`login`, `register`, `fetchMe`)

### API Response Envelopes (critical — never mix)

The frontend expects two distinct JSON shapes. Adding/modifying endpoints must follow the domain's existing convention:

| Envelope | Domains | Success | Error |
|----------|---------|---------|-------|
| `ok` | auth, jobs, match, report, graph | `{"ok": true, "data": ...}` | `{"ok": false, "message": "..."}` |
| `code` | profile, personality | `{"code": 200, "data": ...}` | `{"code": 4xx, "msg": "..."}` |

Backend helpers: `ok_response()` / `fail_ok()` for "ok" domains; `fail_code()` for "code" domains. Raise `ApiError` with the correct `envelope` kwarg for automatic handling.

### 8-Dimension Capability Framework

The system uses an 8-dimension model aligned across resumes, job requirements, and reports: 理论 (theory), 交叉 (interdisciplinary), 实践 (practice), 数字 (digital), 创新 (innovation), 协作 (collaboration), 社会 (social), 成长 (growth).

In the database, these map to columns like `cap_req_theory`, `cap_req_cross`, etc. in job tables, and corresponding fields in resume/profile tables.

### Matching Pipeline

1. Coarse rank: Pearson correlation on shape similarity + soft surplus scoring (configurable weights in `Config`)
2. Optional LLM refinement: DeepSeek evaluates top-K candidates for explainability
3. Results stored as match snapshots for report generation

### Report Generation

Multi-model LLM orchestration: DeepSeek / 通义 (DashScope) / 豆包 (Ark) for plan generation, review metrics extraction, and optional auto-replanning. Reports support periodic review cycles with trend analysis.

## Database

- MySQL for users, resumes, capability profiles, match snapshots, career reports
- Neo4j for the job graph (positions, skill dimensions, promotion relationships)
- Schema: `backend/schema.sql` + migrations in `backend/migrations/` (numbered 002-005)
- Run migrations with scripts in `backend/tools/run_migration_*.py`
- **Never commit**: SQL dumps with real user/resume data, `.env` files, SSH keys

## Privacy & Data Handling

- Uploaded resumes go to a web-inaccessible directory (`RESUME_UPLOAD_DIR`); OCR extracts text, then files are deleted by default (`DELETE_UPLOADED_RESUME_AFTER_OCR=true`)
- LLM calls: max text lengths are capped (`LLM_MAX_TEXT_CHARS`, `LLM_MAX_RESUME_CHARS`); raw snippet storage is opt-in
- API responses: `Cache-Control: no-store` on all `/api/` paths by default (`API_CACHE_NO_STORE`)
- Privacy mode on by default (`LLM_PRIVACY_MODE=true`)

## Production Deployment

See `deploy/DEPLOY.md`. Topology: Nginx (static files + `/api` reverse proxy) → Gunicorn → Flask, with Supervisor process management. MySQL + Neo4j on the same machine or internal network.

## Key Docs

| Doc | Purpose |
|-----|---------|
| `README.md` | Full project overview, tech stack, local setup |
| `PathFy-Uni项目总体设计文档.md` | Comprehensive system design (Chinese, for thesis/defense) |
| `docs/REFACTOR_ROADMAP.md` | Backend layered architecture |
| `docs/API_CONTRACT.md` | API response envelope specification |
| `docs/auth-audit.md` | Endpoint authentication audit |
| `docs/privacy-security.md` | Privacy & security hardening changelog |
| `docs/smoke-test.md` | Manual pre-release smoke test checklist |
