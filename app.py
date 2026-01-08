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
)

# Prefer your refactored modules if present
try:
    from plan import get_session_exercises  # type: ignore
except Exception:
    get_session_exercises = None  # type: ignore

try:
    from progression import recommend_weights_and_reps  # type: ignore
except Exception:
    recommend_weights_and_reps = None  # type: ignore


# -----------------------------
# Fallback plan (only used if plan.py import missing)
# -----------------------------
LEG_ROTATION = [
    "Leg Extension",                # leg session 1
    "Leg Curl",                     # leg session 2
    "Hip Thrust + Glute Lunges",    # leg session 3
]

PULL_MAIN_ROTATION = [
    "Lat Pulldown",
    "Cable Row",
]

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
# DB helpers (kept inside app.py for portability)
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


def load_existing_sets_as_df(db, session_id: int, workout_exercise_id: int) -> pd.DataFrame | None:
    existing_sets = (
        db.query(Set)
        .filter(
            Set.session_id == session_id,
            Set.workout_exercise_id == workout_exercise_id,
        )
        .order_by(Set.set_number.asc())
        .all()
    )
    if not existing_sets:
        return None

    rows = []
    for s in existing_sets:
        rows.append(
            {
                "set_number": int(s.set_number),
                "weight": float(s.weight),
                "reps": int(s.reps),
                "done": True,  # already logged
            }
        )
    return pd.DataFrame(rows)


def save_sets_from_df(db, session_id: int, workout_exercise_id: int, df: pd.DataFrame):
    # Only save rows that are checked as done
    if df.empty or "done" not in df.columns:
        return

    done_df = df[df["done"] == True].copy()  # noqa: E712
    if done_df.empty:
        return

    # Replace existing rows for this session/exercise
    db.query(Set).filter(
        Set.session_id == session_id,
        Set.workout_exercise_id == workout_exercise_id,
    ).delete()

    # Re-number sets based on their current order in the table
    done_df = done_df.reset_index(drop=True)
    for i, row in done_df.iterrows():
        new_set = Set(
            session_id=session_id,
            workout_exercise_id=workout_exercise_id,
            set_number=int(i + 1),
            weight=float(row["weight"]),
            reps=int(row["reps"]),
            rir=None,
        )
        db.add(new_set)

    db.commit()


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

        # Top compact header
        st.markdown(f"**Program:** {prog.name}")

        col_prev, col_mid, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("◀ Previous") and st.session_state["rotation_index"] > 0:
                st.session_state["rotation_index"] -= 1
                st.rerun()

        with col_mid:
            # compact combined banner: session + date
            rot_num = st.session_state["rotation_index"] + 1
            st.info(f"Session {rot_num} • {session.date}")

        with col_next:
            if st.button("Next ▶"):
                st.session_state["rotation_index"] += 1
                st.rerun()

        session_index = st.session_state["rotation_index"]

        # Get exercises for this rotation
        if callable(get_session_exercises):
            exercises_for_session = get_session_exercises(session_index)
        else:
            exercises_for_session = fallback_get_session_exercises(session_index)

        # Render each exercise
        for order_idx, ex_name in enumerate(exercises_for_session):
            we = get_or_create_workout_exercise(db, tracking_workout, ex_name, order_idx)
            db.commit()

            st.subheader(ex_name)

            # If we already have logged sets in DB, show those; else show recommendation
            existing_df = load_existing_sets_as_df(db, session.id, we.id)
            if existing_df is not None:
                df = existing_df
            else:
                if recommend_weights_and_reps is None:
                    # safe fallback if progression import missing
                    rows = []
                    for i in range(1, int(getattr(we, "target_sets", DEFAULT_TARGET_SETS)) + 1):
                        rows.append(
                            {
                                "set_number": i,
                                "weight": 50.0,
                                "reps": int(getattr(we, "target_reps", DEFAULT_TARGET_REPS)),
                                "done": False,
                            }
                        )
                    df = pd.DataFrame(rows)
                else:
                    rec_rows = recommend_weights_and_reps(db, we)
                    # Ensure checkboxes start OFF until user logs
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

            # One clear action: Save sets (removes Reset Draft)
            if st.button("Save sets", key=f"save_{session.id}_{we.id}"):
                save_sets_from_df(db, session.id, we.id, edited_df)
                st.success("Saved ✅")
                st.rerun()

            st.markdown("---")

        # Finish Workout button at the end
        if st.button("Finish Workout ✅"):
            st.session_state["rotation_index"] += 1

            # Optional: clear any editor state so next session starts clean
            for k in list(st.session_state.keys()):
                if k.startswith("editor_"):
                    del st.session_state[k]

            st.success("Workout finished — moved to next session.")
            st.rerun()


if __name__ == "__main__":
    main()
