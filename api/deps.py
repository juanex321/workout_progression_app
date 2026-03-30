import time
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from db import SessionLocal


def get_db():
    """FastAPI dependency that yields a SQLAlchemy session.

    Retries once on OperationalError to handle Neon compute cold-starts:
    the first connection attempt after a period of inactivity may fail while
    the serverless compute node is waking up; a short wait and retry succeeds.
    """
    db = None
    for attempt in range(2):
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            break  # connection validated
        except OperationalError:
            if db is not None:
                db.close()
                db = None
            if attempt == 0:
                time.sleep(2)
            else:
                raise
    try:
        yield db
    finally:
        if db is not None:
            db.close()
