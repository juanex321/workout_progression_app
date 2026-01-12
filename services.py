# services.py
from __future__ import annotations

from datetime import date
from typing import Optional

from db import Session as DbSession, WorkoutExercise, Exercise, Set, Feedback
from plan import DEFAULT_TARGET_SETS, DEFAULT_TARGET_REPS, EXERCISE_DEFAULT_SETS, EXERCISE_DEFAULT_REPS


def get_or_create_today_session(db, workout_id: int) -> DbSession:
    today = date.today()
    sess = (
        db.query(DbSession)
        .filter(DbSession.workout_id == workout_id, DbSession.date == today)
        .first()
    )
    if sess:
        return sess

    sess = DbSession(workout_id=workout_id, date=today)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def get_or_create_workout_exercise(db, workout, ex_name: str, order_index: int) -> WorkoutExercise:
    """
    Ensures:
      - Exercise exists (by name)
      - WorkoutExercise exists (workout_id + exercise_id)
      - Applies default target_sets for finishers
    """
    name_normalized = ex_name.strip()

    exercise = (
        db.query(Exercise)
        .filter(Exercise.name.ilike(name_normalized))
        .first()
    )
    if not exercise:
        exercise = Exercise(name=name_normalized)
        db.add(exercise)
        db.flush()  # get exercise.id

    we = (
        db.query(WorkoutExercise)
        .filter(
            WorkoutExercise.workout_id == workout.id,
            WorkoutExercise.exercise_id == exercise.id,
        )
        .first()
    )
    if not we:
        target_sets = EXERCISE_DEFAULT_SETS.get(name_normalized, DEFAULT_TARGET_SETS)
        target_reps = EXERCISE_DEFAULT_REPS.get(name_normalized, DEFAULT_TARGET_REPS)
        we = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=exercise.id,
            order_index=order_index,
            target_sets=target_sets,
            target_reps=target_reps,
        )
        db.add(we)

    return we


def load_existing_sets(db, session_id: int, workout_exercise_id: int) -> list[Set]:
    return (
        db.query(Set)
        .filter(Set.session_id == session_id, Set.workout_exercise_id == workout_exercise_id)
        .order_by(Set.set_number.asc())
        .all()
    )


def save_sets(db, session_id: int, workout_exercise_id: int, rows) -> None:
    """
    rows: iterable of dict-like rows with set_number, weight, reps, done(optional)
    Deletes and replaces all sets for that exercise in that session.
    """
    db.query(Set).filter(
        Set.session_id == session_id,
        Set.workout_exercise_id == workout_exercise_id,
    ).delete()

    for row in rows:
        if "done" in row and not row["done"]:
            continue
        s = Set(
            session_id=session_id,
            workout_exercise_id=workout_exercise_id,
            set_number=int(row["set_number"]),
            weight=float(row["weight"]),
            reps=int(row["reps"]),
            rir=None,
        )
        db.add(s)

    db.commit()


def check_feedback_exists(db, session_id: int, workout_exercise_id: int) -> bool:
    """
    Check if feedback already exists for this exercise in this session.
    """
    feedback = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_id,
            Feedback.workout_exercise_id == workout_exercise_id,
        )
        .first()
    )
    return feedback is not None


def save_feedback(
    db, session_id: int, workout_exercise_id: int, soreness: int, pump: int, workload: int
) -> None:
    """
    Save feedback to the database for a given session and exercise.
    If feedback already exists, update it. Otherwise, create new feedback.
    """
    existing_feedback = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_id,
            Feedback.workout_exercise_id == workout_exercise_id,
        )
        .first()
    )

    if existing_feedback:
        existing_feedback.soreness = soreness
        existing_feedback.pump = pump
        existing_feedback.workload = workload
    else:
        feedback = Feedback(
            session_id=session_id,
            workout_exercise_id=workout_exercise_id,
            soreness=soreness,
            pump=pump,
            workload=workload,
        )
        db.add(feedback)

    db.commit()


def is_last_exercise_for_muscle_group(
    db, workout_exercise: WorkoutExercise, session_exercises: list[str], session_id: int
) -> bool:
    """
    Check if the given workout_exercise is the last exercise for its muscle group
    in the current session, AND all other exercises for the same muscle group have
    completed all their sets.
    
    Args:
        db: Database session
        workout_exercise: The WorkoutExercise to check
        session_exercises: Ordered list of exercise names for the session
        session_id: The session ID to check set completion
    
    Returns:
        True if this is the last exercise for its muscle group AND all exercises
        for the muscle group have all their sets logged, False otherwise
    """
    # Get the exercise and its muscle group
    exercise = workout_exercise.exercise
    if not exercise.muscle_group:
        # If no muscle group is set, treat each exercise independently
        return True
    
    muscle_group = exercise.muscle_group
    exercise_name = exercise.name
    
    # Find the index of this exercise in the session
    try:
        current_index = session_exercises.index(exercise_name)
    except ValueError:
        # Exercise not in session list, treat as last
        return True
    
    # Check if any later exercises have the same muscle group
    for later_ex_name in session_exercises[current_index + 1:]:
        later_exercise = db.query(Exercise).filter(Exercise.name.ilike(later_ex_name)).first()
        if later_exercise and later_exercise.muscle_group == muscle_group:
            # Found a later exercise with the same muscle group
            return False
    
    # Check if all exercises with the same muscle group have all their sets logged
    for ex_name in session_exercises:
        ex = db.query(Exercise).filter(Exercise.name.ilike(ex_name)).first()
        if ex and ex.muscle_group == muscle_group:
            # Find the corresponding WorkoutExercise
            we = db.query(WorkoutExercise).filter(
                WorkoutExercise.workout_id == workout_exercise.workout_id,
                WorkoutExercise.exercise_id == ex.id
            ).first()
            
            if we:
                # Count logged sets for this exercise in the current session
                logged_sets_count = db.query(Set).filter(
                    Set.session_id == session_id,
                    Set.workout_exercise_id == we.id
                ).count()
                
                # Check if all sets are logged by comparing with target_sets
                # An exercise is considered complete if it has at least target_sets logged
                if logged_sets_count < we.target_sets:
                    return False
    
    # No later exercises with the same muscle group found and all exercises are complete
    return True


def check_muscle_group_feedback_exists(db, session_id: int, muscle_group: str) -> bool:
    """
    Check if feedback already exists for this muscle group in this session.
    """
    feedback = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_id,
            Feedback.muscle_group == muscle_group,
        )
        .first()
    )
    return feedback is not None


def save_muscle_group_feedback(
    db, session_id: int, muscle_group: str, soreness: int, pump: int, workload: int
) -> None:
    """
    Save feedback to the database for a given session and muscle group.
    If feedback already exists, update it. Otherwise, create new feedback.
    """
    existing_feedback = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_id,
            Feedback.muscle_group == muscle_group,
        )
        .first()
    )

    if existing_feedback:
        existing_feedback.soreness = soreness
        existing_feedback.pump = pump
        existing_feedback.workload = workload
    else:
        feedback = Feedback(
            session_id=session_id,
            muscle_group=muscle_group,
            soreness=soreness,
            pump=pump,
            workload=workload,
        )
        db.add(feedback)

    db.commit()
