# progression.py

from typing import List, Tuple
from sqlalchemy.orm import Session as OrmSession

from db import Set, Session, Feedback, WorkoutExercise
from plan import DEFAULT_TARGET_SETS

# ------- constants / config -------

DEFAULT_BASE_WEIGHT = 50.0

MIN_SETS = 1
MAX_SETS_MAIN = 10          # upper cap for normal exercises
MAX_SETS_FINISHER = 3       # upper cap for 1-set finishers

MIN_TARGET_REPS = 8
MAX_TARGET_REPS = 15

# Fatigue model: rep drop-off per set after the first
# This models realistic performance decline across sets
# Set 1 = target_reps, Set 2 = target_reps - 1, Set 3 = target_reps - 2, etc.
FATIGUE_REP_DROP_PER_SET = 1
MIN_REPS_FLOOR = 5  # Never recommend fewer than this many reps

# names of finisher-style movements that should stay low-volume
FINISHER_NAMES = {
    "Single-arm Chest Fly",
    "Sissy Squat",
    "Straight-arm Pulldown",
    "Incline DB Curl",
    "Overhead Cable Extension",
}

# thresholds for interpreting feedback
# 1-2: fully recovered → +1 set
# 3: recovered just in time → keep sets
# 4-5: not fully recovered → -1 set (5 is almost certain)
SORENESS_HIGH = 4      # ≥4 triggers set reduction
WORKLOAD_HIGH = 4      # ≥4 indicates too much volume


# ------- helpers -------

def get_last_session_sets(
    db: OrmSession, workout_exercise_id: int
) -> Tuple[int | None, List[Set] | None]:
    """
    Return (session_id, [Set, ...]) for the most recent completed session of this exercise.
    """
    q = (
        db.query(Set)
        .join(Session, Set.session_id == Session.id)
        .filter(Set.workout_exercise_id == workout_exercise_id)
        .filter(Session.completed == 1)  # Only look at completed sessions
        .order_by(Session.session_number.desc(), Set.set_number.asc())
    )
    sets = q.all()
    if not sets:
        return None, None

    sessions: dict[int, list[Set]] = {}
    for s in sets:
        sessions.setdefault(s.session_id, []).append(s)

    last_sid = list(sessions.keys())[0]
    return last_sid, sessions[last_sid]


def get_recent_feedback(
    db: OrmSession, workout_exercise_id: int, limit: int = 3
) -> List[Feedback]:
    return (
        db.query(Feedback)
        .filter(Feedback.workout_exercise_id == workout_exercise_id)
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .all()
    )


def get_recent_muscle_group_feedback(
    db: OrmSession, muscle_group: str, limit: int = 3
) -> List[Feedback]:
    """
    Get recent feedback for a muscle group (not tied to specific exercises).

    This is used for muscle-group-level feedback that applies to all exercises
    in that muscle group.
    """
    return (
        db.query(Feedback)
        .filter(Feedback.muscle_group == muscle_group)
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .all()
    )


def is_finisher(we: WorkoutExercise) -> bool:
    name = (we.exercise.name or "").strip()
    return name in FINISHER_NAMES


def adjust_sets_based_on_feedback(db: OrmSession, we: WorkoutExercise) -> int:
    """
    Look at the last few feedback entries and gently move target_sets up or down.

    * If soreness, pump and workload have been LOW → +1 set (up to cap).
    * If soreness or workload have been HIGH      → -1 set (down to 1).

    Now uses muscle group feedback (not exercise-specific feedback).

    IMPORTANT: Finishers ALWAYS stay at 1 set - no adjustments based on feedback.
    If more volume is needed, add to core movements instead.
    """
    target_sets = we.target_sets or DEFAULT_TARGET_SETS

    # CRITICAL: Finishers always stay at 1 set - skip all feedback adjustments
    if is_finisher(we):
        return target_sets

    # Get muscle group from exercise
    muscle_group = we.exercise.muscle_group if we.exercise and we.exercise.muscle_group else None

    if not muscle_group:
        # No muscle group assigned, can't adjust based on feedback
        return target_sets

    # Get muscle group feedback (not exercise-specific)
    fb_list = get_recent_muscle_group_feedback(db, muscle_group, limit=3)
    if not fb_list:
        return target_sets

    avg_s = sum(f.soreness or 0 for f in fb_list) / len(fb_list)
    avg_p = sum(f.pump or 0 for f in fb_list) / len(fb_list)
    avg_w = sum(f.workload or 0 for f in fb_list) / len(fb_list)

    max_sets = MAX_SETS_FINISHER if is_finisher(we) else MAX_SETS_MAIN
    changed = False

    # "Under-stimulated" → add a set.
    if (
        avg_s <= 2
        and avg_p <= 2
        and avg_w <= 2
        and target_sets < max_sets
    ):
        target_sets += 1
        changed = True

    # "Beaten up / too much" → remove a set.
    elif (
        (avg_s >= SORENESS_HIGH or avg_w >= WORKLOAD_HIGH)
        and target_sets > MIN_SETS
    ):
        target_sets -= 1
        changed = True

    if changed:
        we.target_sets = int(target_sets)
        db.add(we)
        db.commit()

    return int(target_sets)


def should_deload_by_muscle_group(db: OrmSession, muscle_group: str) -> bool:
    """
    Check if a muscle group should deload based on recent feedback.

    Uses the RIR progression system's deload detection.
    Deload is triggered when feedback indicates excessive fatigue/overtraining.

    Args:
        db: Database session
        muscle_group: Name of the muscle group

    Returns:
        True if deload is needed for this muscle group
    """
    from rir_progression import get_rir_for_muscle_group, RIR_DELOAD

    target_rir, phase, _ = get_rir_for_muscle_group(db, muscle_group)
    return target_rir >= RIR_DELOAD


def calculate_reps_with_rir_progression(
    we: WorkoutExercise, last_sets: List[Set] | None, current_rir: int
) -> int:
    """
    Calculate target reps based on last session's performance and RIR change.

    Progression logic:
    - If last session was 8 reps at RIR 2, next session at RIR 2 = 9 reps (+1)
    - If next session is RIR 1 (harder) = 10 reps (+2)
    - If next session is RIR 3 (easier) = 8 reps (maintain)

    Formula: target_reps = last_reps + 1 + (last_rir - current_rir)

    This ensures the plan "tracks the user" while adjusting for intensity changes.

    Args:
        we: WorkoutExercise object
        last_sets: Sets from the last session
        current_rir: RIR for current session

    Returns:
        Target reps for next session
    """
    if not last_sets:
        # No history - use stored target or default
        return we.target_reps or 10

    # Get first set from last session (strongest/freshest set)
    first_set = min(last_sets, key=lambda s: s.set_number)
    last_reps = int(first_set.reps or 10)
    last_rir = first_set.rir if first_set.rir is not None else current_rir

    # Calculate RIR change (positive = getting harder, negative = getting easier)
    rir_change = last_rir - current_rir

    # Base progression (+1 rep) + RIR adjustment
    target_reps = last_reps + 1 + rir_change

    # Cap at max reps
    target_reps = min(target_reps, MAX_TARGET_REPS)

    # Floor at reasonable minimum
    target_reps = max(target_reps, MIN_TARGET_REPS)

    return int(target_reps)


def should_suggest_weight_increase(
    db: OrmSession, we: WorkoutExercise, last_sets: List[Set] | None
) -> bool:
    """
    Suggest weight increase when hitting max reps on first set with high volume.

    With fatigue modeling, only the FIRST set is the true performance reference.

    Args:
        db: Database session
        we: WorkoutExercise object
        last_sets: Sets from the last session

    Returns:
        True if weight increase should be suggested
    """
    target_reps = we.target_reps or 10

    if not last_sets:
        return False

    # Get first set (the reference point)
    first_set = min(last_sets, key=lambda s: s.set_number)
    first_set_reps = first_set.reps or 0

    # Suggest weight increase if:
    # 1. At max reps (15)
    # 2. First set hit the target
    # 3. High volume (4+ sets)
    first_set_hit_target = first_set_reps >= target_reps
    at_max_reps = target_reps >= MAX_TARGET_REPS
    high_volume = len(last_sets) >= 4

    return first_set_hit_target and at_max_reps and high_volume


# ------- main API -------

def recommend_weights_and_reps(
    db: OrmSession, we: WorkoutExercise, muscle_group: str = None
) -> list[dict]:
    """
    Main entry used by app.py.

    Progression hierarchy:
    1. Adjust target_sets based on recent feedback (primary progression).
    2. Adjust target_reps based on performance (secondary progression).
    3. Keep weight the same as last session (manual changes only).
    4. If deload is indicated → drop weight to ~55%.
       - For finishers during deload: reduce weight only, keep reps same.
    5. Return rows ready for the Streamlit data editor.

    Args:
        db: Database session
        we: WorkoutExercise object
        muscle_group: Name of the muscle group (for deload detection)
    """
    # Get muscle group from exercise if not provided
    if muscle_group is None:
        muscle_group = we.exercise.muscle_group if we.exercise and we.exercise.muscle_group else None

    # Get current RIR for this muscle group (used for rep calculation and deload)
    from rir_progression import get_rir_for_muscle_group, RIR_DELOAD
    if muscle_group:
        current_rir, _, _ = get_rir_for_muscle_group(db, muscle_group)
    else:
        current_rir = 2  # Default moderate RIR if no muscle group

    # Check if this is a finisher exercise
    is_finisher_exercise = is_finisher(we)

    # 1) volume adjustment (primary progression)
    target_sets = adjust_sets_based_on_feedback(db, we)

    # 2) get last session data
    _, last_sets = get_last_session_sets(db, we.id)

    # 3) rep calculation based on last session + RIR progression
    target_reps = calculate_reps_with_rir_progression(we, last_sets, current_rir)

    # 4) weight logic - copy from last session (NO auto-increment)
    if not last_sets:
        next_weight = DEFAULT_BASE_WEIGHT
    else:
        # Simply copy the last weight - user manually increases when ready
        last_weight = last_sets[0].weight or DEFAULT_BASE_WEIGHT
        next_weight = last_weight

    # 5) deload override - applies to ALL exercises including finishers
    deload_active = False
    if current_rir >= RIR_DELOAD:
        deload_active = True
        next_weight = max(next_weight * 0.55, 5.0)  # keep some floor

    # 6) check if we should suggest weight increase (informational only)
    suggest_weight = should_suggest_weight_increase(db, we, last_sets)

    # 7) build plan rows with fatigue model
    # First set = target_reps (strongest/freshest)
    # Subsequent sets = realistic decline based on fatigue
    rows: list[dict] = []
    for i in range(1, int(target_sets) + 1):
        # Apply fatigue: each set after the first drops by FATIGUE_REP_DROP_PER_SET
        # BUT: for finishers during deload, keep reps the same (no fatigue drop)
        if is_finisher_exercise and deload_active:
            # Finishers during deload: keep target reps, no fatigue model
            set_reps = target_reps
        else:
            sets_of_fatigue = i - 1  # 0 for first set, 1 for second, etc.
            fatigued_reps = target_reps - (sets_of_fatigue * FATIGUE_REP_DROP_PER_SET)
            # Never go below the floor
            set_reps = max(fatigued_reps, MIN_REPS_FLOOR)

        row = {
            "set_number": i,
            "weight": round(float(next_weight), 1),
            "reps": int(set_reps),
            "done": False,
        }
        # Add UI hint flag to first row if weight increase suggested
        # This flag is for informational display only and not persisted
        if i == 1 and suggest_weight:
            row["_suggest_weight_increase"] = True
        rows.append(row)

    return rows
