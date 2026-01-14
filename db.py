import os
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, date
from urllib.parse import quote_plus

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


def get_database_url():
    """Get database URL based on environment."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'connections' in st.secrets and 'workout_db' in st.secrets['connections']:
            db_secrets = st.secrets['connections']['workout_db']

            # URL-encode username and password to handle special characters
            raw_username = db_secrets['username']
            raw_password = db_secrets['password']
            host = db_secrets['host']
            port = db_secrets.get('port', 5432)
            database = db_secrets['database']

            # Debug: write to stderr which always shows in logs
            import sys
            sys.stderr.write(f"DEBUG: username='{raw_username}', len={len(raw_username)}\n")
            sys.stderr.write(f"DEBUG: password len={len(raw_password)}, first4='{raw_password[:4]}'\n")
            sys.stderr.write(f"DEBUG: host='{host}'\n")
            sys.stderr.write(f"DEBUG: database='{database}'\n")
            sys.stderr.flush()

            username = quote_plus(raw_username)
            password = quote_plus(raw_password)

            url = f"postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=require"
            print("🌐 Using PostgreSQL database (Streamlit Cloud)")
            return url
    except Exception as e:
        print(f"ℹ️  Not using Streamlit secrets: {e}")
        import traceback
        traceback.print_exc()
    
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
        pool_pre_ping=True,
        pool_recycle=3600,
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
    reps_in_reserve = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=func.now())

    session = relationship("Session", back_populates="sets")


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    workout_exercise_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=True)
    muscle_group = Column(String, nullable=True)
    volume_rating = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=func.now())

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
