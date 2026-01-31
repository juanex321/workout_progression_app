"""
Workout Progression Audit Report (Standalone)

Shows complete history of sets, reps, weights, and feedback across all sessions.
"""

import os
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from collections import defaultdict

Base = declarative_base()


# Database Models (copied to avoid db.py imports)
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
    logged_at = Column(DateTime, nullable=False, default=datetime.now)
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
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    session = relationship("Session", back_populates="feedbacks")


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


class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    muscle_group = Column(String, nullable=True)
    workout_exercises = relationship("WorkoutExercise", back_populates="exercise")


class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    name = Column(String, nullable=False)
    day_label = Column(String, nullable=False)
    workout_exercises = relationship("WorkoutExercise", back_populates="workout")


def get_db_connection():
    """Get database connection from environment."""
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set!")
        print("\nUsage:")
        print('  $env:DATABASE_URL="postgresql://..."')
        print('  python audit_report.py')
        exit(1)

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print("Connecting to database...")
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def audit_progression():
    """Generate a complete progression audit report."""
    db = get_db_connection()

    try:
        # Get all completed sessions
        sessions = (
            db.query(Session)
            .filter(Session.completed == 1)
            .order_by(Session.session_number)
            .all()
        )

        if not sessions:
            print("No completed sessions found.")
            return

        print("=" * 80)
        print("WORKOUT PROGRESSION AUDIT REPORT")
        print("=" * 80)
        print(f"\nTotal Sessions Completed: {len(sessions)}")
        print(f"Session Range: {sessions[0].session_number} - {sessions[-1].session_number}")
        print("=" * 80)

        # Process each session
        for session in sessions:
            print(f"\n{'=' * 80}")
            print(f"SESSION {session.session_number} - {session.date}")
            print('=' * 80)

            # Get sets for this session
            sets_by_exercise = defaultdict(list)
            sets = (
                db.query(Set)
                .filter(Set.session_id == session.id)
                .join(WorkoutExercise)
                .join(Exercise)
                .order_by(Exercise.muscle_group, WorkoutExercise.order_index, Set.set_number)
                .all()
            )

            for set_obj in sets:
                we = db.query(WorkoutExercise).get(set_obj.workout_exercise_id)
                exercise = we.exercise
                muscle_group = exercise.muscle_group or exercise.name

                sets_by_exercise[(muscle_group, exercise.name, we.id)].append({
                    'set_number': set_obj.set_number,
                    'weight': set_obj.weight,
                    'reps': set_obj.reps,
                    'rir': set_obj.rir,
                })

            # Get feedback
            feedbacks = db.query(Feedback).filter(Feedback.session_id == session.id).all()
            feedback_by_muscle = {fb.muscle_group: fb for fb in feedbacks}

            # Display by muscle group
            current_muscle_group = None
            for (muscle_group, exercise_name, we_id), sets_list in sets_by_exercise.items():
                if current_muscle_group != muscle_group:
                    current_muscle_group = muscle_group
                    print(f"\n{muscle_group.upper()}")
                    print("-" * 80)

                    if muscle_group in feedback_by_muscle:
                        fb = feedback_by_muscle[muscle_group]
                        print(f"  Feedback: Soreness={fb.soreness} | Pump={fb.pump} | Workload={fb.workload}")
                    else:
                        print("  Feedback: Not submitted")
                    print()

                print(f"  {exercise_name}:")
                for set_data in sets_list:
                    rir_str = f"@{set_data['rir']}" if set_data['rir'] is not None else ""
                    print(f"    Set {set_data['set_number']}: {set_data['weight']}kg x {set_data['reps']} reps {rir_str}")

                total_sets = len(sets_list)
                avg_weight = sum(s['weight'] for s in sets_list) / total_sets if total_sets else 0
                total_reps = sum(s['reps'] for s in sets_list)
                first_set_reps = sets_list[0]['reps'] if sets_list else 0

                print(f"    -> {total_sets} sets | Avg: {avg_weight:.1f}kg | Total reps: {total_reps} | First: {first_set_reps} reps\n")

        # Progression summary
        print("\n" + "=" * 80)
        print("PROGRESSION SUMMARY (BY EXERCISE)")
        print("=" * 80)

        all_exercises = db.query(Exercise).all()

        for exercise in all_exercises:
            workout_exercises = db.query(WorkoutExercise).filter(
                WorkoutExercise.exercise_id == exercise.id
            ).all()

            if not workout_exercises:
                continue

            print(f"\n{exercise.name} ({exercise.muscle_group}):")
            print("-" * 80)

            for we in workout_exercises:
                all_sets = (
                    db.query(Set, Session)
                    .join(Session)
                    .filter(Set.workout_exercise_id == we.id)
                    .filter(Session.completed == 1)
                    .order_by(Session.session_number, Set.set_number)
                    .all()
                )

                if not all_sets:
                    continue

                sets_by_session = defaultdict(list)
                for set_obj, session_obj in all_sets:
                    sets_by_session[session_obj.session_number].append({
                        'weight': set_obj.weight,
                        'reps': set_obj.reps,
                    })

                for session_num in sorted(sets_by_session.keys()):
                    sets_list = sets_by_session[session_num]
                    first_set = sets_list[0]
                    total_sets = len(sets_list)
                    total_reps = sum(s['reps'] for s in sets_list)

                    print(f"  Session {session_num}: {total_sets} sets x {first_set['weight']}kg "
                          f"(First: {first_set['reps']} reps, Total: {total_reps} reps)")

        # Feedback trends
        print("\n" + "=" * 80)
        print("FEEDBACK TRENDS (BY MUSCLE GROUP)")
        print("=" * 80)

        muscle_groups = [mg[0] for mg in db.query(Exercise.muscle_group).distinct().all() if mg[0]]

        for muscle_group in sorted(muscle_groups):
            print(f"\n{muscle_group}:")
            print("-" * 80)

            feedbacks = (
                db.query(Feedback, Session)
                .join(Session)
                .filter(Feedback.muscle_group == muscle_group)
                .filter(Session.completed == 1)
                .order_by(Session.session_number)
                .all()
            )

            if not feedbacks:
                print("  No feedback recorded")
                continue

            print("  Session | Soreness | Pump | Workload")
            print("  " + "-" * 40)
            for fb, sess in feedbacks:
                print(f"  {sess.session_number:7} | {fb.soreness:8} | {fb.pump:4} | {fb.workload:8}")

            if feedbacks:
                avg_soreness = sum(fb.soreness for fb, _ in feedbacks) / len(feedbacks)
                avg_pump = sum(fb.pump for fb, _ in feedbacks) / len(feedbacks)
                avg_workload = sum(fb.workload for fb, _ in feedbacks) / len(feedbacks)

                print("  " + "-" * 40)
                print(f"  Average | {avg_soreness:8.1f} | {avg_pump:4.1f} | {avg_workload:8.1f}")

        print("\n" + "=" * 80)
        print("END OF REPORT")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    audit_progression()
