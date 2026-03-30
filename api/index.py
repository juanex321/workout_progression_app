import sys
from pathlib import Path
import traceback

_here = Path(__file__).resolve().parent   # .../api/
_root = _here.parent                       # .../workout_progression_app/

# api/ first — api-specific modules (deps, schemas, routes, db, services) take priority.
# root second — shared modules (progression, rir_progression, plan) are imported
# from there directly, so there are no local copies that can drift out of sync.
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_here))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import sessions, exercises, feedback, progression
from db import (
    _hosted_runtime_detected,
    get_database_runtime_info,
    init_db,
    seed_default_data,
    switch_to_sqlite_fallback,
)

app = FastAPI(title="Workout Progression API")
STARTUP_ERROR: str | None = None

import os

_frontend_url = os.environ.get("FRONTEND_URL", "")
_allowed_origins = ["http://localhost:3000", "http://localhost:3001"]
if _frontend_url:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(exercises.router, prefix="/api", tags=["exercises"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(progression.router, prefix="/api", tags=["progression"])


@app.on_event("startup")
def startup():
    # Create tables and seed baseline data for fresh deployments.
    global STARTUP_ERROR
    try:
        init_db()
        seed_default_data()
        STARTUP_ERROR = None
    except Exception as exc:
        STARTUP_ERROR = f"{type(exc).__name__}: {exc}"
        print("Startup initialization failed:")
        print(STARTUP_ERROR)
        print(traceback.format_exc())
        if _hosted_runtime_detected():
            # In production, surface the error rather than masking it with SQLite.
            raise
        # Local dev only: keep service available while DB credentials are being fixed.
        try:
            switch_to_sqlite_fallback(STARTUP_ERROR)
            init_db()
            seed_default_data()
        except Exception as fallback_exc:
            STARTUP_ERROR = f"{STARTUP_ERROR} | sqlite_fallback_failed: {type(fallback_exc).__name__}: {fallback_exc}"


@app.get("/api/health")
def health_check():
    payload = {"status": "ok", "database": get_database_runtime_info()}
    if STARTUP_ERROR:
        payload["startup_error"] = STARTUP_ERROR
    return payload
