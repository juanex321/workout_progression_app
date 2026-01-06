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
    init_db,   # 👈 add this
)


from progression import recommend_weights_and_reps

# ----------------- ROTATION CONFIG -----------------

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

# default sets if nothing special is defined
DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10

# per-exercise overrides for starting # of sets
EXERCISE_DEFAULT_SETS = {
    # chest finisher
    "Single-arm Chest Fly": 1,
    # quad finisher
    "Sissy Squat": 1,
    # lat finisher
    "Straight-arm Pulldown": 1,
    # biceps finisher
    "Incline DB Curl": 1,
    # triceps finisher
    "Overhead Cable Extension": 1,
}

# ----------------- FEEDBACK SCALES -----------------

SORENESS_OPTIONS = [
    "Never got sore",
    "Healed a while ago",
    "Healed just on time",
    "I'm still sore",
]
SORENESS_SCALE = {
    "Never got sore": 1,
    "Healed a while ago": 2,
    "Healed just on time": 3,
    "I'm still sore": 4,
}

PUMP_OPTIONS = ["Low pump", "Moderate pump", "Amazing pump"]
PUMP_SCALE = {
    "Low pump": 1,
    "Moderate pump": 2,
    "Amazing pump": 3,
}

WORKLOAD_OPTIONS = [
    "Easy",
    "Pretty good",
    "Pushed my limits",
    "Too much",
]
WORKLOAD_SCALE = {
    "Easy": 1,
    "Pretty good": 2,
    "Pushed my limits": 3,
    "Too much": 4,
}


def get_session_exercises(session_index: int):
    """
    session_index: 0-based training session number.
    Returns an ordered list of exercise names for that session.

    Pattern:
      - Legs rotate over LEG_ROTATION.
      - Push / Pull alternates each session.
      - Pull days alternate Lat Pulldown / Cable Row.
      - Finish every session with lateral raises.
      - Certain muscles get 1-set "finisher" exercises.
    """
    # ----- leg block -----
    leg_ex = LEG_ROTATION[session_index % len(LEG_ROTATION)]
    leg_block = [leg_ex]

    # add quad finisher only on Leg Extension day
    if leg_ex == "Leg Extension":
        leg_block.append("Sissy Squat")

    # ----- upper block -----
    is_push_day = (session_index % 2 == 0)

    if is_push_day:
        # Push day:
        #   main chest, chest finisher, main triceps, triceps finisher
        upper_block = [
            "Incline DB Bench Press",
            "Single-arm Chest Fly",      # finisher, 1 set
            "Cable Tricep Pushdown",
            "Overhead Cable Extension",  # finisher, 1 set
        ]
    else:
        # Pull day:
        #   main back (alternating), lat finisher, main biceps, biceps finisher
        pull_session_number = session_index // 2  # counts only pull days
        pull_main = PULL_MAIN_ROTATION[pull_session_number % len(PULL_MAIN_ROTATION)]
        upper_block = [
            pull_main,
            "Straight-arm Pulldown",  # lat finisher
            PULL_SECONDARY,           # Cable Curl
            "Incline DB Curl",        # biceps finisher
        ]

    # Always finish with laterals
    exercises = leg_block + upper_block + [LATERAL_RAISES]
    return exercises


# ---------- helpers ----------

def get_or_create_today_session(db, workout_id):
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


def get_or_create_workout_exercise(db, workout, ex_name, order_index):
    """
    Given a tracking workout and an exercise name string,
    return a WorkoutExercise row. If needed, create Exercise and/or
    WorkoutExercise on the fly.
    """
    name_normalized = ex_name.strip()

    # 1) Try to find an Exercise by name (case-insensitive)
    exercise = (
        db.query(Exercise)
        .filter(Exercise.name.ilike(name_normalized))
        .first()
    )
    if not exercise:
        exercise = Exercise(name=name_normalized)
        db.add(exercise)
        db.flush()  # populate exercise.id

    # 2) Try to find a WorkoutExercise linking this exercise to the workout
    we = (
        db.query(WorkoutExercise)
        .filter(
            WorkoutExercise.workout_id == workout.id,
            WorkoutExercise.exercise_id == exercise.id,
        )
        .first()
    )
    if not we:
        target_sets = EXERCISE_DEFAULT_SETS.get(
            name_normalized,
            DEFAULT_TARGET_SETS,
        )
        we = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=exercise.id,
            order_index=order_index,
            target_sets=target_sets,
            target_reps=DEFAULT_TARGET_REPS,
        )
        db.add(we)

    return we


# ---------- main app ----------

def main():
    st.set_page_config(page_title="Workout Progression", layout="centered")
    init_db()
    st.title("Workout Progression")

    # rotation index lives only in Streamlit session state
    if "rotation_index" not in st.session_state:
        st.session_state["rotation_index"] = 0

    with get_session() as db:
        programs = db.query(Program).all()
        if not programs:
            st.error("No programs found. Run init_db.py first.")
            return

        # For now, just use the first program and show its name (no dropdown)
        prog = programs[0]

        st.markdown(f"**Program:** {prog.name}")

        # Use the FIRST workout as the container for sessions
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

        # Navigation for rotation session number
        col_prev, col_label, col_next = st.columns([1, 2, 1])

        with col_prev:
            if st.button("◀ Previous") and st.session_state["rotation_index"] > 0:
                st.session_state["rotation_index"] -= 1

        with col_label:
            st.markdown(
                f"<div style='text-align:center; font-weight:bold;'>"
                f"Rotation session: {st.session_state['rotation_index'] + 1}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button("Next ▶"):
                st.session_state["rotation_index"] += 1

        session_index = st.session_state["rotation_index"]

        # Create or retrieve today's session (used for storing sets)
        session = get_or_create_today_session(db, tracking_workout.id)

        # Session date banner
        st.info(f"Session date: {session.date}")

        # Determine which exercises this rotation session should have
        exercises_for_session = get_session_exercises(session_index)

        # -------- main UI per exercise in the rotation --------
        for order_idx, ex_name in enumerate(exercises_for_session):
            # Get or create WorkoutExercise for this exercise name
            we = get_or_create_workout_exercise(
                db, tracking_workout, ex_name, order_idx
            )
            # commit potential new rows before we query sets
            db.commit()

            st.subheader(ex_name)

            # recommended baseline table (now uses feedback + deload logic)
            rec_rows = recommend_weights_and_reps(db, we)
            df = pd.DataFrame(rec_rows)

            # check if we already logged sets for this session+exercise
            existing_sets = (
                db.query(Set)
                .filter(
                    Set.session_id == session.id,
                    Set.workout_exercise_id == we.id,
                )
                .order_by(Set.set_number.asc())
                .all()
            )
            already_logged = len(existing_sets) > 0

            # Show the editor (no index, dynamic rows, checkboxes start False)
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
                key=f"editor_{we.id}",
            )

            # AUTO-LOG when all sets are checked AND nothing is logged yet
            just_logged = False
            if not already_logged and not edited_df.empty:
                if "done" in edited_df.columns and edited_df["done"].all():
                    db.query(Set).filter(
                        Set.session_id == session.id,
                        Set.workout_exercise_id == we.id,
                    ).delete()

                    for _, row in edited_df.iterrows():
                        if not row["done"]:
                            continue
                        new_set = Set(
                            session_id=session.id,
                            workout_exercise_id=we.id,
                            set_number=int(row["set_number"]),
                            weight=float(row["weight"]),
                            reps=int(row["reps"]),
                            rir=None,
                        )
                        db.add(new_set)
                    db.commit()
                    just_logged = True
                    already_logged = True
                    st.success("Sets logged for this exercise ✅")

            # Simple feedback panel once this exercise has just been logged
            feedback_key_prefix = f"feedback_{session.id}_{we.id}"
            if just_logged:
                st.session_state[feedback_key_prefix + "_show"] = True

            if st.session_state.get(feedback_key_prefix + "_show", False):
                with st.expander("Feedback for this muscle group"):
                    st.write("How did this exercise feel?")

                    # Check whether feedback is already saved for this session+exercise
                    existing_fb = (
                        db.query(Feedback)
                        .filter(
                            Feedback.session_id == session.id,
                            Feedback.workout_exercise_id == we.id,
                        )
                        .order_by(Feedback.created_at.desc())
                        .first()
                    )
                    if existing_fb:
                        st.caption("Feedback already saved for this session.")

                    s_choice = st.radio(
                        "Soreness AFTER last time:",
                        SORENESS_OPTIONS,
                        key=feedback_key_prefix + "_soreness",
                    )

                    p_choice = st.radio(
                        "Pump TODAY:",
                        PUMP_OPTIONS,
                        key=feedback_key_prefix + "_pump",
                    )

                    w_choice = st.radio(
                        "Workload TODAY:",
                        WORKLOAD_OPTIONS,
                        key=feedback_key_prefix + "_workload",
                    )

                    # Save feedback once (if not already saved)
                    if (not existing_fb) and s_choice and p_choice and w_choice:
                        fb = Feedback(
                            session_id=session.id,
                            workout_exercise_id=we.id,
                            soreness=SORENESS_SCALE[s_choice],
                            pump=PUMP_SCALE[p_choice],
                            workload=WORKLOAD_SCALE[w_choice],
                        )
                        db.add(fb)
                        db.commit()
                        st.success("Feedback saved ✅")

            st.markdown("---")


if __name__ == "__main__":
    main()

