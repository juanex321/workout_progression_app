# plan.py
from __future__ import annotations

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

DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10

# per-exercise overrides for starting # of sets (finishers)
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

# per-exercise overrides for target reps (muscle-specific targeting)
EXERCISE_DEFAULT_REPS = {
    "Dumbbell Lateral Raise": 12,  # Higher rep range for delts
    "Cable Curl": 12,
    "Incline DB Curl": 12,
    # All other exercises default to DEFAULT_TARGET_REPS (10)
}

# Muscle group assignments for exercises
EXERCISE_MUSCLE_GROUPS = {
    # Leg exercises
    "Leg Extension": "Quads",
    "Sissy Squat": "Quads",
    "Leg Curl": "Hamstrings",
    "Hip Thrust + Glute Lunges": "Glutes",
    
    # Push exercises - Chest
    "Incline DB Bench Press": "Chest",
    "Single-arm Chest Fly": "Chest",
    
    # Push exercises - Triceps
    "Cable Tricep Pushdown": "Triceps",
    "Overhead Cable Extension": "Triceps",
    
    # Pull exercises - Lats
    "Lat Pulldown": "Lats",
    "Cable Row": "Lats",
    "Straight-arm Pulldown": "Lats",
    
    # Pull exercises - Biceps
    "Cable Curl": "Biceps",
    "Incline DB Curl": "Biceps",
    
    # Shoulders
    "Dumbbell Lateral Raise": "Shoulders",
}

def get_session_exercises(session_index: int) -> list[str]:
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
        upper_block = [
            "Incline DB Bench Press",
            "Single-arm Chest Fly",      # finisher, 1 set
            "Cable Tricep Pushdown",
            "Overhead Cable Extension",  # finisher, 1 set
        ]
    else:
        pull_session_number = session_index // 2  # counts only pull days
        pull_main = PULL_MAIN_ROTATION[pull_session_number % len(PULL_MAIN_ROTATION)]
        upper_block = [
            pull_main,
            "Straight-arm Pulldown",  # lat finisher
            PULL_SECONDARY,           # Cable Curl
            "Incline DB Curl",        # biceps finisher
        ]

    return leg_block + upper_block + [LATERAL_RAISES]
