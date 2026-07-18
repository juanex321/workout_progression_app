import os
import time
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
    Text,
    UniqueConstraint,
    create_engine,
    func,
    text,
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
        raise RuntimeError(
            "DATABASE_URL is not set in a hosted/production environment. "
            "Add your Neon PostgreSQL connection string as DATABASE_URL in Railway."
        )

    # Fall back to SQLite for local development only.
    db_path = Path(__file__).resolve().parent.parent / "workout.db"
    return f"sqlite:///{db_path}", "sqlite-fallback"


DATABASE_URL, DATABASE_SOURCE = get_database_url()
DATABASE_BOOT_ERROR: Optional[str] = None

try:
    if DATABASE_URL.startswith("postgresql"):
        if os.environ.get("VERCEL"):
            # Vercel Python functions are short-lived; avoid keeping sockets open.
            pool_kwargs = {"poolclass": NullPool}
        else:
            pool_kwargs = {
                "pool_pre_ping": True,
                "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE_SECONDS", "1800")),
                "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
                "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "2")),
            }
        engine = create_engine(DATABASE_URL, **pool_kwargs)
    else:
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
except Exception as exc:
    DATABASE_BOOT_ERROR = f"{type(exc).__name__}: {exc}"
    if _hosted_runtime_detected():
        raise RuntimeError(
            f"Database engine initialization failed in production: {DATABASE_BOOT_ERROR}"
        ) from exc
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

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

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
    __table_args__ = (
        UniqueConstraint("session_id", "workout_exercise_id", "set_number", name="uq_set_session_exercise_number"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("workout_exercises.id"), nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rir: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    session = relationship("Session", back_populates="sets")
    workout_exercise = relationship("WorkoutExercise")


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("session_id", "muscle_group", name="uq_feedback_session_muscle"),
    )
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
    workout_exercise = relationship("WorkoutExercise")


# --- Myo Reps models ---

class MyoSession(Base):
    __tablename__ = "myo_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schedule_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    exercise_sessions = relationship("MyoExerciseSession", back_populates="myo_session")


class MyoExerciseSession(Base):
    __tablename__ = "myo_exercise_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    myo_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("myo_sessions.id"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"), nullable=False)
    target_mini_sets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_mini_sets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    workload_feedback: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    myo_session = relationship("MyoSession", back_populates="exercise_sessions")
    exercise = relationship("Exercise")
    activation_set = relationship("MyoActivationSet", back_populates="exercise_session", uselist=False)
    mini_sets = relationship("MyoMiniSet", back_populates="exercise_session", order_by="MyoMiniSet.order_index")


class MyoActivationSet(Base):
    __tablename__ = "myo_activation_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("myo_exercise_sessions.id"), nullable=False, unique=True
    )
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    exercise_session = relationship("MyoExerciseSession", back_populates="activation_set")


class MyoMiniSet(Base):
    __tablename__ = "myo_mini_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("myo_exercise_sessions.id"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    exercise_session = relationship("MyoExerciseSession", back_populates="mini_sets")


class MyoExerciseCalibration(Base):
    """Tracks per-exercise calibration state and progression for myo reps."""
    __tablename__ = "myo_exercise_calibration"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"), nullable=False, unique=True)
    calibrated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_mini_sets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_target: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calibration_sessions_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calibration_mini_sets_sum: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_hard_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    exercise = relationship("Exercise")


@contextmanager
def get_session():
    """Database session context manager with retry for Neon cold starts."""
    max_retries = 3
    retry_delay = 1.0  # seconds

    for attempt in range(max_retries):
        session = SessionLocal()
        try:
            # Test the connection on first acquire (wakes Neon if suspended)
            session.connection()
            break
        except Exception:
            session.close()
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                raise

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
    ensure_myo_schedule_column()
    ensure_performance_indexes()


def ensure_myo_schedule_column() -> None:
    """Add the persisted Myo schedule column to existing deployments."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if "myo_sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("myo_sessions")}
    if "schedule_json" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE myo_sessions ADD COLUMN schedule_json TEXT"))


def ensure_performance_indexes() -> None:
    """Create read-path indexes used by workout loading and progression queries."""
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_exercises_lower_name ON exercises (lower(name))",
        "CREATE INDEX IF NOT EXISTS idx_workout_exercises_workout_exercise ON workout_exercises (workout_id, exercise_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_workout_completed_number ON sessions (workout_id, completed, session_number)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_workout_number ON sessions (workout_id, session_number)",
        "CREATE INDEX IF NOT EXISTS idx_sets_workout_exercise_session ON sets (workout_exercise_id, session_id)",
        "CREATE INDEX IF NOT EXISTS idx_sets_session_workout_exercise ON sets (session_id, workout_exercise_id)",
        "CREATE INDEX IF NOT EXISTS idx_sets_logged_at ON sets (logged_at)",
        "CREATE INDEX IF NOT EXISTS idx_feedback_session_muscle ON feedback (session_id, muscle_group)",
        "CREATE INDEX IF NOT EXISTS idx_feedback_muscle_created ON feedback (muscle_group, created_at)",
    )
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


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
        exercise_names = list(EXERCISE_MUSCLE_GROUPS)
        existing_exercises = (
            db.query(Exercise)
            .filter(func.lower(Exercise.name).in_([name.lower() for name in exercise_names]))
            .all()
        )
        existing_names = {exercise.name.lower() for exercise in existing_exercises}
        for exercise_name, muscle_group in EXERCISE_MUSCLE_GROUPS.items():
            if exercise_name.lower() not in existing_names:
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
