import streamlit as st
from datetime import date
from typing import Optional, Dict, Any, List

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


# -----------------------------
# Helpers
# -----------------------------

def get_or_create_today_session(db, workout_id: int) -> Session:
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


def get_or_create_workout_exercise(db, workout: Workout, ex_name: str, order_index: int) -> WorkoutExercise:
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
        # defaults only for first-time creation; progression.py can override later
        we = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=exercise.id,
            order_index=order_index,
            target_sets=4,
            target_reps=10,
        )
        db.add(we)

    return we


def load_logged_sets(db, session_id: int, we_id: int) -> Dict[int, Set]:
    """Return {set_number: Set} for sets already logged."""
    rows = (
        db.query(Set)
        .filter(Set.session_id == session_id, Set.workout_exercise_id == we_id)
        .order_by(Set.set_number.asc())
        .all()
    )
    return {int(s.set_number): s for s in rows}


def upsert_set(db, session_id: int, we_id: int, set_number: int, weight: int, reps: int) -> None:
    existing = (
        db.query(Set)
        .filter(
            Set.session_id == session_id,
            Set.workout_exercise_id == we_id,
            Set.set_number == set_number,
        )
        .first()
    )
    if existing:
        existing.weight = float(weight)
        existing.reps = int(reps)
    else:
        new_set = Set(
            session_id=session_id,
            workout_exercise_id=we_id,
            set_number=int(set_number),
            weight=float(weight),
            reps=int(reps),
            rir=None,
        )
        db.add(new_set)

    db.commit()


def init_draft_from_recommendations(
    session_id: int,
    we_id: int,
    planned_sets: int,
    rec_rows: List[Dict[str, Any]],
    logged_map: Dict[int, Set],
) -> None:
    """
    Initialize session_state draft values ONLY if keys do not exist.
    This avoids Streamlit "default value + session_state" warnings and prevents resets.
    """
    # Build a fallback recommendation map by set_number
    rec_by_set = {int(r.get("set_number", i + 1)): r for i, r in enumerate(rec_rows)}

    for n in range(1, planned_sets + 1):
        w_key = f"w_{session_id}_{we_id}_{n}"
        r_key = f"r_{session_id}_{we_id}_{n}"

        if w_key in st.session_state and r_key in st.session_state:
            continue

        if n in logged_map:
            # logged beats everything
            if w_key not in st.session_state:
                st.session_state[w_key] = int(round(float(logged_map[n].weight)))
            if r_key not in st.session_state:
                st.session_state[r_key] = int(logged_map[n].reps)
            continue

        # otherwise recommendation
        rec = rec_by_set.get(n) or rec_rows[0] if rec_rows else {"weight": 50, "reps": 10}
        if w_key not in st.session_state:
            st.session_state[w_key] = int(round(float(rec.get("weight", 50))))
        if r_key not in st.session_state:
            st.session_state[r_key] = int(rec.get("reps", 10))


# -----------------------------
# UI
# -----------------------------

def main():
    st.set_page_config(page_title="Workout", layout="centered")

    # rotation index lives only in Streamlit session state
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

        # --- top header (compact) ---
        top_left, top_mid, top_right = st.columns([1.6, 3.2, 1.6])

        with top_left:
            if st.button("◀ Previous", use_container_width=True) and st.session_state["rotation_index"] > 0:
                st.session_state["rotation_index"] -= 1
                st.rerun()

        with top_mid:
            sess_num = st.session_state["rotation_index"] + 1
            st.markdown(
                f"<div style='text-align:center; font-weight:800; font-size:1.1rem;'>"
                f"Session {sess_num}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with top_right:
            if st.button("Next ▶", use_container_width=True):
                st.session_state["rotation_index"] += 1
                st.rerun()

        session_index = st.session_state["rotation_index"]

        # Create or retrieve today's session
        session = get_or_create_today_session(db, tracking_workout.id)

        # Program line (small)
        st.caption(f"Program: {prog.name}")

        # Single banner for session + date
        st.info(f"Session {session_index + 1} • {session.date}")

        # Determine which exercises this rotation session should have
        exercises_for_session = get_session_exercises(session_index)

        last_group: Optional[str] = None

        for order_idx, ex_name in enumerate(exercises_for_session):
            we = get_or_create_workout_exercise(db, tracking_workout, ex_name, order_idx)
            db.commit()
            db.refresh(we)
            db.refresh(we.exercise)

            group = (we.exercise.muscle_group or "").strip()

            # Divider ONLY when changing muscle groups (skip on very first)
            if last_group is not None and group and group != last_group:
                st.markdown("---")
            if group:
                last_group = group

            # Load logged sets
            logged_map = load_logged_sets(db, session.id, we.id)
            logged_count = len(logged_map)

            # Planned sets state for this session+exercise
            planned_sets_key = f"planned_{session.id}_{we.id}"
            if planned_sets_key not in st.session_state:
                # start from max(logged, we.target_sets)
                st.session_state[planned_sets_key] = max(we.target_sets, logged_count, 1)
            planned_sets = int(st.session_state[planned_sets_key])

            # Recommendations (used to seed draft for non-logged sets)
            rec_rows = recommend_weights_and_reps(db, we) or []

            # Ensure we have draft keys BEFORE widgets render (prevents resets)
            init_draft_from_recommendations(
                session_id=session.id,
                we_id=we.id,
                planned_sets=planned_sets,
                rec_rows=rec_rows,
                logged_map=logged_map,
            )

            # --- Exercise header row: name | − | count | ＋ | muscle ---
            title_col, minus_col, count_col, plus_col, group_col = st.columns([7, 1.4, 0.8, 1.4, 2.4])

            with title_col:
                st.subheader(ex_name)

            with minus_col:
                # cannot go below logged_count or 1
                if st.button("−", key=f"minus_{session.id}_{we.id}", use_container_width=True):
                    new_val = max(max(1, logged_count), planned_sets - 1)
                    st.session_state[planned_sets_key] = new_val
                    st.rerun()

            with count_col:
                st.markdown(
                    f"<div style='text-align:center; padding-top:0.55rem; font-weight:800;'>"
                    f"{planned_sets}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with plus_col:
                # Fullwidth plus to avoid font rendering issues
                if st.button("＋", key=f"plus_{session.id}_{we.id}", use_container_width=True):
                    st.session_state[planned_sets_key] = min(30, planned_sets + 1)
                    st.rerun()

            with group_col:
                st.markdown(
                    f"<div style='text-align:right; opacity:0.7; padding-top:0.55rem;'>"
                    f"{group}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Help text (small)
            st.caption("Edit Weight/Reps, then press Log for each completed set. Use Update to correct a logged set.")

            # --- Per-set rows ---
            for n in range(1, planned_sets + 1):
                w_key = f"w_{session.id}_{we.id}_{n}"
                r_key = f"r_{session.id}_{we.id}_{n}"

                is_logged = n in logged_map

                # Layout: Set label | Weight | Reps | Status | Button
                c0, c1, c2, c3, c4 = st.columns([1.2, 2.2, 2.0, 3.0, 1.6])

                with c0:
                    st.markdown(f"**Set {n}**")

                with c1:
                    # weight as int (no decimals)
                    st.number_input(
                        "Weight",
                        min_value=0,
                        step=5,
                        value=int(st.session_state[w_key]),
                        key=w_key,
                        label_visibility="collapsed",
                    )

                with c2:
                    st.number_input(
                        "Reps",
                        min_value=0,
                        step=1,
                        value=int(st.session_state[r_key]),
                        key=r_key,
                        label_visibility="collapsed",
                    )

                with c3:
                    if is_logged:
                        st.success("Logged ✅")
                    else:
                        st.info("Not logged")

                with c4:
                    if is_logged:
                        if st.button("Update", key=f"update_{session.id}_{we.id}_{n}", use_container_width=True):
                            upsert_set(
                                db,
                                session_id=session.id,
                                we_id=we.id,
                                set_number=n,
                                weight=int(st.session_state[w_key]),
                                reps=int(st.session_state[r_key]),
                            )
                            st.rerun()
                    else:
                        if st.button("Log", key=f"log_{session.id}_{we.id}_{n}", use_container_width=True):
                            upsert_set(
                                db,
                                session_id=session.id,
                                we_id=we.id,
                                set_number=n,
                                weight=int(st.session_state[w_key]),
                                reps=int(st.session_state[r_key]),
                            )
                            st.rerun()

        # --- Finish workout ---
        st.markdown("---")
        if st.button("Finish Workout ✅", use_container_width=True):
            st.session_state["rotation_index"] += 1
            st.success("Workout complete. Moving to next session.")
            st.rerun()


if __name__ == "__main__":
    main()
