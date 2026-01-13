from db import init_db, get_session, Program, Workout, Exercise, WorkoutExercise
from plan import EXERCISE_MUSCLE_GROUPS

def main():
    init_db()
    with get_session() as db:
        # Pre-create all exercises from the workout rotation
        exercises_created = 0
        for exercise_name, muscle_group in EXERCISE_MUSCLE_GROUPS.items():
            existing_exercise = (
                db.query(Exercise)
                .filter(Exercise.name.ilike(exercise_name))
                .first()
            )
            if not existing_exercise:
                exercise = Exercise(name=exercise_name, muscle_group=muscle_group)
                db.add(exercise)
                exercises_created += 1
        
        if exercises_created > 0:
            db.commit()
            print(f"Created {exercises_created} new exercises.")
        else:
            print("All exercises already exist.")
        
        if db.query(Program).count() > 0:
            print("Program already seeded.")
            return

        prog = Program(name="Full Body IV")
        db.add(prog)
        db.flush()

        w = Workout(
            program_id=prog.id,
            name="Week 6 Day 4",
            day_label="W6D4 Thursday"
        )
        db.add(w)
        db.flush()

        # Get exercises for the example workout
        leg_ext = db.query(Exercise).filter(Exercise.name.ilike("Leg Extension")).first()
        lat_raise = db.query(Exercise).filter(Exercise.name.ilike("Dumbbell Lateral Raise")).first()

        we1 = WorkoutExercise(
            workout_id=w.id,
            exercise_id=leg_ext.id,
            order_index=1,
            target_sets=7,
            target_reps=10,
        )
        we2 = WorkoutExercise(
            workout_id=w.id,
            exercise_id=lat_raise.id,
            order_index=2,
            target_sets=7,
            target_reps=10,
        )
        db.add_all([we1, we2])
        db.commit()
        print("Seeded program and workout.")


if __name__ == "__main__":
    main()
