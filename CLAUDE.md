# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Use `PROJECT_CONTEXT.md` as the canonical, shared project memory for this repository.

## Architecture Overview

This project has two distinct stacks that coexist:

**Legacy Streamlit app** (root-level Python files):
- `app.py` — Streamlit UI, session-state driven workflow
- `db.py` — SQLAlchemy engine + ORM models, `get_session()` context manager
- `services.py` — CRUD/service layer (sessions, sets, feedback)
- `progression.py` — set/rep recommendation and deload trigger logic
- `rir_progression.py` — RIR progression and feedback-trend logic
- `plan.py` — exercise rotation and session composition

**Active full-stack app** (current focus):
- `api/` — FastAPI backend, deployed to Render (free tier) via `render.yaml`
  - `api/index.py` — FastAPI app entry point, router registration, startup logic
  - `api/db.py` — DB engine/session for the API, with retry logic for Neon cold starts
  - `api/services.py` — API-layer service functions
  - `api/routes/` — Route handlers: `sessions.py`, `exercises.py`, `feedback.py`, `progression.py`
  - `api/schemas.py` — Pydantic request/response schemas
  - **Important**: `api/index.py` adds root to `sys.path` so shared modules (`progression.py`, `rir_progression.py`, `plan.py`) are imported from the project root — there are no duplicate copies in `api/`.
- `frontend/` — Next.js 16 + React 19 + TypeScript + Tailwind CSS 4, deployed to Vercel (free tier)
  - `frontend/src/app/page.tsx` — Single-page workout UI
  - `frontend/next.config.js` — Rewrites `/api/**` to `BACKEND_URL` (default `http://localhost:8000`)
  - `frontend/src/components/` — UI components (`MuscleGroupCard`, `ExerciseSets`, `SetRow`, `FeedbackForm`, `SorenessSelector`, etc.)
  - `frontend/src/hooks/` — React Query hooks wrapping API calls (`useSessionData`, `useLogSet`, `useFeedback`, etc.)
- **Database** — Neon Postgres (free tier), connected via `DATABASE_URL` env var

## Development Commands

### Backend (FastAPI)
```bash
# Install API dependencies
pip install -r api/requirements.txt

# Run locally (from project root)
uvicorn api.index:app --reload --port 8000

# Health check
curl http://localhost:8000/api/health
```

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev       # dev server on :3000
npm run build
npm run lint
```

Set `BACKEND_URL` env var when the API is not on `http://localhost:8000`.

### Legacy Streamlit app
```bash
pip install -r requirements.txt
python init_db.py       # first-time DB setup
streamlit run app.py
python check_db.py      # inspect DB state
python backup_db.py backup
python backup_db.py restore <backup_file>
```

### Tests
```bash
# Progression logic tests (uses unittest.mock, run with pytest or directly)
pytest test_set_progression.py
python test_set_progression.py
```

## Key Conventions

- All DB operations: `with get_session() as db:` — never bypass the context manager
- UI state: `st.session_state` (Streamlit) or React Query cache (Next.js frontend)
- Business logic lives in `services.py`/`progression.py`/`rir_progression.py`, not in UI code
- Shared Python modules (`progression.py`, `rir_progression.py`, `plan.py`) are used by both the legacy app and the API — changes affect both
- Database URL resolution order: `DATABASE_URL` env var → Streamlit secrets → SQLite fallback (`workout.db`)
- When the API fails to connect to Postgres on startup, it automatically falls back to SQLite

## Progression System

See `MEMORY.md` and `PROJECT_CONTEXT.md` for the full spec. Key points:
- **Sets** are adjusted by feedback (soreness/pump/workload): bounded ±1 per session
- **RIR** is driven by session count (mesocycle position), not feedback directly
- **Reps** formula: `target_reps = last_reps + 1 + (last_rir - current_rir)`
- Deload is triggered only when at RIR 0 AND feedback indicates overtraining
- `progression.py` and `rir_progression.py` must stay consistent with each other
