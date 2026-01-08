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

from progression import recommend_weights_and_reps
from plan import get_session_exercises
from services import (
    get_or_create_today_session,
    get_or_create_workout_exercise,
    load_existing_sets,
    save_sets,
)


def _editor_key(session_id: int, we_id: int) -> str:
    return f"editor_{session_id}_{we_id}"


def _draft_key(session_id: int, we_id: int) -> str:
    return f"draft_{session_id}_{we_id}"


def _load_df_for_exercise(db, session_id: int, we: WorkoutExercise) -> pd.DataFrame:
    """
    Priority:
      1) draft from st.session_state (unsaved edits)
      2) saved sets from DB (if any)
      3) recommendations from progression.py
    """
    dk = _draft_key(session_id, we.id)

    # 1) Unsaved draft
    if dk in st.session_state and isinstance(st.session_state[dk], pd.DataFrame):
        return st.session_state[dk].copy()

    # 2) Saved sets
    existing_sets = load_existing_sets(db, session_id, we.id)
    if existing_sets:
        rows = []
        for s in existing_sets:
            rows.append(
                {
                    "set_number": int(s.set_number),
                    "weight": float(s.weight),
                    "reps": int(s.reps),
                    "done": True,  # already saved
                }
            )
        return pd.DataFrame(rows)

    # 3) Fresh recommendation
    rec_rows = recommend_weights_and_reps(db, we)
    df = pd.DataFrame(rec_rows)
    if "done" not in df.columns:
        df["done"] = False
    return df


def main():
    st.set_page_config(page_title="Workout Progression", layout="centered")
    st.title("Workout Progression")

    # rotation index lives only in Streamlit session state
    if "rotation_index" not in st.session_state:
        st.session_state["rotation_index"] = 0

    with get_session() as db:
        programs = db.query(Program).all()
        if not programs:
            st.error("No programs found. Run init_db.py first.")
            return

        # Use the first program for now
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

        # Rotation navigation
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

        # Create/retrieve today's session
        session = get_or_create_today_session(db, tracking_workout.id)
        st.info(f"Session date: {session.date}")

        exercises_for_session = get_session_exercises(session_index)

        # Render each exercise
        for order_idx, ex_name in enumerate(exercises_for_session):
            we = get_or_create_workout_exercise(db, tracking_workout, ex_name, order_idx)
            db.commit()  # commit any newly created Exercise/WorkoutExercise

            st.subheader(ex_name)

            # Load DF (draft -> db -> recommendation)
            df = _load_df_for_exercise(db, session.id, we)

            # Show editor
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
                key=_editor_key(session.id, we.id),
            )

            # Persist draft edits in session state so a rerun doesn't wipe them
            st.session_state[_draft_key(session.id, we.id)] = edited_df.copy()

            # Check saved sets status (for UI messaging only)
            existing_sets = load_existing_sets(db, session.id, we.id)
            already_saved = len(existing_sets) > 0

            # Save button (explicit > auto-save on rerun)
            btn_cols = st.columns([1, 1, 3])
            with btn_cols[0]:
                if st.button("Save sets", key=f"save_{session.id}_{we.id}"):
                    # Save only rows marked done=True
                    rows = edited_df.to_dict("records")
                    if not rows:
                        st.warning("No rows to save.")
                    else:
                        done_rows = [r for r in rows if bool(r.get("done", False))]
                        if not done_rows:
                            st.warning("Nothing is checked as Logged. Check the sets you completed, then Save.")
                        else:
                            save_sets(db, session.id, we.id, done_rows)

                            # clear draft so DB becomes the source of truth on reload
                            dk = _draft_key(session.id, we.id)
                            if dk in st.session_state:
                                del st.session_state[dk]

                            st.success("Saved ✅")

            with btn_cols[1]:
                if st.button("Reset draft", key=f"reset_{session.id}_{we.id}"):
                    # discard unsaved changes (draft) and rerun to reload
                    dk = _draft_key(session.id, we.id)
                    if dk in st.session_state:
                        del st.session_state[dk]
                    st.rerun()

            # Feedback expander (kept simple for now)
            # NOTE: We'll later move this to "after all exercises in the muscle group are saved"
            if already_saved:
                with st.expander("Feedback (for this exercise)", expanded=False):
                    st.radio(
                        "Soreness AFTER last time:",
                        [
                            "Never got sore",
                            "Healed a while ago",
                            "Healed just on time",
                            "I'm still sore",
                        ],
                        key=f"fb_{session.id}_{we.id}_soreness",
                    )
                    st.radio(
                        "Pump TODAY:",
                        ["Low pump", "Moderate pump", "Amazing pump"],
                        key=f"fb_{session.id}_{we.id}_pump",
                    )
                    st.radio(
                        "Workload TODAY:",
                        ["Easy", "Pretty good", "Pushed my limits", "Too much"],
                        key=f"fb_{session.id}_{we.id}_workload",
                    )

            st.markdown("---")


if __name__ == "__main__":
    main()
