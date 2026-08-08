import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from db import Base, Exercise, Feedback, Program, Session, Set, Workout, WorkoutExercise
from progression import (
    _allocate_muscle_sets_to_exercise,
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
        completed = self.add_session(1, completed=1)
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
        self.assertEqual(compute_feedback_adjustment(self.db, "Chest"), 0)

    def test_biceps_sets_follow_recent_volume_without_cap(self):
        """High recent volume is preserved instead of clamped to a fixed ceiling."""
        cable_curl = self.add_we("Cable Curl", "Biceps", target_sets=8, target_reps=15)
        incline_curl = self.add_we("Incline DB Curl", "Biceps", target_sets=1, target_reps=14)

        for session_number, total_sets in enumerate((9, 11, 11, 9, 8), start=1):
            session = self.add_session(session_number)
            main_sets = total_sets - 1
            self.add_sets(session, cable_curl, count=main_sets)
            self.add_sets(session, incline_curl, count=1, weight=15.0)
            self.add_feedback(session, "Biceps", soreness=2, pump=4, workload=3)
        self.db.commit()

        main_recommendations = recommend_weights_and_reps(self.db, cable_curl, "Biceps")
        secondary_recommendations = recommend_weights_and_reps(self.db, incline_curl, "Biceps")

        # The latest total is 8 and is split approximately 70/30.
        self.assertEqual(len(main_recommendations), 6)
        self.assertEqual(len(secondary_recommendations), 2)

    def test_two_exercise_volume_uses_seventy_thirty_split(self):
        main = self.add_we("Cable Curl", "Biceps")
        secondary = self.add_we("Incline DB Curl", "Biceps", target_sets=1)

        expected_splits = {
            4: (3, 1),
            5: (4, 1),
            6: (4, 2),
            7: (5, 2),
            10: (7, 3),
        }
        for total_sets, expected in expected_splits.items():
            with self.subTest(total_sets=total_sets):
                self.assertEqual(
                    _allocate_muscle_sets_to_exercise(
                        self.db, main, "Biceps", total_sets
                    ),
                    expected[0],
                )
                self.assertEqual(
                    _allocate_muscle_sets_to_exercise(
                        self.db, secondary, "Biceps", total_sets
                    ),
                    expected[1],
                )

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
