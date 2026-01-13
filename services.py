"""
Service functions for the workout progression app.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from models import (
    db, User, Workout, WorkoutExercise, ExerciseLog, MuscleGroup, 
    Exercise, WorkoutTemplate, TemplateExercise, FeedbackForm
)
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload
import logging

logger = logging.getLogger(__name__)


def create_workout_from_template(user_id: int, template_id: int) -> Workout:
    """
    Create a new workout instance from a template.
    
    Args:
        user_id: ID of the user creating the workout
        template_id: ID of the template to use
        
    Returns:
        The newly created Workout instance
        
    Raises:
        ValueError: If template not found or doesn't belong to user
    """
    template = WorkoutTemplate.query.filter_by(
        id=template_id, 
        user_id=user_id
    ).first()
    
    if not template:
        raise ValueError("Template not found or doesn't belong to user")
    
    # Create new workout
    workout = Workout(
        user_id=user_id,
        template_id=template_id,
        name=template.name,
        start_time=datetime.utcnow()
    )
    db.session.add(workout)
    db.session.flush()  # Get workout.id
    
    # Copy exercises from template
    for template_exercise in template.exercises:
        workout_exercise = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=template_exercise.exercise_id,
            target_sets=template_exercise.target_sets,
            target_reps=template_exercise.target_reps,
            order=template_exercise.order
        )
        db.session.add(workout_exercise)
    
    db.session.commit()
    return workout


def log_exercise_set(
    workout_id: int,
    exercise_id: int,
    set_number: int,
    reps: int,
    weight: float,
    user_id: int
) -> ExerciseLog:
    """
    Log a completed set for an exercise.
    
    Args:
        workout_id: ID of the current workout
        exercise_id: ID of the exercise
        set_number: Which set number this is
        reps: Number of reps completed
        weight: Weight used
        user_id: ID of the user (for verification)
        
    Returns:
        The newly created ExerciseLog instance
        
    Raises:
        ValueError: If workout not found or doesn't belong to user
    """
    # Verify workout belongs to user
    workout = Workout.query.filter_by(
        id=workout_id,
        user_id=user_id
    ).first()
    
    if not workout:
        raise ValueError("Workout not found or doesn't belong to user")
    
    # Verify exercise is part of workout
    workout_exercise = WorkoutExercise.query.filter_by(
        workout_id=workout_id,
        exercise_id=exercise_id
    ).first()
    
    if not workout_exercise:
        raise ValueError("Exercise not part of this workout")
    
    # Create exercise log
    exercise_log = ExerciseLog(
        workout_id=workout_id,
        exercise_id=exercise_id,
        set_number=set_number,
        reps=reps,
        weight=weight,
        timestamp=datetime.utcnow()
    )
    db.session.add(exercise_log)
    db.session.commit()
    
    return exercise_log


def get_workout_progress(workout_id: int, user_id: int) -> Dict:
    """
    Get progress information for a workout.
    
    Args:
        workout_id: ID of the workout
        user_id: ID of the user (for verification)
        
    Returns:
        Dictionary containing progress information
        
    Raises:
        ValueError: If workout not found or doesn't belong to user
    """
    workout = Workout.query.filter_by(
        id=workout_id,
        user_id=user_id
    ).first()
    
    if not workout:
        raise ValueError("Workout not found or doesn't belong to user")
    
    # Get all exercises for this workout
    workout_exercises = WorkoutExercise.query.filter_by(
        workout_id=workout_id
    ).all()
    
    progress = {
        'workout_id': workout_id,
        'workout_name': workout.name,
        'start_time': workout.start_time,
        'exercises': []
    }
    
    for we in workout_exercises:
        # Count logged sets
        logged_sets = ExerciseLog.query.filter_by(
            workout_id=workout_id,
            exercise_id=we.exercise_id
        ).count()
        
        exercise_info = {
            'exercise_id': we.exercise_id,
            'exercise_name': we.exercise.name,
            'target_sets': we.target_sets,
            'target_reps': we.target_reps,
            'logged_sets': logged_sets,
            'completed': logged_sets >= we.target_sets
        }
        progress['exercises'].append(exercise_info)
    
    # Calculate overall progress
    total_sets = sum(e['target_sets'] for e in progress['exercises'])
    completed_sets = sum(e['logged_sets'] for e in progress['exercises'])
    progress['total_progress'] = {
        'completed_sets': completed_sets,
        'total_sets': total_sets,
        'percentage': (completed_sets / total_sets * 100) if total_sets > 0 else 0
    }
    
    return progress


def complete_workout(workout_id: int, user_id: int) -> Workout:
    """
    Mark a workout as complete.
    
    Args:
        workout_id: ID of the workout to complete
        user_id: ID of the user (for verification)
        
    Returns:
        The updated Workout instance
        
    Raises:
        ValueError: If workout not found or doesn't belong to user
    """
    workout = Workout.query.filter_by(
        id=workout_id,
        user_id=user_id
    ).first()
    
    if not workout:
        raise ValueError("Workout not found or doesn't belong to user")
    
    workout.end_time = datetime.utcnow()
    workout.completed = True
    db.session.commit()
    
    return workout


def check_muscle_group_completion(workout_id: int, muscle_group_id: int) -> bool:
    """
    Check if all exercises for a muscle group in a workout have been completed.
    
    Args:
        workout_id: ID of the workout
        muscle_group_id: ID of the muscle group to check
        
    Returns:
        True if all exercises for the muscle group are complete, False otherwise
    """
    # Get all exercises for this muscle group in the workout
    workout_exercises = db.session.query(WorkoutExercise).join(
        Exercise
    ).filter(
        WorkoutExercise.workout_id == workout_id,
        Exercise.muscle_group_id == muscle_group_id
    ).all()
    
    if not workout_exercises:
        return False
    
    # Check if all exercises have completed their target sets
    for we in workout_exercises:
        logged_sets_count = ExerciseLog.query.filter_by(
            workout_id=workout_id,
            exercise_id=we.exercise_id
        ).count()
        
        # FIX: Check if there are ANY logged sets (meaning the exercise has been started)
        # An exercise is considered complete if at least 1 set is logged
        # This allows the feedback form to appear when all exercises for a muscle group
        # have been worked, regardless of whether all target sets were completed
        if logged_sets_count == 0:
            return False
    
    return True


def save_muscle_feedback(
    user_id: int,
    workout_id: int,
    muscle_group_id: int,
    soreness_level: int,
    pump_level: int,
    notes: Optional[str] = None
) -> FeedbackForm:
    """
    Save feedback for a muscle group after completing its exercises.
    
    Args:
        user_id: ID of the user providing feedback
        workout_id: ID of the workout
        muscle_group_id: ID of the muscle group
        soreness_level: Soreness rating (1-10)
        pump_level: Pump rating (1-10)
        notes: Optional notes
        
    Returns:
        The created FeedbackForm instance
        
    Raises:
        ValueError: If validation fails
    """
    # Validate soreness and pump levels
    if not (1 <= soreness_level <= 10):
        raise ValueError("Soreness level must be between 1 and 10")
    if not (1 <= pump_level <= 10):
        raise ValueError("Pump level must be between 1 and 10")
    
    # Verify workout belongs to user
    workout = Workout.query.filter_by(
        id=workout_id,
        user_id=user_id
    ).first()
    
    if not workout:
        raise ValueError("Workout not found or doesn't belong to user")
    
    # Check if feedback already exists for this muscle group in this workout
    existing_feedback = FeedbackForm.query.filter_by(
        workout_id=workout_id,
        muscle_group_id=muscle_group_id
    ).first()
    
    if existing_feedback:
        # Update existing feedback
        existing_feedback.soreness_level = soreness_level
        existing_feedback.pump_level = pump_level
        existing_feedback.notes = notes
        existing_feedback.timestamp = datetime.utcnow()
        db.session.commit()
        return existing_feedback
    
    # Create new feedback
    feedback = FeedbackForm(
        user_id=user_id,
        workout_id=workout_id,
        muscle_group_id=muscle_group_id,
        soreness_level=soreness_level,
        pump_level=pump_level,
        notes=notes,
        timestamp=datetime.utcnow()
    )
    db.session.add(feedback)
    db.session.commit()
    
    return feedback


def get_muscle_group_history(
    user_id: int,
    muscle_group_id: int,
    limit: int = 10
) -> List[Dict]:
    """
    Get feedback history for a specific muscle group.
    
    Args:
        user_id: ID of the user
        muscle_group_id: ID of the muscle group
        limit: Maximum number of records to return
        
    Returns:
        List of feedback records with workout information
    """
    feedbacks = FeedbackForm.query.filter_by(
        user_id=user_id,
        muscle_group_id=muscle_group_id
    ).order_by(
        FeedbackForm.timestamp.desc()
    ).limit(limit).all()
    
    history = []
    for feedback in feedbacks:
        workout = Workout.query.get(feedback.workout_id)
        history.append({
            'feedback_id': feedback.id,
            'workout_id': feedback.workout_id,
            'workout_name': workout.name if workout else 'Unknown',
            'workout_date': workout.start_time if workout else None,
            'soreness_level': feedback.soreness_level,
            'pump_level': feedback.pump_level,
            'notes': feedback.notes,
            'timestamp': feedback.timestamp
        })
    
    return history


def get_exercise_history(
    user_id: int,
    exercise_id: int,
    limit: int = 10
) -> List[Dict]:
    """
    Get performance history for a specific exercise.
    
    Args:
        user_id: ID of the user
        exercise_id: ID of the exercise
        limit: Maximum number of workouts to return
        
    Returns:
        List of workout sessions with exercise performance data
    """
    # Get recent workouts that included this exercise
    workout_logs = db.session.query(
        Workout.id,
        Workout.name,
        Workout.start_time,
        func.max(ExerciseLog.weight).label('max_weight'),
        func.count(ExerciseLog.id).label('total_sets')
    ).join(
        ExerciseLog, Workout.id == ExerciseLog.workout_id
    ).filter(
        Workout.user_id == user_id,
        ExerciseLog.exercise_id == exercise_id,
        Workout.completed == True
    ).group_by(
        Workout.id, Workout.name, Workout.start_time
    ).order_by(
        Workout.start_time.desc()
    ).limit(limit).all()
    
    history = []
    for log in workout_logs:
        # Get all sets for this exercise in this workout
        sets = ExerciseLog.query.filter_by(
            workout_id=log.id,
            exercise_id=exercise_id
        ).order_by(ExerciseLog.set_number).all()
        
        history.append({
            'workout_id': log.id,
            'workout_name': log.name,
            'workout_date': log.start_time,
            'max_weight': float(log.max_weight),
            'total_sets': log.total_sets,
            'sets': [
                {
                    'set_number': s.set_number,
                    'reps': s.reps,
                    'weight': float(s.weight)
                }
                for s in sets
            ]
        })
    
    return history


def get_personal_records(user_id: int, exercise_id: int) -> Dict:
    """
    Get personal records for a specific exercise.
    
    Args:
        user_id: ID of the user
        exercise_id: ID of the exercise
        
    Returns:
        Dictionary containing PR information
    """
    # Get max weight ever lifted
    max_weight_log = ExerciseLog.query.join(
        Workout
    ).filter(
        Workout.user_id == user_id,
        ExerciseLog.exercise_id == exercise_id
    ).order_by(
        ExerciseLog.weight.desc()
    ).first()
    
    # Get max reps at any weight
    max_reps_log = ExerciseLog.query.join(
        Workout
    ).filter(
        Workout.user_id == user_id,
        ExerciseLog.exercise_id == exercise_id
    ).order_by(
        ExerciseLog.reps.desc()
    ).first()
    
    # Get max volume (weight * reps) for a single set
    volume_logs = db.session.query(
        ExerciseLog,
        (ExerciseLog.weight * ExerciseLog.reps).label('volume')
    ).join(
        Workout
    ).filter(
        Workout.user_id == user_id,
        ExerciseLog.exercise_id == exercise_id
    ).order_by(
        (ExerciseLog.weight * ExerciseLog.reps).desc()
    ).first()
    
    return {
        'max_weight': {
            'weight': float(max_weight_log.weight) if max_weight_log else None,
            'reps': max_weight_log.reps if max_weight_log else None,
            'date': max_weight_log.timestamp if max_weight_log else None
        },
        'max_reps': {
            'reps': max_reps_log.reps if max_reps_log else None,
            'weight': float(max_reps_log.weight) if max_reps_log else None,
            'date': max_reps_log.timestamp if max_reps_log else None
        },
        'max_volume': {
            'volume': float(volume_logs[1]) if volume_logs else None,
            'weight': float(volume_logs[0].weight) if volume_logs else None,
            'reps': volume_logs[0].reps if volume_logs else None,
            'date': volume_logs[0].timestamp if volume_logs else None
        } if volume_logs else {
            'volume': None,
            'weight': None,
            'reps': None,
            'date': None
        }
    }
