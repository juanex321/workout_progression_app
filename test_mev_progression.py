import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from db import Base, Exercise, Feedback, Program, Session, Set, Workout, WorkoutExercise
from progression import (
    adjust_sets_based_on_feedback,
    compute_feedback_adjustment,
    get_recent_muscle_group_feedback,
    recommend_weights_and_reps,
)
from plan import get_session_exercises


class MevProgressionTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.SessionLocal = sessionmaker(bind=engine)
        self.db = self.SessionLocal()

        program = Program(name="Test")
        self.db.add(program)
        self.db.flush()
        self.workout = Workout(program_id=program.id, name="Test Workout", day_label="Day")
        self.db.add(self.workout)
        self.db.flush()

    def tearDown(self):
        self.db.close()

    def add_we(self, name, muscle_group, target_sets=4, target_reps=10, order_index=0):
        exercise = Exercise(name=name, muscle_group=muscle_group)
        self.db.add(exercise)
        self.db.flush()
        we = WorkoutExercise(
            workout_id=self.workout.id,
            exercise_id=exercise.id,
            order_index=order_index,
            target_sets=target_sets,
            target_reps=target_reps,
        )
        we.exercise = exercise
        self.db.add(we)
        self.db.flush()
        return we

    def add_session(self, session_number, completed=1):
        session = Session(
            workout_id=self.workout.id,
            session_number=session_number,
            rotation_index=0,
            completed=completed,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def add_sets(self, session, we, count, weight=30.0, first_reps=12):
        for set_number in range(1, count + 1):
            self.db.add(
                Set(
                    session_id=session.id,
                    workout_exercise_id=we.id,
                    set_number=set_number,
                    weight=weight,
                    reps=max(5, first_reps - set_number + 1),
                )
            )
        self.db.flush()

    def add_feedback(self, session, muscle_group, soreness, pump, workload):
        self.db.add(
            Feedback(
                session_id=session.id,
                muscle_group=muscle_group,
                soreness=soreness,
                pump=pump,
                workload=workload,
            )
        )
        self.db.flush()

    def test_incomplete_soreness_only_feedback_is_ignored(self):
        chest_press = self.add_we("Incline DB Bench Press", "Chest")
        completed = self.add_session(1, completed=1)
        self.add_sets(completed, chest_press, count=4)
        current = self.add_session(2, completed=0)
        self.add_feedback(completed, "Chest", soreness=2, pump=3, workload=3)
        self.db.add(
            Feedback(
                session_id=current.id,
                muscle_group="Chest",
                soreness=4,
                pump=None,
                workload=None,
            )
        )
        self.db.commit()

        feedback = get_recent_muscle_group_feedback(self.db, "Chest", limit=3)

        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0].session_id, completed.id)
        self.assertEqual(compute_feedback_adjustment(self.db, chest_press, "Chest"), 0)

    def test_biceps_sets_follow_recent_volume_without_cap(self):
        """Each exercise's own recent volume is preserved instead of a fixed ceiling
        or a 70/30 split of a shared muscle-group total."""
        cable_curl = self.add_we("Cable Curl", "Biceps", target_sets=8, target_reps=15)
        incline_curl = self.add_we("Incline DB Curl", "Biceps", target_sets=1, target_reps=14)

        for session_number, main_sets in enumerate((8, 10, 10, 8, 7), start=1):
            session = self.add_session(session_number)
            self.add_sets(session, cable_curl, count=main_sets)
            self.add_sets(session, incline_curl, count=1, weight=15.0)
            self.add_feedback(session, "Biceps", soreness=2, pump=4, workload=3)
        self.db.commit()

        main_recommendations = recommend_weights_and_reps(self.db, cable_curl, "Biceps")
        secondary_recommendations = recommend_weights_and_reps(self.db, incline_curl, "Biceps")

        # Each exercise anchors on its own last actual sets performed (7 and 1).
        self.assertEqual(len(main_recommendations), 7)
        self.assertEqual(len(secondary_recommendations), 1)

    def test_hamstring_movements_track_independently(self):
        """Feedback/history logged for one hamstring movement must not leak into
        the other's target - this is the movement-specific tracking fix."""
        leg_curl = self.add_we("Leg Curl", "Hamstrings", target_sets=4)
        rdl = self.add_we("Romanian Deadlift", "Hamstrings", target_sets=4)

        s1 = self.add_session(1)
        self.add_sets(s1, leg_curl, count=7)
        self.add_feedback(s1, "Hamstrings", soreness=2, pump=3, workload=3)

        # A different day/movement for the same muscle logs a soreness spike.
        s2 = self.add_session(2)
        self.add_sets(s2, rdl, count=4)
        self.add_feedback(s2, "Hamstrings", soreness=5, pump=2, workload=4)

        s3 = self.add_session(3)
        self.add_sets(s3, leg_curl, count=7)
        self.add_feedback(s3, "Hamstrings", soreness=2, pump=3, workload=3)
        self.db.commit()

        # Leg Curl's own neutral history/feedback holds it at 7, unaffected by
        # the RDL soreness spike logged in between.
        self.assertEqual(adjust_sets_based_on_feedback(self.db, leg_curl), 7)
        # RDL's own high-soreness feedback drops it by 1 from its own last total.
        self.assertEqual(adjust_sets_based_on_feedback(self.db, rdl), 3)

    def test_hamstring_target_preserves_high_neutral_volume(self):
        leg_curl = self.add_we("Leg Curl", "Hamstrings", target_sets=7)
        for session_number in (1, 2):
            session = self.add_session(session_number)
            self.add_sets(session, leg_curl, count=7)
            self.add_feedback(session, "Hamstrings", soreness=2, pump=3, workload=3)
        self.db.commit()

        target_sets = adjust_sets_based_on_feedback(self.db, leg_curl)

        self.assertEqual(target_sets, 7)

    def test_lower_body_and_upper_body_rotations_are_independent(self):
        self.assertEqual(get_session_exercises(0)[0], "Leg Extension")
        self.assertEqual(get_session_exercises(1)[0], "Leg Curl")
        self.assertEqual(get_session_exercises(2)[0], "Hip Thrust")
        self.assertEqual(get_session_exercises(3)[0], "Leg Extension")
        self.assertEqual(get_session_exercises(4)[0], "Romanian Deadlift")
        self.assertEqual(get_session_exercises(5)[0], "Hip Thrust")
        self.assertIn("Incline DB Bench Press", get_session_exercises(4))
        self.assertIn("Lat Pulldown", get_session_exercises(5))

    def test_new_rdls_start_at_fifty_pounds(self):
        rdl = self.add_we("Romanian Deadlift", "Hamstrings")
        self.db.commit()

        recommendations = recommend_weights_and_reps(self.db, rdl, "Hamstrings")

        self.assertTrue(recommendations)
        self.assertTrue(all(row["weight"] == 50.0 for row in recommendations))


if __name__ == "__main__":
    unittest.main()
