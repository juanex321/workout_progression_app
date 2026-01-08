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
    Feedback,
)

from plan import get_session_exercises
from progression import recommend_weights_and_reps
from services import (
    get_or_create_today_session,
    get_or_create_workout_exercise,
    load_existing_sets,
)

# ----------------- page config -----------------

def main():
    st.set_page_config(page_title="Workout", layout="centered")

    # rotation index lives only in Streamlit session state
    if "rotation_index" not in st.session_state:
        st.session_state["rotation_index"] = 0

    with get_session() as db:
        programs = db.query(Program).order_by(Program.id.asc()).all()
        if not programs:
            st.error("No programs found. Run init_db.py first.")
            return

        prog = programs[0]
        st.markdown(f"**Program:** {prog.name}")

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
        col_prev, col_center, col_next = st.columns([1, 2, 1])

        with col_prev:
            if st.button("◀ Previous") and st.session_state["rotation_index"] > 0:
                st.session_state["rotation_index"] -= 1

        with col_center:
            # "Session 1 · YYYY-MM-DD"
            sess_label = st.session_state["rotation_index"] + 1
            # we create the session below, but show a stable label now
            st.markdown(
                f"<div style='text-align:center; font-weight:bold;'>"
                f"Session {sess_label}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button("Next ▶"):
                st.session_state["rotation_index"] += 1

        session_index = st.session_state["rotation_index"]

        # Create/retrieve today's session (DB-persisted)
        session = get_or_create_today_session(db, tracking_workout.id)

        # compact banner
        st.info(f"Session {session_index + 1} · {session.date}")

        # Determine exercises for this rotation session
        exercises_for_session = get_session_exercises(session_index)

        # -------- per exercise UI --------
        for order_idx, ex_name in enumerate(exercises_for_session):
            we = get_or_create_workout_exercise(db, tracking_workout, ex_name, order_idx)
            db.commit()

            st.subheader(ex_name)

            # recommendations
            rec_rows = recommend_weights_and_reps(db, we) or []

            # existing logged sets (DB)
            existing_sets = load_existing_sets(db, session.id, we.id)
            existing_by_num = {s.set_number: s for s in existing_sets}

            # Draft planned sets, persisted in session_state so refresh/rerun doesn't revert
            draft_sets_key = f"draft_sets_{session.id}_{we.id}"
            if draft_sets_key not in st.session_state:
                # default to recommended length; fallback to we.target_sets; min 1
                default_n = len(rec_rows) if len(rec_rows) > 0 else int(getattr(we, "target_sets", 4))
                st.session_state[draft_sets_key] = max(1, int(default_n))

            planned_sets = st.number_input(
                "Planned sets",
                min_value=1,
                max_value=20,
                step=1,
                key=draft_sets_key,
                help="This controls how many sets you plan to do for this exercise today.",
            )


            st.caption("Edit Weight/Reps, then press **Log** for each completed set. Use **Update** to correct a logged set.")

            # Render rows
            for i in range(1, int(planned_sets) + 1):
                base = rec_rows[i - 1] if i - 1 < len(rec_rows) else None
                default_weight = float(base["weight"]) if base and "weight" in base else 50.0
                default_reps = int(base["reps"]) if base and "reps" in base else 10

                logged = existing_by_num.get(i)
                if logged:
                    default_weight = float(logged.weight)
                    default_reps = int(logged.reps)

                row_cols = st.columns([1.2, 2.2, 2.0, 1.6, 1.6])

                with row_cols[0]:
                    st.markdown(f"**Set {i}**")

                # Stable per-set keys so values persist across reruns
                w_key = f"w_{session.id}_{we.id}_{i}"
                r_key = f"r_{session.id}_{we.id}_{i}"

                with row_cols[1]:
                    weight_val = st.number_input(
                        "Weight",
                        value=float(default_weight),
                        step=2.5,
                        key=w_key,
                        label_visibility="collapsed",
                    )

                with row_cols[2]:
                    reps_val = st.number_input(
                        "Reps",
                        value=int(default_reps),
                        step=1,
                        min_value=1,
                        key=r_key,
                        label_visibility="collapsed",
                    )

                with row_cols[3]:
                    if logged:
                        st.success("Logged ✅")
                    else:
                        st.info("Not logged")

                with row_cols[4]:
                    if logged:
                        if st.button("Update", key=f"btn_update_{session.id}_{we.id}_{i}"):
                            logged.weight = float(weight_val)
                            logged.reps = int(reps_val)
                            db.add(logged)
                            db.commit()
                            st.toast(f"Updated set {i} ✅", icon="✅")
                            st.rerun()
                    else:
                        if st.button("Log", key=f"btn_log_{session.id}_{we.id}_{i}"):
                            new_set = Set(
                                session_id=session.id,
                                workout_exercise_id=we.id,
                                set_number=int(i),
                                weight=float(weight_val),
                                reps=int(reps_val),
                                rir=None,
                            )
                            db.add(new_set)
                            db.commit()
                            st.toast(f"Logged set {i} ✅", icon="✅")
                            st.rerun()

            st.markdown("---")

        # Finish workout button (moves to next rotation session)
        if st.button("Finish Workout ✅"):
            st.session_state["rotation_index"] += 1
            st.toast("Workout complete — moving to next session.", icon="✅")
            st.rerun()


if __name__ == "__main__":
    main()

