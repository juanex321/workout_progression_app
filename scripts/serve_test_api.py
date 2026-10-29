"""Serve disposable workout fixtures for browser regression checks on port 8000."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    # Always override inherited credentials: this server must never use real data.
    with tempfile.TemporaryDirectory(prefix="workout-browser-") as directory:
        os.environ["DATABASE_URL"] = "sqlite:///" + (Path(directory) / "test.db").as_posix()
        os.environ["SKIP_DB_INIT"] = "false"
        from api.index import app
        from db import init_db, seed_default_data, get_session, Workout
        from services import get_current_session, complete_session
        import uvicorn

        init_db()
        seed_default_data()
        with get_session() as db:
            workout = db.query(Workout).first()
            first = get_current_session(db, workout.id)
            second = complete_session(db, first.id)
            complete_session(db, second.id)
        uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
