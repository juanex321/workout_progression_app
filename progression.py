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
SORENESS_HIGH = 3      # 3–4 = pretty sore / still sore
WORKLOAD_HIGH = 3      # 3–4 = pushed / too much


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


def is_finisher(we: WorkoutExercise) -> bool:
    name = (we.exercise.name or "").strip()
    return name in FINISHER_NAMES


def adjust_sets_based_on_feedback(db: OrmSession, we: WorkoutExercise) -> int:
    """
    Look at the last few feedback entries and gently move target_sets up or down.

    * If soreness, pump and workload have been LOW → +1 set (up to cap).
    * If soreness or workload have been HIGH      → -1 set (down to 1).
    """
    target_sets = we.target_sets or DEFAULT_TARGET_SETS

    fb_list = get_recent_feedback(db, we.id, limit=3)
    if not fb_list:
        return target_sets

    avg_s = sum(f.soreness or 0 for f in fb_list) / len(fb_list)
    avg_p = sum(f.pump or 0 for f in fb_list) / len(fb_list)
    avg_w = sum(f.workload or 0 for f in fb_list) / len(fb_list)

    max_sets = MAX_SETS_FINISHER if is_finisher(we) else MAX_SETS_MAIN
    changed = False

    # “Under-stimulated” → add a set.
    if (
        avg_s <= 2
        and avg_p <= 2
        and avg_w <= 2
        and target_sets < max_sets
    ):
        target_sets += 1
        changed = True

    # “Beaten up / too much” → remove a set.
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


def should_deload(db: OrmSession, we: WorkoutExercise) -> bool:
    """
    Simple auto-deload rule:

    If in the last 3 feedback entries for this exercise:
      - at least 2 have workload = 4 ("Too much"), OR
      - workload >=3 AND soreness >=4 in at least 2 entries,

    then the NEXT session is treated as a deload (drop load ~55%).
    """
    fb_list = get_recent_feedback(db, we.id, limit=3)
    if len(fb_list) < 3:
        return False

    high_work = sum(1 for f in fb_list if (f.workload or 0) >= 4)
    high_sore = sum(1 for f in fb_list if (f.soreness or 0) >= 4)

    if high_work >= 2:
        return True
    if high_work >= 1 and high_sore >= 2:
        return True
    return False


def adjust_reps_based_on_performance(
    db: OrmSession, we: WorkoutExercise, last_sets: List[Set] | None
) -> int:
    """
    Auto-increase reps by 1 when first set hits target (up to max 15 reps).

    With fatigue modeling, only the FIRST set is the true performance reference.
    If set 1 hits target_reps, the user is ready to progress.

    Args:
        db: Database session
        we: WorkoutExercise object
        last_sets: Sets from the last session (sorted by set_number)

    Returns:
        Updated target_reps
    """
    target_reps = we.target_reps or 10

    # Don't adjust if no previous data
    if not last_sets:
        return target_reps

    # Get first set (the reference point for progression)
    first_set = min(last_sets, key=lambda s: s.set_number)
    first_set_reps = first_set.reps or 0

    # If first set hit or exceeded target and we're below max, increment reps
    if first_set_reps >= target_reps and target_reps < MAX_TARGET_REPS:
        target_reps += 1
        we.target_reps = target_reps
        db.add(we)
        db.commit()

    return target_reps


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
    db: OrmSession, we: WorkoutExercise
) -> list[dict]:
    """
    Main entry used by app.py.

    Progression hierarchy:
    1. Adjust target_sets based on recent feedback (primary progression).
    2. Adjust target_reps based on performance (secondary progression).
    3. Keep weight the same as last session (manual changes only).
    4. If deload is indicated → drop weight to ~55%.
    5. Return rows ready for the Streamlit data editor.
    """
    # 1) volume adjustment (primary progression)
    target_sets = adjust_sets_based_on_feedback(db, we)
    
    # 2) get last session data
    _, last_sets = get_last_session_sets(db, we.id)
    
    # 3) rep adjustment (secondary progression)
    target_reps = adjust_reps_based_on_performance(db, we, last_sets)
    
    # 4) weight logic - copy from last session (NO auto-increment)
    if not last_sets:
        next_weight = DEFAULT_BASE_WEIGHT
    else:
        # Simply copy the last weight - user manually increases when ready
        last_weight = last_sets[0].weight or DEFAULT_BASE_WEIGHT
        next_weight = last_weight
    
    # 5) deload override
    if should_deload(db, we):
        next_weight = max(next_weight * 0.55, 5.0)  # keep some floor
    
    # 6) check if we should suggest weight increase (informational only)
    suggest_weight = should_suggest_weight_increase(db, we, last_sets)
    
    # 7) build plan rows with fatigue model
    # First set = target_reps (strongest/freshest)
    # Subsequent sets = realistic decline based on fatigue
    rows: list[dict] = []
    for i in range(1, int(target_sets) + 1):
        # Apply fatigue: each set after the first drops by FATIGUE_REP_DROP_PER_SET
        sets_of_fatigue = i - 1  # 0 for first set, 1 for second, etc.
        fatigued_reps = target_reps - (sets_of_fatigue * FATIGUE_REP_DROP_PER_SET)
        # Never go below the floor
        fatigued_reps = max(fatigued_reps, MIN_REPS_FLOOR)

        row = {
            "set_number": i,
            "weight": round(float(next_weight), 1),
            "reps": int(fatigued_reps),
            "done": False,
        }
        # Add UI hint flag to first row if weight increase suggested
        # This flag is for informational display only and not persisted
        if i == 1 and suggest_weight:
            row["_suggest_weight_increase"] = True
        rows.append(row)

    return rows
