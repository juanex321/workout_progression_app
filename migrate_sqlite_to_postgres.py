"""
Migrate data from local SQLite to PostgreSQL.
Run this once to transfer your local workout history to the cloud database.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

def migrate():
    """Migrate all data from SQLite to PostgreSQL."""
    # Source: SQLite
    sqlite_engine = create_engine('sqlite:///workout.db')
    SQLiteSession = sessionmaker(bind=sqlite_engine)
    
    # Target: PostgreSQL (from environment variable)
    postgres_url = os.environ.get('DATABASE_URL')
    if not postgres_url:
        print("❌ Set DATABASE_URL environment variable with PostgreSQL connection string")
        print("\nExample:")
        print('export DATABASE_URL="postgresql://user:password@host:port/database"')
        return
    
    # Fix for some platforms that use postgres:// instead of postgresql://
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
    
    postgres_engine = create_engine(postgres_url)
    PostgresSession = sessionmaker(bind=postgres_engine)
    
    # Create tables in PostgreSQL
    from db import Base
    print("Creating tables in PostgreSQL...")
    Base.metadata.create_all(postgres_engine)
    
    # Migrate data
    from db import Program, Workout, Exercise, WorkoutExercise, Session, Set, Feedback
    
    print("\n🔄 Starting migration...\n")
    
    with SQLiteSession() as source, PostgresSession() as target:
        # Migrate Programs
        programs = source.query(Program).all()
        print(f"Migrating {len(programs)} Programs...")
        for program in programs:
            target.merge(program)
        target.commit()
        
        # Migrate Workouts
        workouts = source.query(Workout).all()
        print(f"Migrating {len(workouts)} Workouts...")
        for workout in workouts:
            target.merge(workout)
        target.commit()
        
        # Migrate Exercises
        exercises = source.query(Exercise).all()
        print(f"Migrating {len(exercises)} Exercises...")
        for exercise in exercises:
            target.merge(exercise)
        target.commit()
        
        # Migrate WorkoutExercises
        workout_exercises = source.query(WorkoutExercise).all()
        print(f"Migrating {len(workout_exercises)} WorkoutExercises...")
        for we in workout_exercises:
            target.merge(we)
        target.commit()
        
        # Migrate Sessions
        sessions = source.query(Session).all()
        print(f"Migrating {len(sessions)} Sessions...")
        for session in sessions:
            target.merge(session)
        target.commit()
        
        # Migrate Sets
        sets = source.query(Set).all()
        print(f"Migrating {len(sets)} Sets...")
        for set_obj in sets:
            target.merge(set_obj)
        target.commit()
        
        # Migrate Feedback
        feedbacks = source.query(Feedback).all()
        print(f"Migrating {len(feedbacks)} Feedback entries...")
        for feedback in feedbacks:
            target.merge(feedback)
        target.commit()

        print("\n✅ Migration complete!")
        print(f"\n📊 Migrated:")
        print(f"  - {len(programs)} Programs")
        print(f"  - {len(workouts)} Workouts")
        print(f"  - {len(exercises)} Exercises")
        print(f"  - {len(workout_exercises)} WorkoutExercises")
        print(f"  - {len(sessions)} Sessions")
        print(f"  - {len(sets)} Sets")
        print(f"  - {len(feedbacks)} Feedback entries")

if __name__ == "__main__":
    migrate()
