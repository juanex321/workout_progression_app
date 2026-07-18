# plan.py
from __future__ import annotations

# ----------------- ROTATION CONFIG -----------------

# Hamstrings use RDLs on chest/push days and the existing leg curl on back/pull days.
HAMSTRING_PUSH_EXERCISE = "Romanian Deadlift"
HAMSTRING_PULL_EXERCISE = "Leg Curl"

LEG_ROTATION = ["Quads", "Hamstrings", "Glutes"]
QUAD_EXERCISE = "Leg Extension"
GLUTE_PUSH_EXERCISE = "Glute Kickbacks"
GLUTE_PULL_EXERCISE = "Hip Thrust"

PULL_MAIN_ROTATION = [
    "Lat Pulldown",
    "Cable Row",
]

PULL_SECONDARY = "Cable Curl"

# Shoulder exercises alternate each session for lateral-head variety
SHOULDER_ROTATION = [
    "Dumbbell Lateral Raise",
    "Dumbbell Upright Row",
]

DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10

# per-exercise overrides for starting # of sets (finishers)
EXERCISE_DEFAULT_SETS = {
    # chest finisher
    "Single-arm Chest Fly": 1,
    # lat finisher
    "Straight-arm Pulldown": 1,
    # biceps finisher
    "Incline DB Curl": 1,
    # triceps finisher
    "Overhead Cable Extension": 1,
}

# per-exercise overrides for target reps (muscle-specific targeting)
EXERCISE_DEFAULT_REPS = {
    "Dumbbell Lateral Raise": 12,   # Higher rep range for delts
    "Dumbbell Upright Row": 12,     # Same rep range for lateral head stimulus
    "Cable Curl": 12,
    "Incline DB Curl": 12,
    # All other exercises default to DEFAULT_TARGET_REPS (10)
}

# Mapping of exercise names to muscle groups
EXERCISE_MUSCLE_GROUPS = {
    # Legs
    "Leg Extension": "Quads",
    "Leg Curl": "Hamstrings",
    "Romanian Deadlift": "Hamstrings",
    "Hip Thrust": "Glutes",
    "Glute Kickbacks": "Glutes",
    
    # Chest
    "Incline DB Bench Press": "Chest",
    "Single-arm Chest Fly": "Chest",
    
    # Back/Lats
    "Lat Pulldown": "Lats",
    "Cable Row": "Lats",
    "Straight-arm Pulldown": "Lats",
    
    # Arms
    "Cable Tricep Pushdown": "Triceps",
    "Overhead Cable Extension": "Triceps",
    "Cable Curl": "Biceps",
    "Incline DB Curl": "Biceps",
    
    # Shoulders
    "Dumbbell Lateral Raise": "Shoulders",
    "Dumbbell Upright Row": "Shoulders",
}

def get_session_exercises_for_focus(
    leg_index: int,
    is_push_day: bool,
    shoulder_index: int,
) -> list[str]:
    """Build one workout from independent lower-, upper-, and shoulder rotations."""
    leg_focus = LEG_ROTATION[leg_index % len(LEG_ROTATION)]
    if leg_focus == "Quads":
        leg_exercise = QUAD_EXERCISE
    elif leg_focus == "Hamstrings":
        leg_exercise = HAMSTRING_PUSH_EXERCISE if is_push_day else HAMSTRING_PULL_EXERCISE
    else:
        leg_exercise = GLUTE_PUSH_EXERCISE if is_push_day else GLUTE_PULL_EXERCISE

    if is_push_day:
        upper_block = [
            "Incline DB Bench Press",
            "Single-arm Chest Fly",
            "Cable Tricep Pushdown",
            "Overhead Cable Extension",
        ]
    else:
        pull_main = PULL_MAIN_ROTATION[(shoulder_index // 2) % len(PULL_MAIN_ROTATION)]
        upper_block = [
            pull_main,
            "Straight-arm Pulldown",
            PULL_SECONDARY,
            "Incline DB Curl",
        ]

    shoulder_exercise = SHOULDER_ROTATION[shoulder_index % len(SHOULDER_ROTATION)]
    return [leg_exercise] + upper_block + [shoulder_exercise]


def get_session_exercises(session_index: int) -> list[str]:
    """
    session_index: 0-based training session number.
    Returns an ordered list of exercise names for that session.

    Pattern:
      - Lower body progresses Quads → Hamstrings → Glutes independently.
      - Push / Pull alternates each session.
      - Pull days alternate Lat Pulldown / Cable Row.
      - Finish every session with lateral raises.
      - Certain upper muscles get finisher exercises.
    """
    is_push_day = (session_index % 2 == 0)
    return get_session_exercises_for_focus(
        leg_index=session_index % len(LEG_ROTATION),
        is_push_day=is_push_day,
        shoulder_index=session_index,
    )
