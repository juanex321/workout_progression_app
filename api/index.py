import sys
from pathlib import Path

# Ensure the api directory is on the Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

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
