# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Use `PROJECT_CONTEXT.md` as the canonical, shared project memory for this repository.

## Architecture Overview

This repository has one active application stack:

- `frontend/` - Next.js 16 + React 19 + TypeScript + Tailwind CSS 4, deployed to Vercel
  - `frontend/src/app/page.tsx` - single-page workout UI
  - `frontend/next.config.js` - rewrites `/api/**` to `BACKEND_URL` (default `http://localhost:8000`)
  - `frontend/src/components/` - UI components
  - `frontend/src/hooks/` - React Query hooks for API access
- `api/` - FastAPI backend, deployed via `render.yaml`
  - `api/index.py` - FastAPI entry point
  - `api/db.py` - API DB config and models
  - `api/services.py` - API-layer service functions
  - `api/routes/` - route handlers for sessions, exercises, feedback, and progression
  - `api/schemas.py` - Pydantic request/response models
- Root shared modules - imported by the API at runtime
  - `progression.py`
  - `plan.py`
- Root support modules - used by local scripts/tests/maintenance
  - `db.py`
  - `services.py`
  - `init_db.py`
  - `scripts/`

Important import detail:

- `api/index.py` inserts `api/` ahead of the repo root on `sys.path`
- Bare imports like `from db import ...` resolve to `api/db.py` inside the API runtime
- Shared modules such as `progression.py` still import `db` by bare name, so they pick up `api/db.py` when running under the API

## Development Commands

### Backend
```bash
pip install -r api/requirements.txt
uvicorn api.index:app --reload --port 8000
curl http://localhost:8000/api/health
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

Set `BACKEND_URL` when the API is not on `http://localhost:8000`.

### Root scripts and tests
```bash
python init_db.py
pytest test_set_progression.py
python test_set_progression.py
python test_exercise_history_summary.py
```

## Key Conventions

- Keep UI logic in `frontend/`
- Keep API orchestration in `api/`
- Keep progression logic in `progression.py`
- Use `with get_session() as db:` for root DB operations
- Database URL resolution in root `db.py`: `DATABASE_URL` env var, then local SQLite fallback
- The API should use `api/db.py`, not root `db.py`

## Progression System

Every set is trained to failure - there is no RIR phase system and no automatic
deload. Key points:

- Sets adjust by recent feedback with a bounded plus/minus 1 change per session
- Rep target formula: `target_reps = last_reps + 1`, clamped to `[MIN_TARGET_REPS, MAX_TARGET_REPS]`
- Weight is carried forward unchanged; the user decides when to add weight
