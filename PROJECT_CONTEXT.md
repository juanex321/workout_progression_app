# Shared Project Context (Agent-Agnostic)

Last updated: 2026-04-05
Repository: `workout_progression_app`

## Purpose

Workout tracking app with adaptive progression. Users log sets, submit muscle-group feedback, and the app adjusts future volume, rep targets, and RIR guidance based on recent performance and recovery.

## Active Stack

- Next.js frontend in `frontend/`
- FastAPI backend in `api/`
- SQLAlchemy ORM
- PostgreSQL via `DATABASE_URL` in hosted environments
- SQLite fallback for local scripts/dev flows
- Alembic for schema migrations

## Core Files

- `frontend/src/app/page.tsx`: primary UI route
- `frontend/src/components/`: workout UI components
- `frontend/src/hooks/`: React Query hooks for frontend data flow
- `api/index.py`: FastAPI entry point
- `api/routes/`: sessions, exercises, feedback, and progression endpoints
- `api/db.py`: API runtime DB config and models
- `api/services.py`: API-layer CRUD/service logic
- `progression.py`: set/rep recommendation and deload logic
- `rir_progression.py`: RIR progression and feedback-trend logic
- `plan.py`: session exercise rotation and defaults
- `db.py`: root DB models/session helper used by scripts and tests
- `init_db.py`: initial schema/seed setup

## Database Model Snapshot

Defined in `db.py` / `api/db.py`:

- `Program`
- `Workout`
- `Exercise`
- `WorkoutExercise`
- `Session`
- `Set`
- `Feedback`

## Progression System

- Primary adjustment: sets up/down from feedback trends
- Secondary adjustment: reps increase when performance supports it
- Intensity guidance: RIR progression from session history
- Deload path exists for overreaching patterns
- Weights are generally user-driven, not auto-progressed aggressively

Main entry points:

- `progression.py::recommend_weights_and_reps`
- `progression.py::adjust_sets_based_on_feedback`
- `progression.py::should_deload_by_muscle_group`
- `rir_progression.py::get_rir_for_muscle_group`
- `rir_progression.py::calculate_rir_from_feedback`

## Runtime and Env

Frontend:

- `frontend` runs on Vercel
- `frontend/next.config.js` rewrites `/api/*` to `BACKEND_URL`

Backend:

- `api` runs as FastAPI
- Hosted DB should be supplied through `DATABASE_URL`

Root `db.py` URL resolution:

1. `DATABASE_URL`
2. local SQLite fallback at `workout.db`

Useful commands:

- `pip install -r api/requirements.txt`
- `python init_db.py`
- `uvicorn api.index:app --reload --port 8000`
- `cd frontend && npm run dev`
- `pytest test_set_progression.py`

## Working Conventions

- Keep frontend changes inside `frontend/`
- Keep API request/response work in `api/routes/` and `api/services.py`
- Keep business rules in `progression.py` / `rir_progression.py`
- Use `with get_session() as db:` for root DB operations
- Shared root progression modules must remain safe to import from the API runtime

## Risks / Attention Points

- `progression.py` and `rir_progression.py` must stay consistent
- Hosted Postgres and local SQLite paths both exist, so DB changes need coverage for both
- Import resolution matters: API runtime should use `api/db.py`, not root `db.py`

## Quick Orientation Path

1. Read `README.md`
2. Inspect `frontend/src/app/page.tsx` and related hooks/components
3. Trace the matching `api/routes/*` handler and `api/services.py`
4. Validate progression changes in `progression.py` and `rir_progression.py`
5. Run the relevant frontend/API/test checks
