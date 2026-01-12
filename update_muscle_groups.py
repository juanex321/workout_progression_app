"""
Script to update muscle groups for all exercises in the database.
"""
from db import get_session, Exercise

# Define muscle groups for each exercise
EXERCISE_MUSCLE_GROUPS = {
    # Leg exercises
    "Leg Extension": "Quads",
    "Sissy Squat": "Quads",
    "Leg Curl": "Hamstrings",
    "Hip Thrust + Glute Lunges": "Glutes",
    
    # Push exercises - Chest
    "Incline DB Bench Press": "Chest",
    "Single-arm Chest Fly": "Chest",
    
    # Push exercises - Triceps
    "Cable Tricep Pushdown": "Triceps",
    "Overhead Cable Extension": "Triceps",
    
    # Pull exercises - Lats
    "Lat Pulldown": "Lats",
    "Cable Row": "Lats",
    "Straight-arm Pulldown": "Lats",
    
    # Pull exercises - Biceps
    "Cable Curl": "Biceps",
    "Incline DB Curl": "Biceps",
    
    # Shoulders
    "Dumbbell Lateral Raise": "Shoulders",
}

def main():
    with get_session() as db:
        updated_count = 0
        created_count = 0
        
        for exercise_name, muscle_group in EXERCISE_MUSCLE_GROUPS.items():
            exercise = db.query(Exercise).filter(Exercise.name.ilike(exercise_name)).first()
            
            if exercise:
                if exercise.muscle_group != muscle_group:
                    exercise.muscle_group = muscle_group
                    updated_count += 1
                    print(f"Updated: {exercise_name} -> {muscle_group}")
                else:
                    print(f"Already set: {exercise_name} -> {muscle_group}")
            else:
                # Create the exercise if it doesn't exist
                exercise = Exercise(name=exercise_name, muscle_group=muscle_group)
                db.add(exercise)
                created_count += 1
                print(f"Created: {exercise_name} -> {muscle_group}")
        
        db.commit()
        print(f"\nSummary: Created {created_count}, Updated {updated_count} exercises")

if __name__ == "__main__":
    main()
