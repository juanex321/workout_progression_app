import os
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
from sqlalchemy.pool import NullPool


def get_database_url():
    """Get database URL based on environment."""
    # First, try Streamlit secrets with DATABASE_URL (simplest approach)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'DATABASE_URL' in st.secrets:
            url = st.secrets['DATABASE_URL']
            if url.startswith('postgres://'):
                url = url.replace('postgres://', 'postgresql://', 1)
            print("🌐 Using PostgreSQL database (Streamlit Cloud - DATABASE_URL)")
            return url
    except Exception as e:
        print(f"ℹ️  DATABASE_URL not in Streamlit secrets: {e}")

    # Second, try environment variable
    if 'DATABASE_URL' in os.environ:
        url = os.environ['DATABASE_URL']
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        print(f"🌐 Using PostgreSQL from DATABASE_URL")
        return url
    
    DB_PATH = Path("workout.db")
    print(f"💾 Using SQLite database: {DB_PATH}")
    return f"sqlite:///{DB_PATH}"


DATABASE_URL = get_database_url()

if DATABASE_URL.startswith('postgresql'):
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,  # No connection pooling - better for serverless
    )
else:
    engine = create_engine(
        DATABASE_URL,
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
    order_index = Column(Integer, nullable=False)
    target_sets = Column(Integer, nullable=False)
    target_reps = Column(Integer, nullable=False)

    workout = relationship("Workout", back_populates="workout_exercises")
    exercise = relationship("Exercise", back_populates="workout_exercises")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False)
    session_number = Column(Integer, nullable=False)
    rotation_index = Column(Integer, nullable=False, default=0)
    date = Column(Date, nullable=False, default=date.today)
    completed = Column(Integer, nullable=False, default=0)

    sets = relationship("Set", back_populates="session")
    feedbacks = relationship("Feedback", back_populates="session")


class Set(Base):
    __tablename__ = "sets"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=False)
    set_number = Column(Integer, nullable=False)
    weight = Column(Float, nullable=True)
    reps = Column(Integer, nullable=True)
    rir = Column(Integer, nullable=True)
    logged_at = Column(DateTime, nullable=False, default=func.now())

    session = relationship("Session", back_populates="sets")


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=True)
    muscle_group = Column(String, nullable=True)
    soreness = Column(Integer, nullable=True)
    pump = Column(Integer, nullable=True)
    workload = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

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
