# services.py
from __future__ import annotations

from datetime import date
from typing import Optional

from db import Session as DbSession, WorkoutExercise, Exercise, Set, Feedback
from plan import DEFAULT_TARGET_SETS, DEFAULT_TARGET_REPS, EXERCISE_DEFAULT_SETS, EXERCISE_DEFAULT_REPS, EXERCISE_MUSCLE_GROUPS


def get_current_session(db, workout_id: int) -> DbSession:
    """
    Get the current (most recent incomplete) session, or create a new one if all are complete.
    """
    # Try to get the most recent incomplete session
    sess = (
        db.query(DbSession)
        .filter(DbSession.workout_id == workout_id, DbSession.completed == 0)
        .order_by(DbSession.session_number.desc())
        .first()
    )
    if sess:
        return sess

    # All sessions are complete, create the next one
    last_session = (
        db.query(DbSession)
        .filter(DbSession.workout_id == workout_id)
        .order_by(DbSession.session_number.desc())
        .first()
    )
    
    if last_session:
        next_session_number = last_session.session_number + 1
        # Import get_session_exercises here to avoid circular import
        from plan import get_session_exercises
        total_workouts = 6  # Based on the rotation pattern (3 leg rotations * 2 push/pull = 6)
        next_rotation_index = (last_session.rotation_index + 1) % total_workouts
    else:
        next_session_number = 1
        next_rotation_index = 0

    sess = DbSession(
        workout_id=workout_id,
        session_number=next_session_number,
        rotation_index=next_rotation_index,
        completed=0,
        date=date.today()
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def get_session_by_number(db, workout_id: int, session_number: int) -> Optional[DbSession]:
    """
    Get a specific session by its session number.
    """
    return (
        db.query(DbSession)
        .filter(DbSession.workout_id == workout_id, DbSession.session_number == session_number)
        .first()
    )


def complete_session(db, session_id: int) -> DbSession:
    """
    Mark a session as complete and create the next session.
    Returns the newly created next session.
    """
    sess = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not sess:
        raise ValueError(f"Session {session_id} not found")
    
    # Mark current session as complete
    sess.completed = 1
    db.add(sess)
    db.commit()
    
    # Create next session
    return get_current_session(db, sess.workout_id)


def get_or_create_today_session(db, workout_id: int) -> DbSession:
    """
    DEPRECATED: Use get_current_session() instead.
    This function is kept for backward compatibility during migration.
    """
    return get_current_session(db, workout_id)


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
        muscle_group = EXERCISE_MUSCLE_GROUPS.get(name_normalized, None)
        exercise = Exercise(name=name_normalized, muscle_group=muscle_group)
        db.add(exercise)
        db.flush()  # get exercise.id

    from sqlalchemy.orm import joinedload
    we = (
        db.query(WorkoutExercise)
        .options(joinedload(WorkoutExercise.exercise))
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
        we.exercise = exercise  # Attach exercise object
        db.add(we)

    # Ensure exercise is attached even for existing records
    if we.exercise is None:
        we.exercise = exercise

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
    rows: iterable of dict-like rows with set_number, weight, reps, done(optional), rir(optional)
    Deletes and replaces all sets for that exercise in that session.
    """
    db.query(Set).filter(
        Set.session_id == session_id,
        Set.workout_exercise_id == workout_exercise_id,
    ).delete()

    for row in rows:
        # Skip incomplete sets
        if ("done" in row and not row["done"]) or ("logged" in row and not row["logged"]):
            continue
        s = Set(
            session_id=session_id,
            workout_exercise_id=workout_exercise_id,
            set_number=int(row["set_number"]),
            weight=float(row["weight"]),
            reps=int(row["reps"]),
            rir=float(row.get("rir")) if row.get("rir") is not None else None,
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
                
                # FIX: Check if there are ANY logged sets (meaning the exercise has been started)
                # An exercise is considered complete if at least 1 set is logged
                # This allows the feedback form to appear when all exercises for a muscle group
                # have been worked, regardless of whether all target sets were completed
                if logged_sets_count == 0:
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


def get_muscle_group_feedback(db, session_id: int, muscle_group: str):
    """
    Load existing feedback for a muscle group in a session.

    Returns:
        dict with soreness, pump, workload values or None if not found
    """
    feedback = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_id,
            Feedback.muscle_group == muscle_group,
        )
        .first()
    )

    if feedback:
        return {
            "soreness": feedback.soreness or 3,
            "pump": feedback.pump or 3,
            "workload": feedback.workload or 3,
        }
    return None


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
