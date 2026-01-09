import streamlit as st
from datetime import date

from db import (
    get_session,
    Program,
    Workout,
    WorkoutExercise,
    Session,
    Set,
    Exercise,
)

from progression import recommend_weights_and_reps
from plan import get_session_exercises


# ----------------- UI / CONFIG -----------------

DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10

# Optional: per-exercise starting sets (finishers etc.)
EXERCISE_DEFAULT_SETS = {
    "Single-arm Chest Fly": 1,
    "Sissy Squat": 1,
    "Straight-arm Pulldown": 1,
    "Incline DB Curl": 1,
    "Overhead Cable Extension": 1,
}

# Used ONLY for drawing dividers when muscle group changes.
# Expand this over time as you add exercises.
MUSCLE_GROUP_BY_EXERCISE = {
    # legs / quads
    "Leg Extension": "Quads",
    "Sissy Squat": "Quads",
    # hamstrings / glutes
    "Leg Curl": "Hamstrings",
    "Hip Thrust + Glute Lunges": "Glutes",
    # chest
    "Incline DB Bench Press": "Chest",
    "Single-arm Chest Fly": "Chest",
    # back / lats
    "Lat Pulldown": "Back",
    "Cable Row": "Back",
    "Straight-arm Pulldown": "Back",
    # biceps
    "Cable Curl": "Biceps",
    "Incline DB Curl": "Biceps",
    # triceps
    "Cable Tricep Pushdown": "Triceps",
    "Overhead Cable Extension": "Triceps",
    # delts
    "Dumbbell Lateral Raise": "Delts",
}


# ----------------- DB HELPERS -----------------

def get_or_create_exercise(db, ex_name: str) -> Exercise:
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
    return exercise


def get_or_create_workout_exercise(db, workout: Workout, ex_name: str, order_index: int) -> WorkoutExercise:
    exercise = get_or_create_exercise(db, ex_name)

    we = (
        db.query(WorkoutExercise)
        .filter(
            WorkoutExercise.workout_id == workout.id,
            WorkoutExercise.exercise_id == exercise.id,
        )
        .first()
    )

    if not we:
        target_sets = EXERCISE_DEFAULT_SETS.get(ex_name.strip(), DEFAULT_TARGET_SETS)
        we = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=exercise.id,
            order_index=order_index,
            target_sets=target_sets,
            target_reps=DEFAULT_TARGET_REPS,
        )
        db.add(we)
        db.flush()

    return we


def get_or_create_active_session(db, workout_id: int) -> Session:
    """
    IMPORTANT CHANGE vs your earlier code:
    - We keep an "active_session_id" in st.session_state.
    - That lets you press "Finish Workout" and create a NEW session row
      even on the same date (no data mixing, no overwrites).
    """
    active_id = st.session_state.get("active_session_id")
    if active_id is not None:
        sess = db.query(Session).filter(Session.id == active_id).first()
        if sess:
            return sess

    sess = Session(workout_id=workout_id, date=date.today())
    db.add(sess)
    db.commit()
    db.refresh(sess)
    st.session_state["active_session_id"] = sess.id
    return sess


def load_logged_sets(db, session_id: int, workout_exercise_id: int) -> dict:
    """
    Returns dict: {set_number: Set}
    """
    rows = (
        db.query(Set)
        .filter(
            Set.session_id == session_id,
            Set.workout_exercise_id == workout_exercise_id,
        )
        .order_by(Set.set_number.asc())
        .all()
    )
    return {r.set_number: r for r in rows}


# ----------------- UI HELPERS -----------------

def muscle_group_for_exercise(ex_name: str) -> str:
    return MUSCLE_GROUP_BY_EXERCISE.get(ex_name, "Other")


def clamp_int(x, lo, hi):
    try:
        v = int(x)
    except Exception:
        v = lo
    return max(lo, min(hi, v))


# ----------------- APP -----------------

def main():
    st.set_page_config(page_title="Workout Progression", layout="wide")

    # rotation index (session # in the rotation)
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
        session = get_or_create_active_session(db, tracking_workout.id)

        # -------- top bar (compact) --------
        top_l, top_c, top_r = st.columns([1.2, 3, 1.2])

        with top_l:
            if st.button("◀ Previous", use_container_width=True) and st.session_state["rotation_index"] > 0:
                st.session_state["rotation_index"] -= 1
                st.rerun()

        with top_c:
            st.markdown(f"**Program:** {prog.name}")
            st.info(f"Session {st.session_state['rotation_index'] + 1} · {session.date}")

        with top_r:
            if st.button("Next ▶", use_container_width=True):
                st.session_state["rotation_index"] += 1
                st.rerun()

        st.write("")

        session_index = st.session_state["rotation_index"]
        exercises_for_session = get_session_exercises(session_index)

        prev_group = None

        for order_idx, ex_name in enumerate(exercises_for_session):
            # Create WE rows as needed
            we = get_or_create_workout_exercise(db, tracking_workout, ex_name, order_idx)
            db.commit()

            # Divider only when muscle group changes
            group = muscle_group_for_exercise(ex_name)
            if prev_group is not None and group != prev_group:
                st.markdown("---")
            prev_group = group

            # Get recommendation baseline (used for defaults)
            rec_rows = recommend_weights_and_reps(db, we) or []
            # fallback if progression returns nothing
            if rec_rows:
                # assume first row has weight/reps
                base_weight = int(float(rec_rows[0].get("weight", 0) or 0))
                base_reps = int(rec_rows[0].get("reps", we.target_reps) or we.target_reps)
                base_sets = int(len(rec_rows))
            else:
                base_weight = 0
                base_reps = int(we.target_reps)
                base_sets = int(we.target_sets)

            # load logged sets from DB
            logged = load_logged_sets(db, session.id, we.id)
            logged_max = max(logged.keys()) if logged else 0

            # planned sets state key
            draft_sets_key = f"draft_sets_{session.id}_{we.id}"
            if draft_sets_key not in st.session_state:
                # start with either recommendation length, or target_sets
                st.session_state[draft_sets_key] = max(base_sets, we.target_sets, logged_max, 1)

            planned_sets = clamp_int(st.session_state[draft_sets_key], lo=max(1, logged_max), hi=30)
            st.session_state[draft_sets_key] = planned_sets

            # -------- Compact header row: Exercise name + sets controls --------
            title_col, minus_col, count_col, plus_col, group_col = st.columns([6, 1, 1.2, 1, 2])

            with title_col:
                st.subheader(ex_name)

            with group_col:
                st.markdown(
                    f"<div style='text-align:right; opacity:0.75; padding-top:0.6rem;'>"
                    f"{group}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with minus_col:
                if st.button("−", key=f"minus_{session.id}_{we.id}", use_container_width=True):
                    # don’t allow shrinking below already-logged max
                    new_val = max(max(1, logged_max), planned_sets - 1)
                    st.session_state[draft_sets_key] = new_val
                    st.rerun()

            with count_col:
                st.markdown(
                    f"<div style='text-align:center; padding-top:0.6rem; font-weight:700;'>"
                    f"{planned_sets}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with plus_col:
                if st.button("+", key=f"plus_{session.id}_{we.id}", use_container_width=True):
                    st.session_state[draft_sets_key] = min(30, planned_sets + 1)
                    st.rerun()

            st.caption("Edit Weight/Reps, then press Log for each completed set. Use Update to correct a logged set.")

            # -------- Set rows (per-set logging) --------
            for set_num in range(1, planned_sets + 1):
                # input keys
                w_key = f"w_{session.id}_{we.id}_{set_num}"
                r_key = f"r_{session.id}_{we.id}_{set_num}"

                # initialize inputs once
                if w_key not in st.session_state:
                    if set_num in logged:
                        st.session_state[w_key] = int(float(logged[set_num].weight))
                    else:
                        st.session_state[w_key] = int(base_weight)

                if r_key not in st.session_state:
                    if set_num in logged:
                        st.session_state[r_key] = int(logged[set_num].reps)
                    else:
                        st.session_state[r_key] = int(base_reps)

                row_cols = st.columns([1.2, 2.2, 2.2, 2.4, 1.2])

                with row_cols[0]:
                    st.markdown(f"**Set {set_num}**")

                with row_cols[1]:
                    st.number_input(
                        "Weight",
                        min_value=0,
                        max_value=2000,
                        step=5,
                        key=w_key,
                        label_visibility="collapsed",
                    )

                with row_cols[2]:
                    st.number_input(
                        "Reps",
                        min_value=0,
                        max_value=100,
                        step=1,
                        key=r_key,
                        label_visibility="collapsed",
                    )

                # status pill
                is_logged = set_num in logged
                with row_cols[3]:
                    if is_logged:
                        st.success("Logged ✅")
                    else:
                        st.info("Not logged")

                # action button (Log or Update)
                with row_cols[4]:
                    if is_logged:
                        if st.button("Update", key=f"update_{session.id}_{we.id}_{set_num}", use_container_width=True):
                            s = logged[set_num]
                            s.weight = float(int(st.session_state[w_key]))
                            s.reps = int(st.session_state[r_key])
                            db.add(s)
                            db.commit()
                            st.rerun()
                    else:
                        if st.button("Log", key=f"log_{session.id}_{we.id}_{set_num}", use_container_width=True):
                            new_set = Set(
                                session_id=session.id,
                                workout_exercise_id=we.id,
                                set_number=set_num,
                                weight=float(int(st.session_state[w_key])),
                                reps=int(st.session_state[r_key]),
                                rir=None,
                            )
                            db.add(new_set)
                            db.commit()
                            st.rerun()

            st.write("")

        st.markdown("---")

        # -------- Finish Workout --------
        finish_col_l, finish_col_r = st.columns([4, 1.5])
        with finish_col_r:
            if st.button("Finish Workout ✅", use_container_width=True):
                # create a new session row and advance rotation
                st.session_state["active_session_id"] = None
                st.session_state["rotation_index"] += 1
                st.rerun()


if __name__ == "__main__":
    main()
