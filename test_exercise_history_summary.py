import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT_DIR = Path(__file__).resolve().parent
API_DIR = ROOT_DIR / "api"

sys.path.insert(0, str(API_DIR))
sys.path.insert(1, str(ROOT_DIR))

import db as api_db
import services as api_services
from routes import exercises as exercise_routes


def make_set(session_id, set_number, weight, reps):
    return SimpleNamespace(
        session_id=session_id,
        set_number=set_number,
        weight=weight,
        reps=reps,
    )


class ExerciseHistorySummaryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        api_db.Base.metadata.create_all(engine)
        self.SessionLocal = sessionmaker(bind=engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()

    def seed_workout(self):
        program = api_db.Program(name="Test Program")
        self.db.add(program)
        self.db.flush()

        workout = api_db.Workout(
            program_id=program.id,
            name="Workout A",
            day_label="Day 1",
        )
        self.db.add(workout)
        self.db.flush()
        return workout

    def add_session(self, workout_id, session_number, completed):
        session = api_db.Session(
            workout_id=workout_id,
            session_number=session_number,
            rotation_index=0,
            completed=completed,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def add_sets(self, session_id, workout_exercise_id, reps, weight=150.0):
        for idx, rep_count in enumerate(reps, start=1):
            self.db.add(
                api_db.Set(
                    session_id=session_id,
                    workout_exercise_id=workout_exercise_id,
                    set_number=idx,
                    weight=weight,
                    reps=rep_count,
                )
            )
        self.db.flush()

    def test_build_last_session_metadata_returns_none_without_history(self):
        summary, recommendation = api_services.build_last_session_metadata([])
        self.assertIsNone(summary)
        self.assertIsNone(recommendation)

    def test_build_last_session_metadata_does_not_trigger_at_12_reps(self):
        last_sets = [
            make_set(1, 1, 150.0, 12),
            make_set(1, 2, 150.0, 12),
            make_set(1, 3, 150.0, 13),
            make_set(1, 4, 150.0, 12),
            make_set(1, 5, 150.0, 11),
        ]

        summary, recommendation = api_services.build_last_session_metadata(last_sets)

        self.assertEqual(
            summary,
            {"last_weight": 150.0, "avg_reps": 12, "set_count": 5},
        )
        self.assertIsNone(recommendation)

    def test_build_last_session_metadata_requires_first_set_15(self):
        last_sets = [
            make_set(1, 1, 50.0, 14),
            make_set(1, 2, 50.0, 15),
            make_set(1, 3, 50.0, 15),
            make_set(1, 4, 50.0, 15),
        ]

        _, recommendation = api_services.build_last_session_metadata(last_sets)

        self.assertIsNone(recommendation)

    def test_build_last_session_metadata_does_not_trigger_at_2_of_5_sets(self):
        last_sets = [
            make_set(1, 1, 50.0, 12),
            make_set(1, 2, 50.0, 12),
            make_set(1, 3, 50.0, 11),
            make_set(1, 4, 50.0, 10),
            make_set(1, 5, 50.0, 9),
        ]

        summary, recommendation = api_services.build_last_session_metadata(last_sets)

        self.assertIsNotNone(summary)
        self.assertIsNone(recommendation)

    def test_build_last_session_metadata_triggers_strong_at_4_of_5_sets(self):
        last_sets = [
            make_set(1, 1, 150.0, 15),
            make_set(1, 2, 150.0, 15),
            make_set(1, 3, 150.0, 16),
            make_set(1, 4, 150.0, 15),
            make_set(1, 5, 150.0, 14),
        ]

        _, recommendation = api_services.build_last_session_metadata(last_sets)

        self.assertEqual(recommendation["level"], "strong")
        self.assertEqual(
            recommendation["message"],
            api_services.WEIGHT_RECOMMENDATION_STRONG,
        )

    def test_get_exercise_last_session_metadata_uses_most_recent_completed_session(self):
        workout = self.seed_workout()
        exercise = api_services.get_or_create_workout_exercise(self.db, workout, "Leg Extension", 0)
        self.db.flush()

        session_1 = self.add_session(workout.id, session_number=1, completed=1)
        session_2 = self.add_session(workout.id, session_number=2, completed=1)
        current_session = self.add_session(workout.id, session_number=3, completed=0)

        self.add_sets(session_1.id, exercise.id, reps=[10, 10, 10, 10], weight=120.0)
        self.add_sets(session_2.id, exercise.id, reps=[15, 12, 12, 11], weight=150.0)
        self.db.commit()

        summary, recommendation = api_services.get_exercise_last_session_metadata(
            self.db,
            workout_exercise_id=exercise.id,
            before_session_number=current_session.session_number,
        )

        self.assertEqual(summary["last_weight"], 150.0)
        self.assertEqual(summary["avg_reps"], 12)
        self.assertEqual(recommendation["level"], "standard")

    def test_get_exercise_last_session_metadata_ignores_current_in_progress_session(self):
        workout = self.seed_workout()
        exercise = api_services.get_or_create_workout_exercise(self.db, workout, "Leg Extension", 0)
        self.db.flush()

        previous_session = self.add_session(workout.id, session_number=1, completed=1)
        current_session = self.add_session(workout.id, session_number=2, completed=0)

        self.add_sets(previous_session.id, exercise.id, reps=[15, 12, 12, 11], weight=150.0)
        self.add_sets(current_session.id, exercise.id, reps=[20, 20, 20, 20], weight=200.0)
        self.db.commit()

        summary, recommendation = api_services.get_exercise_last_session_metadata(
            self.db,
            workout_exercise_id=exercise.id,
            before_session_number=current_session.session_number,
        )

        self.assertEqual(summary["last_weight"], 150.0)
        self.assertEqual(recommendation["level"], "standard")

    def test_get_exercise_last_session_metadata_is_isolated_to_same_exercise(self):
        workout = self.seed_workout()
        leg_extension = api_services.get_or_create_workout_exercise(
            self.db,
            workout,
            "Leg Extension",
            0,
        )
        sissy_squat = api_services.get_or_create_workout_exercise(
            self.db,
            workout,
            "Sissy Squat",
            1,
        )
        self.db.flush()

        previous_session = self.add_session(workout.id, session_number=1, completed=1)
        current_session = self.add_session(workout.id, session_number=2, completed=0)

        self.add_sets(previous_session.id, sissy_squat.id, reps=[15, 15, 15, 15], weight=80.0)
        self.db.commit()

        summary, recommendation = api_services.get_exercise_last_session_metadata(
            self.db,
            workout_exercise_id=leg_extension.id,
            before_session_number=current_session.session_number,
        )

        self.assertIsNone(summary)
        self.assertIsNone(recommendation)

    def test_get_workout_data_serializes_last_session_fields(self):
        workout = self.seed_workout()
        leg_extension = api_services.get_or_create_workout_exercise(
            self.db,
            workout,
            "Leg Extension",
            0,
        )
        self.db.flush()

        previous_session = self.add_session(workout.id, session_number=1, completed=1)
        current_session = self.add_session(workout.id, session_number=2, completed=0)

        self.add_sets(previous_session.id, leg_extension.id, reps=[15, 12, 12, 11], weight=150.0)
        self.db.commit()

        result = exercise_routes.get_workout_data(session_id=current_session.id, db=self.db)
        quad_exercises = result.muscle_groups["Quads"].exercises
        leg_extension_payload = next(ex for ex in quad_exercises if ex.name == "Leg Extension")

        self.assertIsNotNone(leg_extension_payload.last_session_summary)
        self.assertEqual(leg_extension_payload.last_session_summary.last_weight, 150.0)
        self.assertEqual(leg_extension_payload.last_session_summary.avg_reps, 12)
        self.assertIsNotNone(leg_extension_payload.weight_recommendation)
        self.assertEqual(leg_extension_payload.weight_recommendation.level, "standard")
        self.assertEqual(
            leg_extension_payload.weight_recommendation.message,
            api_services.WEIGHT_RECOMMENDATION_STANDARD,
        )
        self.assertIsNone(leg_extension_payload.weight_recommendation.context_note)


if __name__ == "__main__":
    unittest.main()
