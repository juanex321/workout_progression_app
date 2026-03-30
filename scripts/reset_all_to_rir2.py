"""
One-time script to reset all muscle group RIR progression to RIR 2 (calibration phase).

Why:
The progression system now reads the last logged RIR per muscle group to determine
which phase a muscle is in. This script resets all logged RIR values to 2 so every
muscle group starts fresh in the calibration phase and advances only once feedback
confirms sufficient stimulus (pump >= 2, workload >= 3 for 2 consecutive sessions).

What changes:
- Set.rir column → 2 for all sets in completed sessions
- Nothing else is touched: weights, reps, set counts, sessions, and feedback are preserved

Run once: python reset_all_to_rir2.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_session, Set, Session, Exercise, WorkoutExercise


def preview(db):
    """Print a summary of current RIR distribution before making changes."""
    results = (
        db.query(Exercise.muscle_group, Set.rir)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .join(Session, Set.session_id == Session.id)
        .filter(Session.completed == 1)
        .filter(Set.rir.isnot(None))
        .all()
    )

    if not results:
        print("No completed sessions with logged RIR found — nothing to reset.")
        return 0

    # Most recent RIR per muscle group
    from sqlalchemy import func
    latest = (
        db.query(Exercise.muscle_group, Set.rir)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .join(Session, Set.session_id == Session.id)
        .filter(Session.completed == 1)
        .filter(Set.rir.isnot(None))
        .order_by(Session.session_number.desc(), Set.logged_at.desc())
        .all()
    )

    seen = {}
    for muscle, rir in latest:
        if muscle not in seen:
            seen[muscle] = rir

    print(f"\nCurrent last RIR per muscle group ({len(seen)} muscle groups):")
    print(f"  {'Muscle Group':<22} {'Current RIR':>12}  {'After Reset':>12}")
    print(f"  {'-'*22}  {'-'*12}  {'-'*12}")
    already_at_2 = 0
    for muscle, rir in sorted(seen.items()):
        marker = "  (already 2)" if rir == 2 else ""
        print(f"  {muscle:<22} {str(rir):>12}  {'2':>12}{marker}")
        if rir == 2:
            already_at_2 += 1

    total_sets = len(results)
    needs_update = sum(1 for _, rir in results if rir != 2)
    print(f"\nTotal sets in completed sessions: {total_sets}")
    print(f"Sets that will be updated (rir != 2): {needs_update}")
    print(f"Muscle groups already at RIR 2: {already_at_2}/{len(seen)}")
    return needs_update


def main():
    with get_session() as db:
        needs_update = preview(db)

        if needs_update == 0:
            print("\nAll sets are already at RIR 2. Nothing to do.")
            return

        confirm = input("\nProceed with reset? This will update RIR to 2 on all "
                        "completed-session sets. (y/N): ").strip().lower()
        if confirm != "y":
            print("Aborted — no changes made.")
            return

        # Fetch IDs first (joins block bulk .update()), then update by ID
        set_ids = [
            row[0] for row in (
                db.query(Set.id)
                .join(Session, Set.session_id == Session.id)
                .filter(Session.completed == 1)
                .filter(Set.rir.isnot(None))
                .filter(Set.rir != 2)
                .all()
            )
        ]
        updated = (
            db.query(Set)
            .filter(Set.id.in_(set_ids))
            .update({Set.rir: 2}, synchronize_session=False)
        )

        db.commit()
        print(f"\nDone — updated {updated} set(s) to RIR 2.")
        print("All muscle groups will now begin in the calibration phase.")
        print("Progression to RIR 1 will happen automatically once feedback confirms")
        print("pump >= 2 and workload >= 3 for 2 consecutive sessions.")


if __name__ == "__main__":
    main()
