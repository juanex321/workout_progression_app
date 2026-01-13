# services.py

from datetime import date
from db import (
    Session,
    WorkoutSession,
    WorkoutExercise,
    LoggedSet,
    ExerciseFeedback,
    MuscleGroupFeedback,
    db
)
from plan import get_workout_plan

def get_or_create_today_session():
    """
    Get or create a workout session for today.
    Returns the WorkoutSession object for today's date.
    """
    today = date.today()
    session = Session.query.filter_by(session_date=today).first()
    
    if not session:
        session = WorkoutSession(session_date=today)
        db.session.add(session)
        db.session.commit()
    
    return session

def get_or_create_workout_exercise(session_id, exercise_name, muscle_group, target_sets, target_reps):
    """
    Get or create a WorkoutExercise for the given session and exercise.
    
    Args:
        session_id: ID of the workout session
        exercise_name: Name of the exercise
        muscle_group: Muscle group being worked
        target_sets: Target number of sets
        target_reps: Target number of reps
    
    Returns:
        WorkoutExercise object
    """
    we = WorkoutExercise.query.filter_by(
        session_id=session_id,
        exercise_name=exercise_name
    ).first()
    
    if not we:
        we = WorkoutExercise(
            session_id=session_id,
            exercise_name=exercise_name,
            muscle_group=muscle_group,
            target_sets=target_sets,
            target_reps=target_reps
        )
        db.session.add(we)
        db.session.commit()
    
    return we

def load_existing_sets(workout_exercise_id):
    """
    Load existing logged sets for a workout exercise.
    
    Args:
        workout_exercise_id: ID of the WorkoutExercise
    
    Returns:
        List of LoggedSet objects
    """
    return LoggedSet.query.filter_by(
        workout_exercise_id=workout_exercise_id
    ).order_by(LoggedSet.set_number).all()

def save_sets(workout_exercise_id, sets_data):
    """
    Save sets data for a workout exercise.
    
    Args:
        workout_exercise_id: ID of the WorkoutExercise
        sets_data: List of dictionaries with 'reps' and 'weight' keys
    
    Returns:
        None
    """
    # Delete existing sets for this exercise
    LoggedSet.query.filter_by(workout_exercise_id=workout_exercise_id).delete()
    
    # Add new sets
    for i, set_data in enumerate(sets_data, 1):
        logged_set = LoggedSet(
            workout_exercise_id=workout_exercise_id,
            set_number=i,
            reps=set_data['reps'],
            weight=set_data['weight']
        )
        db.session.add(logged_set)
    
    db.session.commit()

def check_feedback_exists(workout_exercise_id):
    """
    Check if feedback exists for a workout exercise.
    
    Args:
        workout_exercise_id: ID of the WorkoutExercise
    
    Returns:
        Boolean indicating if feedback exists
    """
    feedback = ExerciseFeedback.query.filter_by(
        workout_exercise_id=workout_exercise_id
    ).first()
    
    return feedback is not None

def save_feedback(workout_exercise_id, difficulty, notes):
    """
    Save feedback for a workout exercise.
    
    Args:
        workout_exercise_id: ID of the WorkoutExercise
        difficulty: Difficulty rating (1-5)
        notes: Optional notes about the exercise
    
    Returns:
        None
    """
    # Check if feedback already exists
    feedback = ExerciseFeedback.query.filter_by(
        workout_exercise_id=workout_exercise_id
    ).first()
    
    if feedback:
        # Update existing feedback
        feedback.difficulty = difficulty
        feedback.notes = notes
    else:
        # Create new feedback
        feedback = ExerciseFeedback(
            workout_exercise_id=workout_exercise_id,
            difficulty=difficulty,
            notes=notes
        )
        db.session.add(feedback)
    
    db.session.commit()

def is_last_exercise_for_muscle_group(session_id, muscle_group, current_exercise_name):
    """
    Check if the current exercise is the last one for its muscle group in today's session.
    
    Args:
        session_id: ID of the workout session
        muscle_group: Muscle group to check
        current_exercise_name: Name of the current exercise
    
    Returns:
        Boolean indicating if this is the last exercise for the muscle group
    """
    # Get the workout plan for today
    today = date.today()
    day_name = today.strftime('%A')
    workout_plan = get_workout_plan()
    
    if day_name not in workout_plan:
        return False
    
    # Get all exercises for this muscle group from the plan
    exercises_for_muscle = [
        ex for ex in workout_plan[day_name]
        if ex['muscle_group'] == muscle_group
    ]
    
    if not exercises_for_muscle:
        return False
    
    # Find the index of the current exercise
    current_index = None
    for i, ex in enumerate(exercises_for_muscle):
        if ex['name'] == current_exercise_name:
            current_index = i
            break
    
    if current_index is None:
        return False
    
    # Check if there are any exercises after the current one
    # that don't have logged sets yet
    for ex in exercises_for_muscle[current_index + 1:]:
        we = WorkoutExercise.query.filter_by(
            session_id=session_id,
            exercise_name=ex['name']
        ).first()
        
        if we:
            # Check if this exercise has logged sets
            logged_sets_count = LoggedSet.query.filter_by(
                workout_exercise_id=we.id
            ).count()
            
            # If no sets logged, this exercise is still pending
            if logged_sets_count == 0:
                return False
        else:
            # Exercise hasn't been started yet
            return False
    
    # All subsequent exercises for this muscle group have been completed
    return True

def check_muscle_group_feedback_exists(session_id, muscle_group):
    """
    Check if muscle group feedback exists for a session.
    
    Args:
        session_id: ID of the workout session
        muscle_group: Muscle group to check
    
    Returns:
        Boolean indicating if feedback exists
    """
    feedback = MuscleGroupFeedback.query.filter_by(
        session_id=session_id,
        muscle_group=muscle_group
    ).first()
    
    return feedback is not None

def save_muscle_group_feedback(session_id, muscle_group, overall_feeling, notes):
    """
    Save feedback for a muscle group.
    
    Args:
        session_id: ID of the workout session
        muscle_group: Muscle group name
        overall_feeling: Overall feeling rating (1-5)
        notes: Optional notes about the muscle group workout
    
    Returns:
        None
    """
    # Check if feedback already exists
    feedback = MuscleGroupFeedback.query.filter_by(
        session_id=session_id,
        muscle_group=muscle_group
    ).first()
    
    if feedback:
        # Update existing feedback
        feedback.overall_feeling = overall_feeling
        feedback.notes = notes
    else:
        # Create new feedback
        feedback = MuscleGroupFeedback(
            session_id=session_id,
            muscle_group=muscle_group,
            overall_feeling=overall_feeling,
            notes=notes
        )
        db.session.add(feedback)
    
    db.session.commit()
