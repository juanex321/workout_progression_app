from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Date,
    DateTime,
    func,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DB_PATH = Path("workout.db")
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class Program(Base):
    __tablename__ = "programs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    workouts = relationship("Workout", back_populates="program")


class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    name = Column(String, nullable=False)
    day_label = Column(String, nullable=False)

    program = relationship("Program", back_populates="workouts")
    workout_exercises = relationship("WorkoutExercise", back_populates="workout")


class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    muscle_group = Column(String, nullable=True)

    workout_exercises = relationship("WorkoutExercise", back_populates="exercise")


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    order_index = Column(Integer, nullable=False, default=1)
    target_sets = Column(Integer, nullable=False, default=4)
    target_reps = Column(Integer, nullable=False, default=10)

    workout = relationship("Workout", back_populates="workout_exercises")
    exercise = relationship("Exercise", back_populates="workout_exercises")
    sessions_sets = relationship("Set", back_populates="workout_exercise")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False)
    session_number = Column(Integer, nullable=False, default=1)
    rotation_index = Column(Integer, nullable=False, default=0)
    completed = Column(Integer, nullable=False, default=0)  # 0 = incomplete, 1 = complete
    date = Column(Date, nullable=False, default=date.today)

    sets = relationship("Set", back_populates="session")
    workout = relationship("Workout")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=True)
    muscle_group = Column(String, nullable=True)

    soreness = Column(Integer)
    pump = Column(Integer)
    workload = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())


class Set(Base):
    __tablename__ = "sets"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=False)
    set_number = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    rir = Column(Float, nullable=True)
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("Session", back_populates="sets")
    workout_exercise = relationship("WorkoutExercise", back_populates="sessions_sets")


# NEW: autosaved draft rows so refresh/reboots don’t wipe your progress
class DraftSet(Base):
    __tablename__ = "draft_sets"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=False)

    set_number = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    done = Column(Integer, nullable=False, default=0)  # 0/1

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def init_db(create_backup_first=True):
    """
    Initialize database tables ONLY if they don't exist.
    Does NOT modify existing tables (preserves data).
    
    Args:
        create_backup_first: If True, creates a safety backup before initialization
    """
    # If database exists and backup requested, create a backup before any operations
    if create_backup_first and DB_PATH.exists():
        try:
            # Import here to avoid circular import
            import backup_db
            print("📦 Existing database found - creating safety backup...")
            backup_db.create_backup(reason="auto_safety")
        except ImportError:
            # backup_db not available yet (during initial module import)
            pass
        except Exception as e:
            print(f"⚠️  Could not create backup: {e}")
    
    # Create tables only if they don't exist (won't modify existing tables)
    Base.metadata.create_all(bind=engine)
    if create_backup_first:
        print("✅ Database tables verified/created")


# Make sure tables exist in Streamlit Cloud even if init_db.py isn't run
# Don't create backup during module import to avoid circular dependencies
init_db(create_backup_first=False)


@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
