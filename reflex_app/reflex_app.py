"""
Reflex version of the workout progression app.
This is a proof of concept running parallel to the Streamlit app.
"""

import reflex as rx
from typing import List, Dict
import sys
from pathlib import Path

# Add parent directory to path to import shared modules
sys.path.append(str(Path(__file__).parent.parent))

from db import get_session, Session as DbSession, Workout, WorkoutExercise
from progression import recommend_weights_and_reps
from rir_progression import get_rir_for_muscle_group, get_feedback_summary
from services import get_current_session, get_or_create_workout_exercise
from plan import get_session_exercises


class WorkoutState(rx.State):
    """State management for the workout app."""

    session_number: int = 1
    muscle_groups: Dict = {}

    def load_session(self):
        """Load the current session data."""
        with get_session() as db:
            # Get workout
            workout = db.query(Workout).first()
            if not workout:
                return

            # Get current session
            session = get_current_session(db, workout.id)
            self.session_number = session.session_number

            # Get exercises and group by muscle
            exercises_for_session = get_session_exercises(session.rotation_index)
            muscle_groups_data = {}

            for order_idx, ex_name in enumerate(exercises_for_session):
                we = get_or_create_workout_exercise(db, workout, ex_name, order_idx)
                muscle_group = we.exercise.muscle_group if we.exercise.muscle_group else we.exercise.name

                if muscle_group not in muscle_groups_data:
                    # Get RIR info for this muscle group
                    target_rir, phase, _ = get_rir_for_muscle_group(db, muscle_group)
                    feedback_summary = get_feedback_summary(db, muscle_group)

                    muscle_groups_data[muscle_group] = {
                        "target_rir": target_rir,
                        "phase": phase,
                        "feedback_summary": feedback_summary,
                        "exercises": []
                    }

                # Get recommended sets for this exercise
                rec_rows = recommend_weights_and_reps(db, we)

                muscle_groups_data[muscle_group]["exercises"].append({
                    "name": ex_name,
                    "sets": rec_rows,
                    "target_rir": muscle_groups_data[muscle_group]["target_rir"]
                })

            self.muscle_groups = muscle_groups_data


def get_rir_color(target_rir: int) -> str:
    """Get border color based on RIR level."""
    if target_rir >= 4:
        return "rgba(52,152,219,1)"  # Blue - Deload
    elif target_rir == 3:
        return "rgba(46,204,113,0.7)"  # Light Green - Moderate
    elif target_rir == 2:
        return "rgba(46,204,113,1)"  # Green - Hard
    elif target_rir == 1:
        return "rgba(255,165,0,1)"  # Orange - Very Hard
    else:
        return "rgba(231,76,60,1)"  # Red - Failure


def get_rir_emoji(target_rir: int) -> str:
    """Get emoji based on RIR level."""
    if target_rir >= 4:
        return "🔵"
    elif target_rir == 3:
        return "🟢"
    elif target_rir == 2:
        return "🟢"
    elif target_rir == 1:
        return "🟠"
    else:
        return "🔴"


def muscle_group_header(name: str, target_rir: int, phase: str, feedback: str) -> rx.Component:
    """Render the muscle group header."""
    emoji = get_rir_emoji(target_rir)

    return rx.box(
        rx.heading(f"{emoji} {name}", size="6", weight="bold"),
        rx.text(f"RIR {target_rir} - {phase}", size="2", opacity=0.8),
        rx.text(f"Recent: {feedback}", size="1", opacity=0.65, font_style="italic"),
        background="rgba(100, 100, 100, 0.08)",
        border_radius="8px",
        padding="0.8rem",
        margin_bottom="1rem",
    )


def exercise_set_row(set_data: Dict, set_num: int) -> rx.Component:
    """Render a single set row with weight, reps, and log button."""
    return rx.hstack(
        # Weight input
        rx.box(
            rx.input(
                value=str(set_data["weight"]),
                width="100%",
                size="3",
                text_align="center",
            ),
            flex="1.2",
        ),
        # Reps input
        rx.box(
            rx.input(
                value=str(set_data["reps"]),
                width="100%",
                size="3",
                text_align="center",
            ),
            flex="0.9",
        ),
        # Log button
        rx.box(
            rx.button("Log", size="3", width="100%"),
            flex="0.7",
        ),
        width="100%",
        spacing="2",
        margin_bottom="0.5rem",
    )


def exercise_sets(exercise_data: Dict) -> rx.Component:
    """Render all sets for an exercise."""
    return rx.box(
        rx.heading(exercise_data["name"], size="4", margin_bottom="0.5rem"),
        rx.foreach(
            exercise_data["sets"],
            lambda set_data, idx: exercise_set_row(set_data, idx)
        ),
        margin_bottom="1.5rem",
    )


def muscle_group_section(name: str, data: Dict) -> rx.Component:
    """
    Render a complete muscle group section with colored border.
    This is the key improvement over Streamlit - proper component wrapping!
    """
    border_color = get_rir_color(data["target_rir"])
    background = f"rgba{border_color[4:-1]}, 0.08)"  # Convert border color to background

    return rx.box(
        # Header
        muscle_group_header(
            name,
            data["target_rir"],
            data["phase"],
            data["feedback_summary"]
        ),

        # All exercises for this muscle group
        rx.foreach(
            data["exercises"],
            exercise_sets
        ),

        # Feedback form would go here
        rx.text("✅ Feedback form goes here", opacity=0.5),

        # Wrapper styling - THIS IS WHAT STREAMLIT COULDN'T DO EASILY!
        border=f"3px solid {border_color}",
        border_radius="12px",
        padding="1rem",
        margin_bottom="1.5rem",
        background=background,
        width="100%",
    )


def index() -> rx.Component:
    """Main page."""
    return rx.container(
        rx.vstack(
            # Header
            rx.hstack(
                rx.button("◀ Prev", size="2"),
                rx.heading(f"Session {WorkoutState.session_number}", size="7", text_align="center"),
                rx.button("Next ▶", size="2"),
                justify="between",
                width="100%",
                margin_bottom="2rem",
            ),

            # Muscle groups - properly wrapped with colored borders!
            rx.foreach(
                WorkoutState.muscle_groups,
                lambda name, data: muscle_group_section(name, data)
            ),

            # Finish button
            rx.button("✅ Finish Workout", size="3", width="100%", margin_top="2rem"),

            width="100%",
            spacing="4",
        ),
        max_width="900px",
        padding="2rem",
        on_mount=WorkoutState.load_session,
    )


# Create the app
app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="grass",
    )
)
app.add_page(index)
