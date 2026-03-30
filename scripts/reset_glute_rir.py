"""
One-time script to reset Glute RIR progression after replacing
"Hip Thrust + Glute Lunges" with separate Hip Thrust / Glute Kickbacks.

Actions:
1. Deletes all Feedback records where muscle_group = "Glutes"
2. Renames old exercise's muscle_group to "Glutes_Legacy" so old session/set
   data doesn't pollute the new muscle group queries

Run once: python reset_glute_rir.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_session, Feedback, Exercise


def main():
    with get_session() as db:
        # 1. Clear all Glute feedback history
        deleted = (
            db.query(Feedback)
            .filter(Feedback.muscle_group == "Glutes")
            .delete()
        )
        print(f"Deleted {deleted} Glutes feedback record(s)")

        # 2. Isolate old exercise so its session data doesn't affect new muscle group queries
        old_exercise = (
            db.query(Exercise)
            .filter(Exercise.name == "Hip Thrust + Glute Lunges")
            .first()
        )
        if old_exercise:
            old_exercise.muscle_group = "Glutes_Legacy"
            db.add(old_exercise)
            print(f"Updated '{old_exercise.name}' muscle_group -> 'Glutes_Legacy'")
        else:
            print("No 'Hip Thrust + Glute Lunges' exercise found (already clean)")

        db.commit()
        print("Done! Glute RIR has been reset to a fresh start.")


if __name__ == "__main__":
    main()
