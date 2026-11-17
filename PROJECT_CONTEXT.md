# Shared Project Context (Agent-Agnostic)

Last updated: 2026-11-17
Repository: `workout_progression_app`

## Purpose

Workout tracking app with adaptive progression. Users log sets, submit muscle-group feedback, and the app adjusts future volume and rep targets based on recent performance and recovery. Every set is trained to failure - there is no RIR phase system or intensity guidance.

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
- `progression.py`: set/rep recommendation logic
- `plan.py`: session exercise rotation and defaults
- `db.py`: root DB models/session helper used by scripts and tests
- `init_db.py`: initial schema/seed setup (root/scripts)
- `api/bootstrap.py`: explicit API-side DB init (`python -m api.bootstrap`): tables, indexes, seed data
- `scripts/package_vercel_api.py`: builds the allowlisted API folder for hand deploys to Vercel

## Database Model Snapshot

Defined in `db.py` / `api/db.py`:

- `Program`
- `Workout`
- `Exercise`
- `WorkoutExercise`
- `Session`
- `Set`
- `Feedback` (includes nullable `recovery_days`: days until soreness from the previous exposure cleared; 0 = never sore)
- `SetDraft` (server-side autosave of in-progress sets)

## Progression System

- Every set is trained to failure within a fixed rep range - no RIR phases, no
  automatic deload/wave-reset. This was removed 2026-07-23; see the "Remove RIR
  phase system" commit if the history is ever needed.
- Primary adjustment: sets up/down from feedback trends (bounded +/-1 per session)
- Secondary adjustment: reps increase by 1 when performance supports it
- Weights are generally user-driven, not auto-progressed aggressively
- Soreness is asked before the session. With "Healed a while ago" the user also
  gives recovery days; otherwise `derive_recovery_days` infers them from days
  since the muscle was last trained. Fast or slow recovery feeds today's set count.

Main entry points:

- `progression.py::recommend_weights_and_reps`
- `progression.py::adjust_sets_based_on_feedback`

## Runtime and Env

Hosting details and the deploy procedure are in `HOSTING_MIGRATION.md`.

Frontend:

- `frontend` runs on Vercel (project `workout-progression-app`), auto-deployed from Git `main`
- `frontend/next.config.js` rewrites `/api/*` to `BACKEND_URL` at build time
- Initial load uses one bootstrap request, `GET /api/workout-data`, which fills the per-session React Query cache

Backend:

- `api` runs as FastAPI on Vercel (project `workout-progression-api-candidate`, alias
  `workout-progression-api-candidate.vercel.app`), region `iad1`, Fluid compute
- **Not Git-connected**: API changes must be repackaged with `scripts/package_vercel_api.py`
  and deployed by hand after merging, or production keeps running the old API
- Database: Neon Postgres via `DATABASE_URL` (Production only; Preview has none, so add a
  Neon test-branch secret before preview testing)
- `SKIP_DB_INIT=true` skips create_all/indexes/seed on startup; `ensure_schema_columns()`
  still adds new nullable columns. Other schema changes need an Alembic migration
- Render was the API host until 2026-10-16 and is retired

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
- Keep business rules in `progression.py`
- Use `with get_session() as db:` for root DB operations
- Shared root progression modules must remain safe to import from the API runtime

## Risks / Attention Points

- Hosted Postgres and local SQLite paths both exist, so DB changes need coverage for both
- Import resolution matters: API runtime should use `api/db.py`, not root `db.py`
- Frontend and API deploy separately; a merged API change is not live until it is deployed by hand
- Run root-model and API-model test modules in separate pytest processes (both use bare `db`/`services` imports)

## Quick Orientation Path

1. Read `README.md`
2. Inspect `frontend/src/app/page.tsx` and related hooks/components
3. Trace the matching `api/routes/*` handler and `api/services.py`
4. Validate progression changes in `progression.py`
5. Run the relevant frontend/API/test checks
