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
from services import (
    get_or_create_today_session,
    get_or_create_workout_exercise,
    load_existing_sets,
    save_sets,
)

# ----------------- UI HELPERS -----------------

def inject_css():
    st.markdown(
        """
        <style>
        /* Prevent horizontal scrolling */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            overflow-x: hidden !important;
            max-width: 100vw !important;
        }
        
        /* Centered container with max-width for better desktop layout */
        .block-container {
            max-width: 900px;
            padding-top: 1rem;
            padding-bottom: 1.5rem;
            padding-left: 1.5rem;
            padding-right: 1.5rem;
            margin: 0 auto;
            overflow-x: hidden !important;
        }

        /* Header section */
        .header-container {
            margin-bottom: 1.5rem;
        }

        .session-info {
            text-align: center;
            font-size: 22px;
            font-weight: 900;
            margin-bottom: 4px;
        }

        .program-name {
            text-align: center;
            opacity: 0.75;
            font-size: 15px;
        }

        /* Exercise headers */
        h2 {
            font-size: 1.5rem !important;
            margin-bottom: 0.3rem !important;
            margin-top: 0 !important;
        }

        /* Set row container for better grouping */
        .set-row {
            margin-bottom: 0.5rem;
            padding: 0.5rem;
            border-radius: 8px;
            background: rgba(0,0,0,0.02);
        }

        /* Set label and badge row */
        .set-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.4rem;
        }

        .set-label {
            font-weight: 600;
            font-size: 14px;
        }

        /* Compact horizontal layout for inputs */
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
            gap: 0.5rem !important;
            align-items: stretch !important;
            overflow-x: visible !important;
        }

        div[data-testid="column"] {
            min-width: 0 !important;
            flex-shrink: 1 !important;
            overflow: visible !important;
        }

        /* Number inputs - more compact */
        div[data-testid="stNumberInput"],
        div[data-testid="stNumberInput"] > div {
            width: 100% !important;
            min-width: 0 !important;
            max-width: 100% !important;
        }

        div[data-testid="stNumberInput"] input {
            width: 100% !important;
            min-width: 0 !important;
            padding: 0.5rem 0.5rem !important;
            font-size: 15px !important;
            height: 40px !important;
            box-sizing: border-box !important;
        }

        /* Hide number input spinners */
        input[type="number"]::-webkit-inner-spin-button,
        input[type="number"]::-webkit-outer-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        input[type="number"] {
            -moz-appearance: textfield;
        }

        /* Buttons - match input height */
        .stButton > button {
            width: 100% !important;
            padding: 0.5rem 0.75rem !important;
            border-radius: 8px !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            height: 40px !important;
            box-sizing: border-box !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            overflow: visible !important;
        }
        
        .stButton {
            overflow: visible !important;
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 100%;
        }
        .badge-ok {
            background: rgba(46,204,113,0.20);
            color: rgba(46,204,113,1);
        }
        .badge-no {
            background: rgba(52,152,219,0.20);
            color: rgba(52,152,219,1);
        }

        /* Exercise gap */
        .exercise-gap {
            height: 1.5rem;
        }

        /* Caption text */
        .stCaption {
            margin-bottom: 0.75rem !important;
            font-size: 13px !important;
        }

        /* Tablet breakpoint (900px) */
        @media (max-width: 900px) {
            .block-container {
                max-width: 700px;
                padding-left: 1.25rem;
                padding-right: 1.25rem;
            }

            h2 {
                font-size: 1.4rem !important;
            }

            .session-info {
                font-size: 20px;
            }
        }

        /* Mobile breakpoint (600px) */
        @media (max-width: 600px) {
            .block-container {
                padding-left: 0.5rem;
                padding-right: 0.5rem;
                padding-top: 0.5rem;
            }

            h2 {
                font-size: 1.2rem !important;
                margin-bottom: 0.2rem !important;
            }

            .session-info {
                font-size: 16px;
            }

            .program-name {
                font-size: 12px;
            }

            div[data-testid="stHorizontalBlock"] {
                gap: 0.25rem !important;
            }

            div[data-testid="stNumberInput"] input {
                padding: 0.4rem 0.3rem !important;
                font-size: 14px !important;
                height: 38px !important;
            }

            .stButton > button {
                padding: 0.4rem 0.4rem !important;
                font-size: 12px !important;
                height: 38px !important;
                white-space: nowrap !important;
            }

            .set-row {
                padding: 0.3rem;
                margin-bottom: 0.3rem;
            }

            .badge {
                font-size: 9px;
                padding: 2px 6px;
                max-width: 60px;
            }

            .exercise-gap {
                height: 0.75rem;
            }

            .set-label {
                font-size: 13px;
            }

            .stCaption {
                font-size: 12px !important;
                margin-bottom: 0.5rem !important;
            }
        }

        /* Small mobile (375px minimum) */
        @media (max-width: 400px) {
            .block-container {
                padding-left: 0.4rem;
                padding-right: 0.4rem;
            }

            h2 {
                font-size: 1.1rem !important;
            }

            .session-info {
                font-size: 15px;
            }

            div[data-testid="stHorizontalBlock"] {
                gap: 0.2rem !important;
            }

            div[data-testid="stNumberInput"] input {
                font-size: 13px !important;
                padding: 0.35rem 0.25rem !important;
            }

            .stButton > button {
                font-size: 11px !important;
                padding: 0.35rem 0.3rem !important;
            }

            .badge {
                font-size: 8px;
                padding: 2px 5px;
                max-width: 50px;
            }

            .set-label {
                font-size: 12px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def number_input_int(key: str, default_value: int, min_value: int, step: int):
    if key not in st.session_state:
        st.session_state[key] = int(default_value)
        return st.number_input(
            label="",
            key=key,
            min_value=min_value,
            step=step,
            format="%d",
            label_visibility="collapsed",
            value=int(default_value),
        )
    return st.number_input(
        label="",
        key=key,
        min_value=min_value,
        step=step,
        format="%d",
        label_visibility="collapsed",
    )

# ----------------- MAIN APP -----------------

def main():
    st.set_page_config(
        page_title="Workout Progression",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    inject_css()

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

        # -------- Header (responsive) --------
        col_prev, col_mid, col_next = st.columns([1.0, 2.5, 1.0])

        with col_prev:
            if st.button("◀ Prev", key="prev_session") and st.session_state["rotation_index"] > 0:
                st.session_state["rotation_index"] -= 1
                st.rerun()

        with col_mid:
            sess_num = st.session_state["rotation_index"] + 1
            st.markdown(
                f"""
                <div class="header-container">
                  <div class="session-info">Session {sess_num} • {session.date}</div>
                  <div class="program-name">{prog.name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button("Next ▶", key="next_session"):
                st.session_state["rotation_index"] += 1
                st.rerun()

        st.markdown("<div class='exercise-gap'></div>", unsafe_allow_html=True)

        # Exercises for this session
        session_index = st.session_state["rotation_index"]
        exercises_for_session = get_session_exercises(session_index)

        for order_idx, ex_name in enumerate(exercises_for_session):
            we = get_or_create_workout_exercise(db, tracking_workout, ex_name, order_idx)
            db.commit()

            existing_sets = load_existing_sets(db, session.id, we.id)
            rec_rows = recommend_weights_and_reps(db, we)

            draft_key = f"draft_{session.id}_{we.id}"
            planned_key = f"planned_{session.id}_{we.id}"

            # Initialize draft once
            if draft_key not in st.session_state:
                if existing_sets:
                    draft = [
                        dict(
                            set_number=s.set_number,
                            weight=int(round(s.weight)),
                            reps=int(s.reps),
                            logged=True,
                        )
                        for s in existing_sets
                    ]
                else:
                    draft = [
                        dict(
                            set_number=int(r["set_number"]),
                            weight=int(round(float(r["weight"]))),
                            reps=int(r["reps"]),
                            logged=False,
                        )
                        for r in rec_rows
                    ]
                st.session_state[draft_key] = draft

            if planned_key not in st.session_state:
                st.session_state[planned_key] = len(st.session_state[draft_key])

            draft = st.session_state[draft_key]

            planned_sets = max(1, int(st.session_state[planned_key]))

            if len(draft) < planned_sets:
                last_w = draft[-1]["weight"] if draft else 0
                last_r = draft[-1]["reps"] if draft else 10
                start_n = len(draft) + 1
                for i in range(start_n, planned_sets + 1):
                    draft.append(dict(set_number=i, weight=last_w, reps=last_r, logged=False))
            elif len(draft) > planned_sets:
                while len(draft) > planned_sets and not draft[-1]["logged"]:
                    draft.pop()
                st.session_state[planned_key] = len(draft)
                planned_sets = len(draft)

            st.session_state[draft_key] = draft

            # -------- Exercise header row with +/- --------
            h1, h2 = st.columns([2.5, 1.5])
            with h1:
                st.markdown(f"## {ex_name}")
            with h2:
                c1, c2, c3 = st.columns([1.0, 1.0, 1.0])
                with c1:
                    if st.button("−", key=f"minus_{we.id}"):
                        if st.session_state[planned_key] > 1:
                            st.session_state[planned_key] -= 1
                            st.rerun()
                with c2:
                    st.markdown(
                        f"<div style='text-align:center; font-size:18px; font-weight:700; padding-top:8px;'>{st.session_state[planned_key]}</div>",
                        unsafe_allow_html=True,
                    )
                with c3:
                    if st.button("+", key=f"plus_{we.id}"):
                        st.session_state[planned_key] += 1
                        st.rerun()

            st.caption("Edit weight/reps, then press **Log** for each completed set.")

            # -------- Set rows --------
            for i, row in enumerate(draft, start=1):
                row_key_prefix = f"{session.id}_{we.id}_{i}"
                w_key = f"w_{row_key_prefix}"
                r_key = f"r_{row_key_prefix}"

                if w_key not in st.session_state:
                    st.session_state[w_key] = int(row["weight"])
                if r_key not in st.session_state:
                    st.session_state[r_key] = int(row["reps"])

                # Set header with label and badge
                label_col, badge_col = st.columns([1.2, 2.0])
                with label_col:
                    st.markdown(f"<div class='set-label'>Set {i}</div>", unsafe_allow_html=True)
                with badge_col:
                    badge = "badge-ok" if row["logged"] else "badge-no"
                    badge_text = "Logged ✅" if row["logged"] else "Not logged"
                    st.markdown(
                        f"<span class='badge {badge}'>{badge_text}</span>",
                        unsafe_allow_html=True,
                    )

                # Input row: Weight, Reps, Button (better proportions)
                cols = st.columns([1.2, 1.0, 1.2])

                with cols[0]:
                    number_input_int(
                        key=w_key,
                        default_value=int(row["weight"]),
                        min_value=0,
                        step=5,
                    )

                with cols[1]:
                    number_input_int(
                        key=r_key,
                        default_value=int(row["reps"]),
                        min_value=1,
                        step=1,
                    )

                with cols[2]:
                    if not row["logged"]:
                        if st.button("Log", key=f"log_{row_key_prefix}"):
                            row["weight"] = int(st.session_state[w_key])
                            row["reps"] = int(st.session_state[r_key])
                            row["logged"] = True
                            save_sets(db, session.id, we.id, draft)
                            st.session_state[draft_key] = draft
                            st.rerun()
                    else:
                        if st.button("Update", key=f"upd_{row_key_prefix}"):
                            row["weight"] = int(st.session_state[w_key])
                            row["reps"] = int(st.session_state[r_key])
                            save_sets(db, session.id, we.id, draft)
                            st.session_state[draft_key] = draft
                            st.rerun()

                # Minimal spacing between sets
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

            st.markdown("<div class='exercise-gap'></div>", unsafe_allow_html=True)

        st.markdown("<div class='exercise-gap'></div>", unsafe_allow_html=True)
        
        # Center the finish button
        _, center_col, _ = st.columns([1, 2, 1])
        with center_col:
            if st.button("✅ Finish Workout", key="finish_workout"):
                st.session_state["rotation_index"] += 1
                st.rerun()

if __name__ == "__main__":
    main()
