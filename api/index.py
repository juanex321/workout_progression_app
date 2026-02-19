import sys
from pathlib import Path

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

app = FastAPI(title="Workout Progression API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(exercises.router, prefix="/api", tags=["exercises"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(progression.router, prefix="/api", tags=["progression"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
