import streamlit as st
import pandas as pd
from datetime import date

from db import (
    get_session,
    Program,
    Workout,
    WorkoutExercise,
    Session,
    Set,
    Exercise,
    Feedback,
    DraftSet,   # NEW
)

try:
    from plan import get_session_exercises  # type: ignore
except Exception:
    get_session_exercises = None  # type: ignore

try:
    from progression import recommend_weights_and_reps  # type: ignore
except Exception:
    recommend_weights_and_reps = None  # type: ignore


# -----------------------------
# Plan fallback (if plan.py missing)
# -----------------------------
LEG_ROTATION = [
    "Leg Extension",
    "Leg Curl",
    "Hip Thrust + Glute Lunges",
]
PULL_MAIN_ROTATION = ["Lat Pulldown", "Cable Row"]
PULL_SECONDARY = "Cable Curl"
LATERAL_RAISES = "Dumbbell Lateral Raise"

DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10

EXERCISE_DEFAULT_SETS = {
    "Single-arm Chest Fly": 1,
    "Sissy Squat": 1,
    "Straight-arm Pulldown": 1,
    "Incline DB Curl": 1,
    "Overhead Cable Extension": 1,
}

# Muscle mapping for “divider only when muscle group changes”
EXERCISE_TO_MUSCLE = {
    # Quads
    "Leg Extension": "Quads",
    "Sissy Squat": "Quads",
    # Hams / Glutes
    "Leg Curl": "Hams",
    "Hip Thrust + Glute Lunges": "Glutes",
    # Chest
    "Incline DB Bench Press": "Chest",
    "Single-arm Chest Fly": "Chest",
    # Triceps
    "Cable Tricep Pushdown": "Triceps",
    "Overhead Cable Extension": "Triceps",
    # Back / Lats
    "Lat Pulldown": "Back",
    "Cable Row": "Back",
    "Straight-arm Pulldown": "Back",
    # Biceps
    "Cable Curl": "Biceps",
    "Incline DB Curl": "Biceps",
    # Delts
    "Dumbbell Lateral Raise": "Delts",
}


def fallback_get_session_exercises(session_index: int):
    leg_ex = LEG_ROTATION[session_index % len(LEG_ROTATION)]
    leg_block = [leg_ex]
    if leg_ex == "Leg Extension":
        leg_block.append("Sissy Squat")

    is_push_day = (session_index % 2 == 0)
    if is_push_day:
        upper_block = [
            "Incline DB Bench Press",
            "Single-arm Chest Fly",
            "Cable Tricep Pushdown",
            "Overhead Cable Extension",
        ]
    else:
        pull_session_number = session_index // 2
        pull_main = PULL_MAIN_ROTATION[pull_session_number % len(PULL_MAIN_ROTATION)]
        upper_block = [
            pull_main,
            "Straight-arm Pulldown",
            PULL_SECONDARY,
            "Incline DB Curl",
        ]

    return leg_block + upper_block + [LATERAL_RAISES]


# -----------------------------
# DB helpers
# -----------------------------
def get_or_create_today_session(db, workout_id: int):
    today = date.today()
    sess = (
        db.query(Session)
        .filter(Session.workout_id == workout_id, Session.date == today)
        .first()
    )
    if sess:
        return sess
    sess = Session(workout_id=workout_id, date=today)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def get_or_create_workout_exercise(db, workout: Workout, ex_name: str, order_index: int):
    name_normalized = ex_name.strip()

    exercise = (
        db.query(Exercise)
        .filter(Exercise.name.ilike(name_normalized))
        .first()
    )
    if not exercise:
        exercise = Exercise(name=name_normalized)
        db.add(exercise)
        db.flush()

    we = (
        db.query(WorkoutExercise)
        .filter(
            WorkoutExercise.workout_id == workout.id,
            WorkoutExercise.exercise_id == exercise.id,
        )
        .first()
    )
    if not we:
        target_sets = EXERCISE_DEFAULT_SETS.get(name_normalized, DEFAULT_TARGET_SETS)
        we = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=exercise.id,
            order_index=order_index,
            target_sets=target_sets,
            target_reps=DEFAULT_TARGET_REPS,
        )
        db.add(we)

    return we


def load_sets_or_draft_as_df(db, session_id: int, workout_exercise_id: int) -> pd.DataFrame | None:
    # If final sets exist, show them (done=True)
    final_sets = (
        db.query(Set)
        .filter(Set.session_id == session_id, Set.workout_exercise_id == workout_exercise_id)
        .order_by(Set.set_number.asc())
        .all()
    )
    if final_sets:
        return pd.DataFrame(
            [
                {"set_number": s.set_number, "weight": float(s.weight), "reps": int(s.reps), "done": True}
                for s in final_sets
            ]
        )

    # Else show draft if exists
    drafts = (
        db.query(DraftSet)
        .filter(DraftSet.session_id == session_id, DraftSet.workout_exercise_id == workout_exercise_id)
        .order_by(DraftSet.set_number.asc())
        .all()
    )
    if drafts:
        return pd.DataFrame(
            [
                {
                    "set_number": d.set_number,
                    "weight": float(d.weight),
                    "reps": int(d.reps),
                    "done": bool(d.done),
                }
                for d in drafts
            ]
        )

    return None


def save_draft_from_df(db, session_id: int, workout_exercise_id: int, df: pd.DataFrame):
    """Always persist current edits as draft so refresh doesn’t wipe progress."""
    if df is None or df.empty:
        return

    # Replace draft with the current table rows (including unchecked)
    db.query(DraftSet).filter(
        DraftSet.session_id == session_id,
        DraftSet.workout_exercise_id == workout_exercise_id,
    ).delete()

    df2 = df.copy().reset_index(drop=True)
    for i, row in df2.iterrows():
        # tolerate missing done column
        done_val = bool(row["done"]) if "done" in df2.columns else False
        ds = DraftSet(
            session_id=session_id,
            workout_exercise_id=workout_exercise_id,
            set_number=int(i + 1),
            weight=float(row["weight"]),
            reps=int(row["reps"]),
            done=1 if done_val else 0,
        )
        db.add(ds)

    db.commit()


def promote_draft_to_sets_if_complete(db, session_id: int, workout_exercise_id: int):
    """If all draft rows are checked, commit them to final Set table."""
    drafts = (
        db.query(DraftSet)
        .filter(DraftSet.session_id == session_id, DraftSet.workout_exercise_id == workout_exercise_id)
        .order_by(DraftSet.set_number.asc())
        .all()
    )
    if not drafts:
        return False

    if not all(d.done == 1 for d in drafts):
        return False

    # Replace final sets
    db.query(Set).filter(
        Set.session_id == session_id,
        Set.workout_exercise_id == workout_exercise_id,
    ).delete()

    for i, d in enumerate(drafts):
        s = Set(
            session_id=session_id,
            workout_exercise_id=workout_exercise_id,
            set_number=int(i + 1),
            weight=float(d.weight),
            reps=int(d.reps),
            rir=None,
        )
        db.add(s)

    # Clear draft after promote
    db.query(DraftSet).filter(
        DraftSet.session_id == session_id,
        DraftSet.workout_exercise_id == workout_exercise_id,
    ).delete()

    db.commit()
    return True


def muscle_for(ex_name: str) -> str:
    return EXERCISE_TO_MUSCLE.get(ex_name, "Other")


# -----------------------------
# Main app
# -----------------------------
def main():
    st.set_page_config(page_title="Workout", layout="centered")

    if "rotation_index" not in st.session_state:
        st.session_state["rotation_index"] = 0

    with get_session() as db:
        programs = db.query(Program).all()
        if not programs:
            st.error("No programs found. Run init_db.py first.")
            return

        prog = programs[0]
        workouts = (
            db.query(Workout)
            .filter(Workout.program_id == prog.id)
            .order_by(Workout.id.asc())
            .all()
        )
        if not workouts:
            st.error("No workouts found for this program. Run init_db.py first.")
            return

        tracking_workout = workouts[0]
        session = get_or_create_today_session(db, tracking_workout.id)

        # Compact header
        st.markdown(f"**Program:** {prog.name}")

        col_prev, col_mid, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("◀ Previous") and st.session_state["rotation_index"] > 0:
                st.session_state["rotation_index"] -= 1
                st.rerun()

        with col_mid:
            rot_num = st.session_state["rotation_index"] + 1
            st.info(f"Session {rot_num} • {session.date}")

        with col_next:
            if st.button("Next ▶"):
                st.session_state["rotation_index"] += 1
                st.rerun()

        session_index = st.session_state["rotation_index"]

        # Build session exercise list
        if callable(get_session_exercises):
            exercises_for_session = get_session_exercises(session_index)
        else:
            exercises_for_session = fallback_get_session_exercises(session_index)

        # Render exercises
        for idx, ex_name in enumerate(exercises_for_session):
            we = get_or_create_workout_exercise(db, tracking_workout, ex_name, idx)
            db.commit()

            st.subheader(ex_name)

            # Load final sets OR draft OR recommendation
            df = load_sets_or_draft_as_df(db, session.id, we.id)
            if df is None:
                if recommend_weights_and_reps is None:
                    # Safe fallback
                    rows = []
                    target_sets = int(getattr(we, "target_sets", DEFAULT_TARGET_SETS))
                    target_reps = int(getattr(we, "target_reps", DEFAULT_TARGET_REPS))
                    for i in range(1, target_sets + 1):
                        rows.append({"set_number": i, "weight": 50.0, "reps": target_reps, "done": False})
                    df = pd.DataFrame(rows)
                else:
                    rec_rows = recommend_weights_and_reps(db, we)
                    for r in rec_rows:
                        r["done"] = False
                    df = pd.DataFrame(rec_rows)

            editor_key = f"editor_{session.id}_{we.id}"

            edited_df = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    "set_number": st.column_config.NumberColumn("Set", min_value=1),
                    "weight": st.column_config.NumberColumn("Weight"),
                    "reps": st.column_config.NumberColumn("Reps", min_value=1),
                    "done": st.column_config.CheckboxColumn("Logged", default=False),
                },
                key=editor_key,
            )

            # Always save draft so refresh doesn’t wipe progress
            save_draft_from_df(db, session.id, we.id, edited_df)

            # Auto-promote to final sets when ALL checked
            did_promote = promote_draft_to_sets_if_complete(db, session.id, we.id)
            if did_promote:
                st.success("Saved ✅")
                st.rerun()

            # Divider ONLY when muscle group changes
            if idx < len(exercises_for_session) - 1:
                cur_m = muscle_for(ex_name)
                nxt_m = muscle_for(exercises_for_session[idx + 1])
                if cur_m != nxt_m:
                    st.markdown("---")

        # Finish workout
        if st.button("Finish Workout ✅"):
            st.session_state["rotation_index"] += 1
            # Clear editor states so next session starts clean
            for k in list(st.session_state.keys()):
                if k.startswith("editor_"):
                    del st.session_state[k]
            st.success("Workout finished — moved to next session.")
            st.rerun()


if __name__ == "__main__":
    main()
