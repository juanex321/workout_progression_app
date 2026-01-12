"""
Script to update muscle groups for all exercises in the database.
"""
from db import get_session, Exercise
from plan import EXERCISE_MUSCLE_GROUPS

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
