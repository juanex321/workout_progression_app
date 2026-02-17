from db import SessionLocal


def get_db():
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
