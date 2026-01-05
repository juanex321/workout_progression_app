from db import init_db, get_session, Program, Workout, Exercise, WorkoutExercise

def main():
    init_db()
    with get_session() as db:
        if db.query(Program).count() > 0:
            print("DB already seeded.")
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

        # Example exercises for that day
        leg_ext = Exercise(name="Leg Extension", muscle_group="Quads")
        lat_raise = Exercise(name="Dumbbell Lateral Raise", muscle_group="Shoulders")
        db.add_all([leg_ext, lat_raise])
        db.flush()

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
        print("Seeded DB.")


if __name__ == "__main__":
    main()
