# progression.py

from typing import List, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from db import Set, Session, Feedback, WorkoutExercise, Exercise

# ------- constants / config -------

DEFAULT_BASE_WEIGHT = 50.0
INITIAL_EXERCISE_WEIGHTS = {
    "Romanian Deadlift": 50.0,
}

MIN_SETS = 1

# Minimum total direct sets per muscle exposure. Completed volume and recovery
# feedback drive every subsequent recommendation without a preferred target or cap.
DEFAULT_VOLUME_MINIMUM = 3
MUSCLE_VOLUME_MINIMUMS = {
    "Chest": 4,
    "Lats": 4,
    "Quads": 4,
    "Biceps": 4,
    "Triceps": 4,
    "Hamstrings": 3,
    "Glutes": 3,
    "Shoulders": 3,
}
MAIN_EXERCISE_SET_SHARE = 0.70

MIN_TARGET_REPS = 8
MAX_TARGET_REPS = 15

# Fatigue model: rep drop-off per set after the first
# This models realistic performance decline across sets
# Set 1 = target_reps, Set 2 = target_reps - 1, Set 3 = target_reps - 2, etc.
FATIGUE_REP_DROP_PER_SET = 1
MIN_REPS_FLOOR = 5  # Never recommend fewer than this many reps

# Secondary movements that receive the smaller share in a 70/30 split.
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

# thresholds for the human-readable feedback summary text only (get_feedback_summary)
SORENESS_LOW = 2.0
PUMP_LOW = 2.0
PUMP_GOOD = 3.0
WORKLOAD_LOW = 2.2


# ------- helpers -------

def _session_cache(db: OrmSession, namespace: str) -> dict:
    info = getattr(db, "info", None)
    if not isinstance(info, dict):
        return {}
    return info.setdefault(namespace, {})


def _completed_sets_by_session(db: OrmSession, workout_exercise_id: int) -> dict[int, list[Set]]:
    cache = _session_cache(db, "progression.completed_sets_by_session")
    if workout_exercise_id not in cache:
        sets = (
            db.query(Set)
            .join(Session, Set.session_id == Session.id)
            .filter(Set.workout_exercise_id == workout_exercise_id)
            .filter(Session.completed == 1)
            .order_by(Session.session_number.desc(), Set.set_number.asc())
            .all()
        )
        sessions: dict[int, list[Set]] = {}
        for s in sets:
            sessions.setdefault(s.session_id, []).append(s)
        cache[workout_exercise_id] = sessions
    return cache[workout_exercise_id]


def get_last_session_sets(
    db: OrmSession, workout_exercise_id: int
) -> Tuple[int | None, List[Set] | None]:
    """
    Return (session_id, [Set, ...]) for the most recent completed session of this exercise.
    """
    sessions = _completed_sets_by_session(db, workout_exercise_id)
    if not sessions:
        return None, None

    last_sid = list(sessions.keys())[0]
    return last_sid, sessions[last_sid]


def get_last_n_session_set_counts(
    db: OrmSession, workout_exercise_id: int, n: int = 2
) -> List[int]:
    """
    Return the actual number of sets performed in the last N completed sessions.

    Returns a list ordered most-recent-first: [S_last, S_prev, ...]
    Empty list if no history.
    """
    sessions = _completed_sets_by_session(db, workout_exercise_id)
    if not sessions:
        return []

    # Return set counts for the last N sessions
    counts = []
    for sid in list(sessions.keys())[:n]:
        counts.append(len(sessions[sid]))

    return counts


def get_muscle_volume_minimum(muscle_group: str | None) -> int:
    """Return the minimum direct sets for one muscle exposure."""
    if not muscle_group:
        return DEFAULT_VOLUME_MINIMUM
    return MUSCLE_VOLUME_MINIMUMS.get(muscle_group, DEFAULT_VOLUME_MINIMUM)


def _muscle_secondary_count(db: OrmSession, we: WorkoutExercise, muscle_group: str | None) -> int:
    """Count designated secondary exercises for this muscle in the workout."""
    if not muscle_group or not getattr(we, "workout_id", None):
        return 0

    rows = (
        db.query(Exercise.name)
        .join(WorkoutExercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(WorkoutExercise.workout_id == we.workout_id)
        .filter(Exercise.muscle_group == muscle_group)
        .all()
    )
    return sum(1 for (name,) in rows if (name or "").strip() in FINISHER_NAMES)


def get_exercise_set_bounds(db: OrmSession, we: WorkoutExercise) -> tuple[int, int | None]:
    """Every exercise has a one-set floor and no upper ceiling."""
    return MIN_SETS, None


def _allocate_muscle_sets_to_exercise(
    db: OrmSession, we: WorkoutExercise, muscle_group: str | None, total_sets: int
) -> int:
    """Allocate a muscle total approximately 70/30 between main and secondary work."""
    secondary_count = _muscle_secondary_count(db, we, muscle_group)
    if secondary_count == 0:
        return max(MIN_SETS, int(total_sets))

    total_sets = max(int(total_sets), secondary_count + 1)
    main_sets = int((total_sets * MAIN_EXERCISE_SET_SHARE) + 0.5)
    main_sets = max(MIN_SETS, min(main_sets, total_sets - secondary_count))
    secondary_sets = total_sets - main_sets

    if is_finisher(we):
        return max(MIN_SETS, int(round(secondary_sets / secondary_count)))
    return main_sets


def get_last_n_muscle_group_set_counts(
    db: OrmSession, muscle_group: str, n: int = 2
) -> List[int]:
    """
    Return total direct sets for a muscle group in the last N completed exposures.

    Counts all exercises for that muscle in the same completed session so main
    lifts and secondary exercises are combined into one muscle-level dose.
    """
    if not muscle_group:
        return []

    cache = _session_cache(db, "progression.muscle_set_counts")
    key = (muscle_group, n)
    if key not in cache:
        rows = (
            db.query(Session.id, func.count(Set.id), Session.session_number)
            .join(Set, Session.id == Set.session_id)
            .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
            .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
            .filter(Exercise.muscle_group == muscle_group)
            .filter(Session.completed == 1)
            .group_by(Session.id, Session.session_number)
            .order_by(Session.session_number.desc())
            .limit(n)
            .all()
        )
        cache[key] = [int(row[1]) for row in rows]
    return cache[key]


def get_recent_muscle_group_feedback(
    db: OrmSession, muscle_group: str, limit: int = 3
) -> List[Feedback]:
    """
    Get recent feedback for a muscle group (not tied to specific exercises).

    This is used for muscle-group-level feedback that applies to all exercises
    in that muscle group.
    """
    cache = _session_cache(db, "progression.recent_muscle_feedback")
    key = (muscle_group, limit)
    if key not in cache:
        cache[key] = (
            db.query(Feedback)
            .join(Session, Feedback.session_id == Session.id)
            .filter(Feedback.muscle_group == muscle_group)
            .filter(Session.completed == 1)
            .filter(Feedback.pump.isnot(None))
            .filter(Feedback.workload.isnot(None))
            .order_by(Feedback.created_at.desc())
            .limit(limit)
            .all()
        )
    return cache[key]


def get_feedback_summary(db: OrmSession, muscle_group: str) -> str:
    """Human-readable summary of recent soreness/pump/workload for UI display."""
    if not muscle_group:
        return "No feedback data"

    fb_list = get_recent_muscle_group_feedback(db, muscle_group, limit=3)
    if not fb_list:
        return "No recent feedback"

    avg_s = sum(f.soreness or 0 for f in fb_list) / len(fb_list)
    avg_p = sum(f.pump or 0 for f in fb_list) / len(fb_list)
    avg_w = sum(f.workload or 0 for f in fb_list) / len(fb_list)

    parts = []
    if avg_s >= SORENESS_HIGH:
        parts.append("High soreness")
    elif avg_s <= SORENESS_LOW:
        parts.append("Low soreness")

    if avg_p >= PUMP_GOOD:
        parts.append("Good pump")
    elif avg_p <= PUMP_LOW:
        parts.append("Low pump")

    if avg_w >= WORKLOAD_HIGH:
        parts.append("High workload")
    elif avg_w <= WORKLOAD_LOW:
        parts.append("Low workload")

    if not parts:
        parts.append("Moderate levels")

    return ", ".join(parts)


def is_finisher(we: WorkoutExercise) -> bool:
    name = (we.exercise.name or "").strip()
    return name in FINISHER_NAMES


def compute_feedback_adjustment(db: OrmSession, muscle_group: str) -> int:
    """
    Compute a set adjustment direction from recent muscle group feedback.

    Returns:
        +1 if under-stimulated (all feedback low)
        -1 if overtrained (soreness or workload high)
         0 if no change needed
    """
    fb_list = get_recent_muscle_group_feedback(db, muscle_group, limit=3)
    if not fb_list:
        return 0

    recent_two = fb_list[:2]
    avg_s = sum(f.soreness or 0 for f in fb_list) / len(fb_list)
    avg_p = sum(f.pump or 0 for f in fb_list) / len(fb_list)
    avg_w = sum(f.workload or 0 for f in fb_list) / len(fb_list)

    # High soreness is a direct recovery warning.
    if any((f.soreness or 0) >= SORENESS_HIGH for f in recent_two):
        return -1

    # Repeated workload 4+ means the current dose is already costly enough.
    if len(recent_two) >= 2 and all((f.workload or 0) >= WORKLOAD_HIGH for f in recent_two):
        return -1

    # "Under-stimulated" → +1
    if len(recent_two) >= 2:
        easy_and_recovered = all(
            (f.soreness or 0) <= 2 and (f.workload or 0) <= 2
            for f in recent_two
        )
        never_sore_and_manageable = all(
            (f.soreness or 0) <= 1 and (f.workload or 0) <= 3
            for f in recent_two
        )
        if easy_and_recovered or never_sore_and_manageable:
            return +1

    # "Beaten up / too much" → -1
    if avg_s >= SORENESS_HIGH or avg_w >= WORKLOAD_HIGH:
        return -1

    return 0


def adjust_sets_based_on_feedback(db: OrmSession, we: WorkoutExercise) -> int:
    """
    Determine target sets using session-to-session bounded progression.

    Rules:
    A) Base sets come from the last session's ACTUAL sets performed (not stored target).
       If no history exists, use the exercise's stored starting prescription.
    B) Sets can only change by ±1 per session (hard limiter).
    C) Feedback alone drives direction (+1/-1/0) from that most recent total.

    """
    muscle_group = we.exercise.muscle_group if we.exercise and we.exercise.muscle_group else None
    total_min = get_muscle_volume_minimum(muscle_group)

    # Rule A: Anchor to last session's actual sets performed
    history = get_last_n_muscle_group_set_counts(db, muscle_group, n=1) if muscle_group else []

    if not history:
        min_sets, _ = get_exercise_set_bounds(db, we)
        s_reco = max(min_sets, int(we.target_sets or MIN_SETS))
        if we.target_sets != s_reco:
            we.target_sets = int(s_reco)
            db.add(we)
        return int(s_reco)

    total_anchor = history[0]

    # Rule C: Compute the user-feedback adjustment direction.
    adj = compute_feedback_adjustment(db, muscle_group) if muscle_group else 0

    # Rule B: Apply the ±1 feedback adjustment with a minimum but no ceiling.
    target_total = max(total_min, total_anchor + adj)
    s_reco = _allocate_muscle_sets_to_exercise(db, we, muscle_group, target_total)

    if s_reco != we.target_sets:
        we.target_sets = int(s_reco)
        db.add(we)

    return int(s_reco)


def calculate_target_reps(we: WorkoutExercise, last_sets: List[Set] | None) -> int:
    """
    Calculate target reps based on last session's performance.

    Every set is trained to failure within a fixed rep range: the target is a
    starting aim, not a hard stop. Progression is +1 rep from last session's
    first set, bounded to [MIN_TARGET_REPS, MAX_TARGET_REPS]. Hitting the top
    of the range signals a weight increase (see should_suggest_weight_increase).

    Args:
        we: WorkoutExercise object
        last_sets: Sets from the last session

    Returns:
        Target reps for next session
    """
    if not last_sets:
        # No history - use stored target or default
        return we.target_reps or 10

    # Get first set from last session (strongest/freshest set)
    first_set = min(last_sets, key=lambda s: s.set_number)
    last_reps = int(first_set.reps or 10)

    target_reps = last_reps + 1
    target_reps = min(target_reps, MAX_TARGET_REPS)
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
    Main entry used by the API recommendation flow.

    Progression hierarchy:
    1. Adjust target_sets: feedback-driven and bounded ±1 per session, with no
       upper set ceiling (see adjust_sets_based_on_feedback).
    2. Adjust target_reps based on last session's first-set performance.
    3. Carry forward last session's weight unchanged (user controls weight increases).
    4. Return rows ready for API serialization and UI rendering. Every set is
       trained to failure - there's no reps-in-reserve target.
    """
    # Get muscle group from exercise if not provided
    if muscle_group is None:
        muscle_group = we.exercise.muscle_group if we.exercise and we.exercise.muscle_group else None

    # 1) volume adjustment (primary progression)
    target_sets = adjust_sets_based_on_feedback(db, we)

    # 2) get last session data
    _, last_sets = get_last_session_sets(db, we.id)

    # 3) rep calculation based on last session's first-set performance
    target_reps = calculate_target_reps(we, last_sets)

    # 4) weight — always carry forward last session's weight, no auto-cut
    if not last_sets:
        exercise_name = we.exercise.name if we.exercise else ""
        next_weight = INITIAL_EXERCISE_WEIGHTS.get(exercise_name, DEFAULT_BASE_WEIGHT)
    else:
        next_weight = last_sets[0].weight or DEFAULT_BASE_WEIGHT

    # 5) check if we should suggest weight increase (informational only)
    suggest_weight = should_suggest_weight_increase(db, we, last_sets)

    # 6) build plan rows with fatigue model
    rows: list[dict] = []
    for i in range(1, int(target_sets) + 1):
        sets_of_fatigue = i - 1
        fatigued_reps = target_reps - (sets_of_fatigue * FATIGUE_REP_DROP_PER_SET)
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
