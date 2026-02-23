import os
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import NullPool


def _is_truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _hosted_runtime_detected() -> bool:
    hosted_markers = (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_ID",
        "VERCEL",
        "VERCEL_ENV",
        "RENDER",
        "FLY_APP_NAME",
    )
    if any(os.environ.get(marker) for marker in hosted_markers):
        return True

    app_env = os.environ.get("APP_ENV", "").strip().lower()
    env = os.environ.get("ENVIRONMENT", "").strip().lower()
    return app_env == "production" or env == "production"


def _normalize_database_url(url: str) -> str:
    normalized = url.strip()

    # Accept pasted Neon CLI form:
    #   psql 'postgresql://user:pass@host/db?...'
    # and plain quoted strings.
    if normalized.lower().startswith("psql "):
        normalized = normalized[5:].strip()

    if (
        (normalized.startswith("'") and normalized.endswith("'"))
        or (normalized.startswith('"') and normalized.endswith('"'))
    ):
        normalized = normalized[1:-1].strip()

    # If surrounding text still exists, extract the URL portion.
    if "postgresql://" in normalized and not normalized.startswith("postgresql://"):
        normalized = normalized[normalized.index("postgresql://") :]
    if "postgres://" in normalized and not normalized.startswith("postgres://"):
        normalized = normalized[normalized.index("postgres://") :]

    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql://", 1)

    # Only force pg8000 when explicitly requested (e.g. Vercel Python runtime).
    force_pg8000 = _is_truthy_env(os.environ.get("FORCE_PG8000", ""))
    if os.environ.get("VERCEL"):
        force_pg8000 = True
    if (
        force_pg8000
        and normalized.startswith("postgresql://")
        and "+" not in normalized.split("://")[0]
    ):
        normalized = normalized.replace("postgresql://", "postgresql+pg8000://", 1)

    # pg8000 does not support channel_binding; strip if present.
    if normalized.startswith("postgresql+pg8000://") and "channel_binding" in normalized:
        import re

        normalized = re.sub(r"[&?]channel_binding=[^&]*", "", normalized)
        normalized = re.sub(r"\?&", "?", normalized)
        normalized = normalized.rstrip("?")

    return normalized


def _sanitize_database_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return "<invalid-url>"

        host = parsed.hostname or "<unknown-host>"
        database_name = parsed.path.lstrip("/") or "<unknown-db>"
        return f"{parsed.scheme}://{host}/{database_name}"
    except Exception:
        return "<unavailable>"


def get_database_url():
    """Resolve runtime database URL and source."""

    require_database_url = _is_truthy_env(os.environ.get("REQUIRE_DATABASE_URL", ""))
    require_database_url = require_database_url or _hosted_runtime_detected()

    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if raw_url:
        return _normalize_database_url(raw_url), "DATABASE_URL"

    if require_database_url:
        print(
            "WARNING: DATABASE_URL missing in hosted/production runtime; "
            "falling back to SQLite. Set Railway DATABASE_URL to Neon."
        )

    # Fall back to SQLite for local development only.
    db_path = Path(__file__).resolve().parent.parent / "workout.db"
    return f"sqlite:///{db_path}", "sqlite-fallback"


DATABASE_URL, DATABASE_SOURCE = get_database_url()
DATABASE_BOOT_ERROR: Optional[str] = None

try:
    if DATABASE_URL.startswith("postgresql"):
        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,
        )
    else:
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
except Exception as exc:
    DATABASE_BOOT_ERROR = f"{type(exc).__name__}: {exc}"
    print("Database engine initialization failed; falling back to SQLite.")
    print(DATABASE_BOOT_ERROR)
    db_path = Path(__file__).resolve().parent.parent / "workout.db"
    DATABASE_URL = f"sqlite:///{db_path}"
    DATABASE_SOURCE = "sqlite-fallback-engine-error"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
DATABASE_FALLBACK_REASON: Optional[str] = None

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class Program(Base):
    __tablename__ = "programs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    workouts = relationship("Workout", back_populates="program")


class Workout(Base):
    __tablename__ = "workouts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    day_label: Mapped[str] = mapped_column(String, nullable=False)

    program = relationship("Program", back_populates="workouts")
    workout_exercises = relationship("WorkoutExercise", back_populates="workout")


class Exercise(Base):
    __tablename__ = "exercises"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    muscle_group: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    workout_exercises = relationship("WorkoutExercise", back_populates="exercise")


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(Integer, ForeignKey("workouts.id"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    target_sets: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reps: Mapped[int] = mapped_column(Integer, nullable=False)

    workout = relationship("Workout", back_populates="workout_exercises")
    exercise = relationship("Exercise", back_populates="workout_exercises")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(Integer, ForeignKey("workouts.id"), nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sets = relationship("Set", back_populates="session")
    feedbacks = relationship("Feedback", back_populates="session")


class Set(Base):
    __tablename__ = "sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("workout_exercises.id"), nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rir: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    session = relationship("Session", back_populates="sets")


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("workout_exercises.id"),
        nullable=True,
    )
    muscle_group: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    soreness: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pump: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    workload: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    session = relationship("Session", back_populates="feedbacks")


@contextmanager
def get_session():
    """Database session context manager."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(engine)


def switch_to_sqlite_fallback(reason: str, source: str = "sqlite-fallback-runtime-error") -> None:
    """
    Rebind ORM engine/session to local SQLite when primary DB is unavailable.
    """
    global engine, DATABASE_URL, DATABASE_SOURCE, DATABASE_FALLBACK_REASON

    db_path = Path(__file__).resolve().parent.parent / "workout.db"
    DATABASE_URL = f"sqlite:///{db_path}"
    DATABASE_SOURCE = source
    DATABASE_FALLBACK_REASON = reason
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    SessionLocal.configure(bind=engine)


def get_database_runtime_info() -> dict:
    """Safe DB runtime info for diagnostics."""
    is_postgres = DATABASE_URL.startswith("postgresql")
    info = {
        "source": DATABASE_SOURCE,
        "engine": "postgresql" if is_postgres else "sqlite",
        "target": _sanitize_database_url(DATABASE_URL),
    }
    if DATABASE_BOOT_ERROR:
        info["boot_error"] = DATABASE_BOOT_ERROR
    if DATABASE_FALLBACK_REASON:
        info["fallback_reason"] = DATABASE_FALLBACK_REASON
    return info


def seed_default_data():
    """
    Ensure base data exists for first boot in fresh environments.

    This keeps new Railway deployments usable without a manual init step.
    """
    from plan import EXERCISE_MUSCLE_GROUPS

    with get_session() as db:
        # Ensure exercise catalog exists.
        for exercise_name, muscle_group in EXERCISE_MUSCLE_GROUPS.items():
            existing_exercise = (
                db.query(Exercise)
                .filter(Exercise.name.ilike(exercise_name))
                .first()
            )
            if not existing_exercise:
                db.add(Exercise(name=exercise_name, muscle_group=muscle_group))

        # Ensure at least one program + one workout exist.
        program = db.query(Program).first()
        if not program:
            program = Program(name="Full Body IV")
            db.add(program)
            db.flush()

        workout = db.query(Workout).filter(Workout.program_id == program.id).first()
        if not workout:
            db.add(
                Workout(
                    program_id=program.id,
                    name="Week 1 Day 1",
                    day_label="W1D1",
                )
            )
