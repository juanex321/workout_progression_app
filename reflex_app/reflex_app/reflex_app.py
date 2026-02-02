"""
Reflex version of the workout progression app.
Full implementation with all features from the Streamlit version.
"""

import reflex as rx
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import shared modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from db import get_session, Session as DbSession, Workout, WorkoutExercise, Set as DbSet, Feedback
from progression import recommend_weights_and_reps
from rir_progression import get_rir_for_muscle_group, get_feedback_summary
from services import (
    get_current_session,
    get_session_by_number,
    get_or_create_workout_exercise,
    load_existing_sets,
    save_muscle_group_feedback,
    check_muscle_group_feedback_exists,
    complete_session,
)
from plan import get_session_exercises


class SetData(rx.Base):
    """Data for a single set."""
    set_number: int
    we_id: int
    key: str
    target_reps: int
    target_rir: int


class ExerciseData(rx.Base):
    """Data for an exercise."""
    name: str
    we_id: int
    sets: List[SetData]


class MuscleGroupData(rx.Base):
    """Data for a muscle group."""
    name: str
    target_rir: int
    phase: str
    feedback_summary: str
    exercises: List[ExerciseData]
    border_color: str
    background_color: str
    emoji: str


class WorkoutState(rx.State):
    """State management for the workout app."""

    # Session info
    session_number: int = 1
    session_id: int = 0
    workout_id: int = 0
    rotation_index: int = 0
    max_session: int = 1

    # Muscle groups data - properly typed!
    muscle_groups_list: List[MuscleGroupData] = []

    # Input states for each set (keyed by "we_id:set_num")
    set_weights: Dict[str, str] = {}
    set_reps: Dict[str, str] = {}
    set_logged: Dict[str, bool] = {}

    # Feedback states (keyed by muscle_group name)
    feedback_soreness: Dict[str, int] = {}
    feedback_pump: Dict[str, int] = {}
    feedback_workload: Dict[str, int] = {}
    feedback_submitted: Dict[str, bool] = {}

    # UI state
    loading: bool = False
    error_message: str = ""

    def load_session(self, session_num: Optional[int] = None):
        """Load a specific session or the current one."""
        self.loading = True
        self.error_message = ""

        try:
            with get_session() as db:
                # Get workout
                workout = db.query(Workout).first()
                if not workout:
                    self.error_message = "No workout found in database!"
                    self.loading = False
                    return

                self.workout_id = workout.id

                # Get session
                if session_num is not None:
                    session = get_session_by_number(db, workout.id, session_num)
                else:
                    session = get_current_session(db, workout.id)

                if not session:
                    self.error_message = f"Session {session_num} not found!"
                    self.loading = False
                    return

                self.session_number = session.session_number
                self.session_id = session.id
                self.rotation_index = session.rotation_index

                # Get max session number
                max_sess = db.query(DbSession).filter(
                    DbSession.workout_id == workout.id
                ).order_by(DbSession.session_number.desc()).first()
                self.max_session = max_sess.session_number if max_sess else 1

                # Load all session data
                self._load_session_data(db, workout, session)

        except Exception as e:
            self.error_message = f"Error loading session: {str(e)}"
            print(f"Error in load_session: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.loading = False

    def _load_session_data(self, db, workout, session):
        """Load all exercises, sets, and feedback for the session."""
        exercises_for_session = get_session_exercises(session.rotation_index)
        muscle_groups_data = {}

        # Reset state dictionaries
        self.set_weights = {}
        self.set_reps = {}
        self.set_logged = {}
        self.feedback_soreness = {}
        self.feedback_pump = {}
        self.feedback_workload = {}
        self.feedback_submitted = {}

        for order_idx, ex_name in enumerate(exercises_for_session):
            we = get_or_create_workout_exercise(db, workout, ex_name, order_idx)
            muscle_group = we.exercise.muscle_group if we.exercise.muscle_group else we.exercise.name

            # Initialize muscle group if not exists
            if muscle_group not in muscle_groups_data:
                target_rir, phase, _ = get_rir_for_muscle_group(db, muscle_group)
                feedback_summary = get_feedback_summary(db, muscle_group)

                # Check if feedback exists for this muscle group
                feedback_exists = check_muscle_group_feedback_exists(db, session.id, muscle_group)
                self.feedback_submitted[muscle_group] = feedback_exists

                muscle_groups_data[muscle_group] = {
                    "target_rir": target_rir,
                    "phase": phase,
                    "feedback_summary": feedback_summary,
                    "exercises": []
                }

            # Load existing sets
            existing_sets = load_existing_sets(db, session.id, we.id)

            # Get recommendations
            rec_rows = recommend_weights_and_reps(db, we, muscle_group)

            # Build sets data
            sets_data = []
            for set_num, rec in enumerate(rec_rows, 1):
                # Find existing set if any
                existing = next((s for s in existing_sets if s.set_number == set_num), None)

                key = f"{we.id}:{set_num}"

                if existing:
                    # Use logged values
                    self.set_weights[key] = str(existing.weight) if existing.weight else ""
                    self.set_reps[key] = str(existing.reps) if existing.reps else ""
                    self.set_logged[key] = True
                else:
                    # Use recommended values
                    self.set_weights[key] = str(rec["weight"]) if rec.get("weight") else ""
                    self.set_reps[key] = str(rec["reps"]) if rec.get("reps") else ""
                    self.set_logged[key] = False

                sets_data.append(SetData(
                    set_number=set_num,
                    we_id=we.id,
                    key=key,
                    target_reps=rec.get("reps", 10),
                    target_rir=muscle_groups_data[muscle_group]["target_rir"],
                ))

            muscle_groups_data[muscle_group]["exercises"].append(ExerciseData(
                name=ex_name,
                we_id=we.id,
                sets=sets_data,
            ))

        # Convert to list for UI
        self.muscle_groups_list = [
            MuscleGroupData(
                name=name,
                target_rir=data["target_rir"],
                phase=data["phase"],
                feedback_summary=data["feedback_summary"],
                exercises=data["exercises"],
                border_color=get_rir_color(data["target_rir"]),
                background_color=get_rir_background(data["target_rir"]),
                emoji=get_rir_emoji(data["target_rir"])
            )
            for name, data in muscle_groups_data.items()
        ]

    def update_weight(self, key: str, value: str):
        """Update weight for a specific set."""
        self.set_weights[key] = value

    def update_reps(self, key: str, value: str):
        """Update reps for a specific set."""
        self.set_reps[key] = value

    def log_set(self, we_id: int, set_num: int):
        """Log a single set to the database."""
        key = f"{we_id}:{set_num}"

        try:
            weight = float(self.set_weights.get(key, "0") or "0")
            reps = int(self.set_reps.get(key, "0") or "0")

            if weight <= 0 or reps <= 0:
                return

            # Get target RIR for this exercise's muscle group
            target_rir = 2  # Default
            for mg in self.muscle_groups_list:
                for ex in mg.exercises:
                    if ex.we_id == we_id:
                        target_rir = mg.target_rir
                        break

            with get_session() as db:
                # Check if set already exists
                existing = db.query(DbSet).filter(
                    DbSet.session_id == self.session_id,
                    DbSet.workout_exercise_id == we_id,
                    DbSet.set_number == set_num
                ).first()

                if existing:
                    # Update existing
                    existing.weight = weight
                    existing.reps = reps
                    existing.rir = target_rir
                    existing.logged_at = datetime.now()
                else:
                    # Create new
                    new_set = DbSet(
                        session_id=self.session_id,
                        workout_exercise_id=we_id,
                        set_number=set_num,
                        weight=weight,
                        reps=reps,
                        rir=target_rir,
                        logged_at=datetime.now()
                    )
                    db.add(new_set)

                db.commit()

            # Mark as logged
            self.set_logged[key] = True

        except ValueError:
            # Invalid input
            pass
        except Exception as e:
            self.error_message = f"Error logging set: {str(e)}"
            print(f"Error in log_set: {e}")

    def update_feedback(self, muscle_group: str, field: str, value: int):
        """Update feedback value for a muscle group."""
        if field == "soreness":
            self.feedback_soreness[muscle_group] = value
        elif field == "pump":
            self.feedback_pump[muscle_group] = value
        elif field == "workload":
            self.feedback_workload[muscle_group] = value

    def submit_feedback(self, muscle_group: str):
        """Submit feedback for a muscle group."""
        try:
            soreness = self.feedback_soreness.get(muscle_group, 3)
            pump = self.feedback_pump.get(muscle_group, 3)
            workload = self.feedback_workload.get(muscle_group, 3)

            with get_session() as db:
                save_muscle_group_feedback(
                    db,
                    self.session_id,
                    muscle_group,
                    soreness,
                    pump,
                    workload
                )
                db.commit()

            self.feedback_submitted[muscle_group] = True

        except Exception as e:
            self.error_message = f"Error submitting feedback: {str(e)}"
            print(f"Error in submit_feedback: {e}")

    def go_to_prev_session(self):
        """Navigate to previous session."""
        if self.session_number > 1:
            self.load_session(self.session_number - 1)

    def go_to_next_session(self):
        """Navigate to next session."""
        if self.session_number < self.max_session:
            self.load_session(self.session_number + 1)
        else:
            # Create new session
            try:
                with get_session() as db:
                    workout = db.query(Workout).get(self.workout_id)
                    if workout:
                        # Complete current session and create next
                        current_session = db.query(DbSession).get(self.session_id)
                        if current_session:
                            complete_session(db, current_session.id)
                            db.commit()
                            self.load_session(self.session_number + 1)
            except Exception as e:
                self.error_message = f"Error creating new session: {str(e)}"
                print(f"Error in go_to_next_session: {e}")


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


def get_rir_background(target_rir: int) -> str:
    """Get background color based on RIR level."""
    if target_rir >= 4:
        return "rgba(52,152,219,0.08)"  # Blue - Deload
    elif target_rir == 3:
        return "rgba(46,204,113,0.05)"  # Light Green - Moderate
    elif target_rir == 2:
        return "rgba(46,204,113,0.08)"  # Green - Hard
    elif target_rir == 1:
        return "rgba(255,165,0,0.08)"  # Orange - Very Hard
    else:
        return "rgba(231,76,60,0.08)"  # Red - Failure


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


def muscle_group_header(mg_data: MuscleGroupData) -> rx.Component:
    """Render the muscle group header."""
    return rx.box(
        rx.heading(
            f"{mg_data.emoji} {mg_data.name}",
            size="6",
            weight="bold",
            margin_bottom="0.2rem"
        ),
        rx.text(
            f"RIR {mg_data.target_rir} - {mg_data.phase}",
            size="2",
            opacity=0.8
        ),
        rx.text(
            f"Recent: {mg_data.feedback_summary}",
            size="1",
            opacity=0.65,
            font_style="italic"
        ),
        background="rgba(100, 100, 100, 0.08)",
        border_radius="8px",
        padding="0.8rem",
        margin_bottom="1rem",
    )


def exercise_set_row(set_data: SetData) -> rx.Component:
    """Render a single set row with weight, reps, and log button."""
    key = set_data.key
    is_logged = WorkoutState.set_logged.get(key, False)

    return rx.hstack(
        # Set number
        rx.text(
            f"Set {set_data.set_number}",
            size="2",
            weight="medium",
            width="60px",
            opacity=0.7
        ),
        # Weight input
        rx.input(
            value=WorkoutState.set_weights.get(key, ""),
            on_change=lambda val, k=key: WorkoutState.update_weight(k, val),
            placeholder="Weight",
            type="number",
            size="3",
            width="90px",
            disabled=is_logged,
        ),
        # Reps input
        rx.input(
            value=WorkoutState.set_reps.get(key, ""),
            on_change=lambda val, k=key: WorkoutState.update_reps(k, val),
            placeholder="Reps",
            type="number",
            size="3",
            width="70px",
            disabled=is_logged,
        ),
        # Target info
        rx.text(
            f"({set_data.target_reps}r @ RIR {set_data.target_rir})",
            size="1",
            opacity=0.5,
            width="100px"
        ),
        # Log button
        rx.button(
            rx.cond(is_logged, "✓", "Log"),
            on_click=lambda w=set_data.we_id, s=set_data.set_number: WorkoutState.log_set(w, s),
            size="2",
            color_scheme=rx.cond(is_logged, "green", "gray"),
            variant=rx.cond(is_logged, "soft", "solid"),
            disabled=is_logged,
        ),
        spacing="2",
        margin_bottom="0.5rem",
        width="100%",
        align="center",
    )


def exercise_sets(exercise_data: ExerciseData) -> rx.Component:
    """Render all sets for an exercise."""
    return rx.box(
        rx.heading(
            exercise_data.name,
            size="4",
            margin_bottom="0.5rem",
            weight="medium"
        ),
        rx.foreach(
            exercise_data.sets,
            exercise_set_row
        ),
        margin_bottom="1.5rem",
    )


def feedback_form(mg_data: MuscleGroupData) -> rx.Component:
    """Render feedback form for a muscle group."""
    mg_name = mg_data.name
    is_submitted = WorkoutState.feedback_submitted.get(mg_name, False)

    return rx.box(
        rx.divider(margin_y="1rem"),
        rx.heading("Feedback", size="4", margin_bottom="0.8rem"),

        # Soreness slider
        rx.vstack(
            rx.hstack(
                rx.text("Soreness", size="2", weight="medium", width="100px"),
                rx.text(
                    f"{WorkoutState.feedback_soreness.get(mg_name, 3)}/5",
                    size="2",
                    opacity=0.7
                ),
                justify="between",
                width="100%"
            ),
            rx.slider(
                value=[WorkoutState.feedback_soreness.get(mg_name, 3)],
                on_change=lambda val, mg=mg_name: WorkoutState.update_feedback(mg, "soreness", val[0]),
                min=1,
                max=5,
                step=1,
                disabled=is_submitted,
                width="100%"
            ),
            margin_bottom="0.8rem",
            width="100%",
            align="start"
        ),

        # Pump slider
        rx.vstack(
            rx.hstack(
                rx.text("Pump", size="2", weight="medium", width="100px"),
                rx.text(
                    f"{WorkoutState.feedback_pump.get(mg_name, 3)}/5",
                    size="2",
                    opacity=0.7
                ),
                justify="between",
                width="100%"
            ),
            rx.slider(
                value=[WorkoutState.feedback_pump.get(mg_name, 3)],
                on_change=lambda val, mg=mg_name: WorkoutState.update_feedback(mg, "pump", val[0]),
                min=1,
                max=5,
                step=1,
                disabled=is_submitted,
                width="100%"
            ),
            margin_bottom="0.8rem",
            width="100%",
            align="start"
        ),

        # Workload slider
        rx.vstack(
            rx.hstack(
                rx.text("Workload", size="2", weight="medium", width="100px"),
                rx.text(
                    f"{WorkoutState.feedback_workload.get(mg_name, 3)}/5",
                    size="2",
                    opacity=0.7
                ),
                justify="between",
                width="100%"
            ),
            rx.slider(
                value=[WorkoutState.feedback_workload.get(mg_name, 3)],
                on_change=lambda val, mg=mg_name: WorkoutState.update_feedback(mg, "workload", val[0]),
                min=1,
                max=5,
                step=1,
                disabled=is_submitted,
                width="100%"
            ),
            margin_bottom="1rem",
            width="100%",
            align="start"
        ),

        # Submit button
        rx.button(
            rx.cond(is_submitted, "✓ Submitted", "Submit Feedback"),
            on_click=lambda mg=mg_name: WorkoutState.submit_feedback(mg),
            size="3",
            width="100%",
            color_scheme=rx.cond(is_submitted, "green", "blue"),
            variant=rx.cond(is_submitted, "soft", "solid"),
            disabled=is_submitted,
        ),

        padding_top="0.5rem",
    )


def muscle_group_section(mg_data: MuscleGroupData) -> rx.Component:
    """Render a complete muscle group section with colored border."""
    return rx.box(
        # Header
        muscle_group_header(mg_data),

        # Exercises
        rx.foreach(
            mg_data.exercises,
            exercise_sets
        ),

        # Feedback form
        feedback_form(mg_data),

        # Wrapper styling - THIS IS THE KEY IMPROVEMENT!
        border=f"3px solid {mg_data.border_color}",
        border_radius="12px",
        padding="1rem",
        margin_bottom="1.5rem",
        background=mg_data.background_color,
        width="100%",
    )


def index() -> rx.Component:
    """Main page."""
    return rx.container(
        rx.vstack(
            # Error message
            rx.cond(
                WorkoutState.error_message != "",
                rx.callout(
                    WorkoutState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                    margin_bottom="1rem"
                ),
            ),

            # Header with navigation
            rx.hstack(
                rx.button(
                    "◀ Prev",
                    on_click=WorkoutState.go_to_prev_session,
                    size="3",
                    disabled=WorkoutState.session_number <= 1,
                    variant="soft"
                ),
                rx.heading(
                    f"Session {WorkoutState.session_number}",
                    size="7",
                    text_align="center",
                    flex="1"
                ),
                rx.button(
                    rx.cond(
                        WorkoutState.session_number < WorkoutState.max_session,
                        "Next ▶",
                        "New ▶"
                    ),
                    on_click=WorkoutState.go_to_next_session,
                    size="3",
                    variant="soft"
                ),
                justify="between",
                width="100%",
                margin_bottom="2rem",
                align="center"
            ),

            # Loading state
            rx.cond(
                WorkoutState.loading,
                rx.spinner(size="3"),
                # Muscle groups - properly wrapped with colored borders!
                rx.foreach(
                    WorkoutState.muscle_groups_list,
                    muscle_group_section
                ),
            ),

            width="100%",
            spacing="4",
        ),
        max_width="900px",
        padding="2rem 1rem",
        on_mount=WorkoutState.load_session,
    )


# Create the app
app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="grass",
    )
)
app.add_page(index, title="Workout Tracker")
