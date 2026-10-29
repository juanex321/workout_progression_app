# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Use `PROJECT_CONTEXT.md` as the canonical, shared project memory for this repository.

## Architecture

Important import detail:

- `api/index.py` inserts `api/` ahead of the repo root on `sys.path`
- Bare imports like `from db import ...` resolve to `api/db.py` inside the API runtime
- Shared modules such as `progression.py` still import `db` by bare name, so they pick up `api/db.py` when running under the API

## Development Commands

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
