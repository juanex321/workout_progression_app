"""
Workout Progression Audit Report

Shows complete history of sets, reps, weights, and feedback across all sessions.

Usage:
  Set DATABASE_URL environment variable and run:
  $env:DATABASE_URL="your_connection_string"
  python audit_progression.py
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from collections import defaultdict

# Import database models
from db import Session, Set, Feedback, WorkoutExercise, Exercise, Workout, Base


def get_db_connection():
    """Get database connection from environment or use SQLite fallback."""
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        print(f"Connecting to PostgreSQL database...")
        engine = create_engine(database_url, pool_pre_ping=True)
    else:
        print("Using SQLite database (workout.db)...")
        engine = create_engine('sqlite:///workout.db', connect_args={"check_same_thread": False})

    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def audit_progression():
    """Generate a complete progression audit report."""
    db = get_db_connection()

    try:
        # Get all completed sessions ordered by session number
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

            # Get all sets for this session grouped by exercise
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

            # Get feedback for this session
            feedbacks = (
                db.query(Feedback)
                .filter(Feedback.session_id == session.id)
                .all()
            )

            feedback_by_muscle = {fb.muscle_group: fb for fb in feedbacks}

            # Display by muscle group
            current_muscle_group = None
            for (muscle_group, exercise_name, we_id), sets_list in sets_by_exercise.items():
                if current_muscle_group != muscle_group:
                    current_muscle_group = muscle_group

                    # Display muscle group header with feedback
                    print(f"\n{muscle_group.upper()}")
                    print("-" * 80)

                    if muscle_group in feedback_by_muscle:
                        fb = feedback_by_muscle[muscle_group]
                        print(f"  Feedback: Soreness={fb.soreness} | Pump={fb.pump} | Workload={fb.workload}")
                    else:
                        print("  Feedback: Not submitted")
                    print()

                # Display exercise
                print(f"  {exercise_name}:")

                # Display sets
                for set_data in sets_list:
                    rir_str = f"@{set_data['rir']}" if set_data['rir'] is not None else ""
                    print(f"    Set {set_data['set_number']}: {set_data['weight']}kg x {set_data['reps']} reps {rir_str}")

                # Calculate totals
                total_sets = len(sets_list)
                avg_weight = sum(s['weight'] for s in sets_list) / total_sets if total_sets else 0
                total_reps = sum(s['reps'] for s in sets_list)
                first_set_reps = sets_list[0]['reps'] if sets_list else 0

                print(f"    -> {total_sets} sets | Avg weight: {avg_weight:.1f}kg | Total reps: {total_reps} | First set: {first_set_reps} reps")
                print()

        # Summary statistics
        print("\n" + "=" * 80)
        print("PROGRESSION SUMMARY")
        print("=" * 80)

        # Get unique exercises and show progression over time
        all_exercises = db.query(Exercise).all()

        for exercise in all_exercises:
            # Get all workout exercises for this exercise
            workout_exercises = db.query(WorkoutExercise).filter(
                WorkoutExercise.exercise_id == exercise.id
            ).all()

            if not workout_exercises:
                continue

            print(f"\n{exercise.name} ({exercise.muscle_group}):")
            print("-" * 80)

            for we in workout_exercises:
                # Get sets across all sessions for this workout exercise
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

                # Group by session
                sets_by_session = defaultdict(list)
                for set_obj, session_obj in all_sets:
                    sets_by_session[session_obj.session_number].append({
                        'weight': set_obj.weight,
                        'reps': set_obj.reps,
                    })

                # Show progression
                for session_num in sorted(sets_by_session.keys()):
                    sets_list = sets_by_session[session_num]
                    first_set = sets_list[0]
                    total_sets = len(sets_list)
                    total_reps = sum(s['reps'] for s in sets_list)

                    print(f"  Session {session_num}: {total_sets} sets x {first_set['weight']}kg "
                          f"(First set: {first_set['reps']} reps, Total: {total_reps} reps)")

        # Feedback trends
        print("\n" + "=" * 80)
        print("FEEDBACK TRENDS BY MUSCLE GROUP")
        print("=" * 80)

        # Get all muscle groups
        muscle_groups = db.query(Exercise.muscle_group).distinct().all()
        muscle_groups = [mg[0] for mg in muscle_groups if mg[0]]

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

            # Calculate averages
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
