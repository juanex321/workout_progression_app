from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, date

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Date,
    DateTime,
    func,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ---------- engine / session setup ----------

DB_PATH = Path("workout.db")
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

# ---------- models ----------


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
    day_label = Column(String, nullable=False)  # e.g. "Week 6 Day 4 Thursday"

    program = relationship("Program", back_populates="workouts")
    workout_exercises = relationship("WorkoutExercise", back_populates="workout")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    muscle_group = Column(String, nullable=True)

    workout_exercises = relationship("WorkoutExercise", back_populates="exercise")


class WorkoutExercise(Base):
    """
    An exercise assigned to a specific workout (e.g. Leg Extension in Week 6 Day 4),
    with target sets/reps and order.
    """

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
    date = Column(Date, nullable=False, default=date.today)

    sets = relationship("Set", back_populates="session")
    workout = relationship("Workout")
    # optional: if you want easy access to feedback from a session
    # feedback_entries = relationship("Feedback", back_populates="session")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=False)

    # stored as 1–4, 1–3, 1–4
    soreness = Column(Integer)
    pump = Column(Integer)
    workload = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())

    # These relationships are optional but handy
    # session = relationship("Session")
    # workout_exercise = relationship("WorkoutExercise")


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


def init_db():
    Base.metadata.create_all(bind=engine)


# Ensure all tables (including Feedback) exist whenever db.py is imported
init_db()


@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

