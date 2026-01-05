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
    Exercise,        # <-- make sure Exercise is exported from db.py
)

# ----------------- EXERCISE ROTATION CONFIG -----------------

LEG_ROTATION = [
    "Leg Extension",                # leg session 1
    "Leg Curl",                     # leg session 2
    "Hip Thrust + Glute Lunges",    # leg session 3
]

PUSH_BLOCK = [
    "Incline DB Bench Press",
    "Single-arm Chest Fly",
    "Cable Tricep Pushdown",
]

PULL_MAIN_ROTATION = [
    "Lat Pulldown",
    "Cable Row",
]

PULL_SECONDARY = "Cable Curl"

LATERAL_RAISES = "Dumbbell Lateral Raise"

DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10


def get_session_exercises(session_index: int):
    """
    session_index: 0-based training session number.
    Returns an ordered list of exercise names for that session.

    Pattern:
      - Legs rotate over LEG_ROTATION
      - Push / Pull alternates each session
      - Pull days alternate Lat Pulldown / Cable Row
      - Finish every session with lateral raises
    """
    # Legs: simple 3-day rotation
    leg_ex = LEG_ROTATION[session_index % len(LEG_ROTATION)]

    # Upper: alternate Push / Pull
    is_push_day = (session_index % 2 == 0)

    if is_push_day:
        # Push day: always the same three
        upper_block = PUSH_BLOCK
    else:
        # Pull day: alternate Lat Pulldown / Cable Row for the main movement
        pull_session_number = session_index // 2  # counts only pull days
        pull_main = PULL_MAIN_ROTATION[pull_session_number % len(PULL_MAIN_ROTATION)]
        upper_block = [pull_main, PULL_SECONDARY]

    # Always finish with laterals
    exercises = [leg_ex] + upper_block + [LATERAL_RAISES]
    return exercises


# ---------- progression logic (very simple first pass) ----------

def get_last_session_sets(db, workout_exercise_id, max_sessions_back=3):
    q = (
        db.query(Set)
        .join(Session, Set.session_id == Session.id)
        .filter(Set.workout_exercise_id == workout_exercise_id)
        .order_by(Session.date.desc(), Set.set_number.asc())
    )
    sets = q.all()
    if not sets:
        return None, None

    # group by session_id
    sessions = {}
    for s in sets:
        sessions.setdefault(s.session_id, []).append(s)

    # take most recent session
    last_sid = list(sessions.keys())[0]
    return last_sid, sessions[last_sid]


def recommend_weights_and_reps(db, we: WorkoutExercise):
    """
    Return a list of dicts: [{set_number, weight, reps, done}, ...]
    Very dumb rule:
      - If we have a previous session and *all* sets hit >= target_reps,
        add +5 units of weight.
      - Else keep previous weight.
      - If no history, use 50 as base weight.
    """
    base_weight = 50.0

    last_session_id, last_sets = get_last_session_sets(db, we.id)
    result = []
    if not last_sets:
        for i in range(1, int(we.target_sets) + 1):  # type: ignore
            result.append(
                {
                    "set_number": i,
                    "weight": base_weight,
                    "reps": we.target_reps,
                    "done": True,  # default: plan to do all sets
                }
            )
        return result

    all_hit_target = all(s.reps >= we.target_reps for s in last_sets)
    last_weight = last_sets[0].weight  # assume same weight per set
    next_weight = last_weight + 5 if all_hit_target else last_weight

    for i in range(1, int(we.target_sets) + 1):  # type: ignore
        result.append(
            {
                "set_number": i,
                "weight": next_weight,
                "reps": we.target_reps,
                "done": True,
            }
        )
    return result


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


def get_or_create_workout_exercise(db, prog, workout, ex_name, order_index):
    """
    Given a program, a tracking workout and an exercise name string,
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
        # (No commit here; we'll commit later)

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
        we = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=exercise.id,
            order_index=order_index,
            target_sets=DEFAULT_TARGET_SETS,
            target_reps=DEFAULT_TARGET_REPS,
        )
        db.add(we)
        # again, actual commit happens outside

    return we


# ---------- main app ----------

def main():
    st.set_page_config(page_title="Workout Progression", layout="centered")

    st.title("Workout Progression")

    with get_session() as db:
        programs = db.query(Program).all()
        if not programs:
            st.error("No programs found. Run init_db.py first.")
            return

        prog_names = [p.name for p in programs]
        prog_choice = st.selectbox("Program", prog_names)
        prog = programs[prog_names.index(prog_choice)]

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

        # Create or retrieve today's session
        session = get_or_create_today_session(db, tracking_workout.id)

        # Work out which number session this is (0-based) for this workout
        ordered_sessions = (
            db.query(Session)
            .filter(Session.workout_id == tracking_workout.id)
            .order_by(Session.date.asc())
            .all()
        )
        session_index = 0
        for i, s in enumerate(ordered_sessions):
            if s.id == session.id: # type: ignore
                session_index = i
                break

        st.info(f"Session date (stored in DB): {session.date}")
        st.caption(f"Rotation session number: **{session_index + 1}**")

        # Determine which exercises this rotation session should have
        exercises_for_session = get_session_exercises(session_index)

        st.caption("Exercise order for this session:")
        st.markdown("- " + "\n- ".join(exercises_for_session))

                # -------- main UI per exercise in the rotation --------
        for order_idx, ex_name in enumerate(exercises_for_session):
            # Get or create WorkoutExercise for this exercise name
            we = get_or_create_workout_exercise(
                db, prog, tracking_workout, ex_name, order_idx
            )
            # commit potential new rows before we query sets
            db.commit()

            st.subheader(ex_name)

            # ---- recommended baseline table ----
            rec_rows = recommend_weights_and_reps(db, we)
            df = pd.DataFrame(rec_rows)

            # Ensure nice column order and presence of 'done'
            if "done" not in df.columns:
                df["done"] = True
            df = df[["set_number", "weight", "reps", "done"]]

            # ---- previous logged sets for this session (if any) ----
            existing_sets = (
                db.query(Set)
                .filter(
                    Set.session_id == session.id,
                    Set.workout_exercise_id == we.id,
                )
                .order_by(Set.set_number.asc())
                .all()
            )
            if existing_sets:
                st.caption("Already logged for this session:")
                prev_df = pd.DataFrame(
                    [
                        {
                            "set_number": s.set_number,
                            "weight": s.weight,
                            "reps": s.reps,
                            "RIR": s.rir,
                        }
                        for s in existing_sets
                    ]
                )
                st.dataframe(prev_df, use_container_width=True)

            st.caption("Edit the plan for this session before logging:")

            edited_df = st.data_editor(
                df,
                num_rows="dynamic",        # allow add/remove sets
                hide_index=True,           # hide 0,1,2,... index column
                use_container_width=True,
                key=f"editor_{we.id}",
                column_config={
                    "set_number": st.column_config.NumberColumn(
                        "Set",
                        min_value=1,
                        step=1,
                    ),
                    "weight": st.column_config.NumberColumn(
                        "Weight",
                        min_value=0.0,
                        step=2.5,
                    ),
                    "reps": st.column_config.NumberColumn(
                        "Reps",
                        min_value=1,
                        step=1,
                    ),
                    "done": st.column_config.CheckboxColumn(
                        "Logged", help="Tick for sets you actually performed"
                    ),
                },
            )

            if st.button("Log sets", key=f"log_{we.id}"):
                # delete any existing sets for this session/exercise
                db.query(Set).filter(
                    Set.session_id == session.id,
                    Set.workout_exercise_id == we.id,
                ).delete()

                # Only log rows that are marked as done
                if "done" in edited_df.columns:
                    rows_to_log = edited_df[edited_df["done"] == True]
                else:
                    # fallback: log all rows
                    rows_to_log = edited_df

                for _, row in rows_to_log.iterrows():
                    # skip incomplete rows (e.g. newly added but empty)
                    if pd.isna(row.get("set_number")) or pd.isna(row.get("weight")) or pd.isna(row.get("reps")):
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

                if len(rows_to_log) == 0:
                    st.warning("No sets were marked as logged; cleared any previous sets.")
                else:
                    st.success(f"Logged {len(rows_to_log)} set(s) for this exercise.")

            st.markdown("---")


if __name__ == "__main__":
    main()
