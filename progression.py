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

# Total direct sets per muscle exposure: (minimum, preferred reset target, cap).
# This keeps progression MEV-biased instead of accumulating toward MRV by default.
DEFAULT_VOLUME_WINDOW = (3, 4, 5)
MUSCLE_VOLUME_WINDOWS = {
    "Chest": (4, 5, 6),
    "Lats": (4, 5, 6),
    "Quads": (4, 5, 6),
    "Biceps": (4, 5, 6),
    "Triceps": (4, 5, 6),
    "Hamstrings": (3, 4, 5),
    "Glutes": (3, 4, 5),
    "Shoulders": (3, 3, 4),
}
DEFAULT_SET_CAP = DEFAULT_VOLUME_WINDOW[2]
MAX_SETS_MAIN = max(window[2] for window in MUSCLE_VOLUME_WINDOWS.values())
MUSCLE_SET_CAPS = {muscle: window[2] for muscle, window in MUSCLE_VOLUME_WINDOWS.items()}
# Finisher-style names (always 1 set regardless of progression)
FINISHER_TARGET_SETS = 1    # finishers are always 1 set

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


def get_muscle_volume_window(muscle_group: str | None) -> tuple[int, int, int]:
    """Return (min, preferred, max) total direct sets for one muscle exposure."""
    if not muscle_group:
        return DEFAULT_VOLUME_WINDOW
    return MUSCLE_VOLUME_WINDOWS.get(muscle_group, DEFAULT_VOLUME_WINDOW)


def _muscle_finisher_count(db: OrmSession, we: WorkoutExercise, muscle_group: str | None) -> int:
    """Count fixed 1-set finisher exercises for this muscle in the same workout."""
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


def get_exercise_set_bounds(db: OrmSession, we: WorkoutExercise) -> tuple[int, int]:
    """Return backend min/max set bounds for this exercise's recommendation."""
    if is_finisher(we):
        return FINISHER_TARGET_SETS, FINISHER_TARGET_SETS

    muscle_group = we.exercise.muscle_group if we.exercise and we.exercise.muscle_group else None
    total_min, _, total_max = get_muscle_volume_window(muscle_group)
    finisher_count = _muscle_finisher_count(db, we, muscle_group)

    min_sets = max(MIN_SETS, total_min - finisher_count)
    max_sets = max(min_sets, total_max - finisher_count)
    return int(min_sets), int(max_sets)


def _allocate_muscle_sets_to_exercise(
    db: OrmSession, we: WorkoutExercise, muscle_group: str | None, total_sets: int
) -> int:
    """Allocate a muscle-level set target to this exercise."""
    if is_finisher(we):
        return FINISHER_TARGET_SETS

    finisher_count = _muscle_finisher_count(db, we, muscle_group)
    min_sets, max_sets = get_exercise_set_bounds(db, we)
    exercise_sets = int(total_sets) - finisher_count
    return max(min_sets, min(exercise_sets, max_sets))


def _preferred_exercise_sets(db: OrmSession, we: WorkoutExercise, muscle_group: str | None) -> int:
    _, preferred_total, _ = get_muscle_volume_window(muscle_group)
    return _allocate_muscle_sets_to_exercise(db, we, muscle_group, preferred_total)


def get_last_n_muscle_group_set_counts(
    db: OrmSession, muscle_group: str, n: int = 2
) -> List[int]:
    """
    Return total direct sets for a muscle group in the last N completed exposures.

    Counts all exercises for that muscle in the same completed session so main
    lifts and fixed finishers are capped as one muscle-level dose.
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


def estimate_mev_for_muscle(db: OrmSession, muscle_group: str) -> int:
    """
    Estimate Minimum Effective Volume for a muscle group from recent history.

    Returns the lowest recent productive dose, capped at the preferred MEV target.
    """
    min_total, preferred_total, max_total = get_muscle_volume_window(muscle_group)
    if not muscle_group:
        return preferred_total

    recent_session_ids = [
        r.id for r in (
            db.query(Session.id)
            .join(Set, Session.id == Set.session_id)
            .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
            .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
            .filter(Exercise.muscle_group == muscle_group)
            .filter(Session.completed == 1)
            .distinct()
            .order_by(Session.id.desc())
            .limit(8)
            .all()
        )
    ]

    if not recent_session_ids:
        return preferred_total

    set_rows = (
        db.query(Set.session_id)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(Exercise.muscle_group == muscle_group)
        .filter(Set.session_id.in_(recent_session_ids))
        .all()
    )
    counts_by_session: dict[int, int] = {}
    for row in set_rows:
        counts_by_session[row.session_id] = counts_by_session.get(row.session_id, 0) + 1

    feedback_rows = (
        db.query(Feedback)
        .filter(Feedback.session_id.in_(recent_session_ids))
        .filter(Feedback.muscle_group == muscle_group)
        .filter(Feedback.pump.isnot(None))
        .filter(Feedback.workload.isnot(None))
        .all()
    )
    fb_by_session = {f.session_id: f for f in feedback_rows}

    min_adequate: int | None = None
    for sid, count in counts_by_session.items():
        fb = fb_by_session.get(sid)
        if (
            fb
            and (fb.soreness or 0) <= 3
            and (fb.pump or 0) >= 3
            and (fb.workload or 0) >= 2
        ):
            if min_adequate is None or count < min_adequate:
                min_adequate = count

    if min_adequate is None:
        return preferred_total
    return max(min_total, min(min_adequate, preferred_total, max_total))


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


def first_set_performance_declining(
    db: OrmSession, workout_exercise_id: int, drop_threshold: int = 2
) -> bool:
    """
    Return True when first-set reps drop at least drop_threshold at the same weight.
    """
    rows = (
        db.query(Set.reps, Set.weight, Session.session_number)
        .join(Session, Set.session_id == Session.id)
        .filter(Set.workout_exercise_id == workout_exercise_id)
        .filter(Session.completed == 1)
        .filter(Set.set_number == 1)
        .filter(Set.reps.isnot(None))
        .filter(Set.weight.isnot(None))
        .order_by(Session.session_number.desc())
        .limit(2)
        .all()
    )
    if len(rows) < 2:
        return False

    most_recent, previous = rows[0], rows[1]
    if most_recent.weight != previous.weight:
        return False
    return int(previous.reps) - int(most_recent.reps) >= drop_threshold


def adjust_sets_based_on_feedback(
    db: OrmSession, we: WorkoutExercise, wave_reset: bool = False
) -> int:
    """
    Determine target sets using session-to-session bounded progression.

    Rules:
    A) Base sets come from the last session's ACTUAL sets performed (not stored target).
       If no history, use a conservative default.
    B) Sets can only change by ±1 per session (hard limiter).
    C) Optional smoothing: if 2 sessions of history exist, anchor to the average.
    D) Feedback drives direction (+1/-1/0), but never more than ±1 from anchor.
    E) wave_reset=True: drop back to MEV estimate regardless of recent history.

    Finishers ALWAYS stay at their stored target (typically 1 set).
    """
    # CRITICAL: Finishers are always 1 set - no exceptions
    if is_finisher(we):
        if we.target_sets != FINISHER_TARGET_SETS:
            we.target_sets = FINISHER_TARGET_SETS
            db.add(we)
        return FINISHER_TARGET_SETS

    muscle_group = we.exercise.muscle_group if we.exercise and we.exercise.muscle_group else None
    total_min, _, total_max = get_muscle_volume_window(muscle_group)

    # Rule E: Wave reset — drop to MEV, ignoring recent history
    if wave_reset and muscle_group:
        target_total = estimate_mev_for_muscle(db, muscle_group)
        s_reco = _allocate_muscle_sets_to_exercise(db, we, muscle_group, target_total)
        if we.target_sets != s_reco:
            we.target_sets = int(s_reco)
            db.add(we)
        return int(s_reco)

    # Rule A: Anchor to last session's actual sets performed
    history = get_last_n_muscle_group_set_counts(db, muscle_group, n=2) if muscle_group else []

    if not history:
        s_reco = _preferred_exercise_sets(db, we, muscle_group)
        if we.target_sets != s_reco:
            we.target_sets = int(s_reco)
            db.add(we)
        return int(s_reco)

    total_last = history[0]

    # Rule C: If 2 sessions available, smooth by averaging
    if len(history) >= 2:
        total_anchor = round((total_last + history[1]) / 2)
    else:
        total_anchor = total_last

    # Rule D: Compute feedback-driven adjustment direction
    adj = compute_feedback_adjustment(db, muscle_group) if muscle_group else 0
    if first_set_performance_declining(db, we.id):
        adj = min(adj, -1)

    # Rule B: Apply ±1 hard limiter and clamp to floor/cap
    target_total = max(total_min, min(total_anchor + adj, total_max))
    s_reco = _allocate_muscle_sets_to_exercise(db, we, muscle_group, target_total)

    if s_reco != we.target_sets:
        we.target_sets = int(s_reco)
        db.add(we)

    return int(s_reco)


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
    Main entry used by the API recommendation flow.

    Progression hierarchy:
    1. Adjust target_sets: feedback-driven accumulation up to MUSCLE_SET_CAPS ceiling.
       On wave reset (RIR 4), sets drop back to adaptive MEV estimate instead.
    2. Adjust target_reps based on last session performance + RIR change.
    3. Carry forward last session's weight unchanged (user controls weight increases).
    4. At RIR 0 (peak): apply -1 set modifier for quality over quantity.
    5. Return rows ready for API serialization and UI rendering.
    """
    # Get muscle group from exercise if not provided
    if muscle_group is None:
        muscle_group = we.exercise.muscle_group if we.exercise and we.exercise.muscle_group else None

    # Get current RIR for this muscle group (used for rep calculation and deload)
    from rir_progression import get_rir_for_muscle_group, is_peak_cycle_complete, RIR_DELOAD, RIR_FAILURE
    if muscle_group:
        current_rir, _, _ = get_rir_for_muscle_group(db, muscle_group)
    else:
        current_rir = 2  # Default moderate RIR if no muscle group

    # Check if this is a finisher exercise
    is_finisher_exercise = is_finisher(we)

    # Wave reset: RIR 4 signals the volume reset phase — sets drop to MEV, weight unchanged
    wave_reset = current_rir >= RIR_DELOAD or (
        bool(muscle_group) and is_peak_cycle_complete(db, muscle_group)
    )

    # 1) volume adjustment (primary progression)
    target_sets = adjust_sets_based_on_feedback(db, we, wave_reset=wave_reset)

    # 2) get last session data
    _, last_sets = get_last_session_sets(db, we.id)

    # 3) rep calculation based on last session + RIR progression
    target_reps = calculate_reps_with_rir_progression(we, last_sets, current_rir)

    # 4) weight — always carry forward last session's weight, no auto-cut
    if not last_sets:
        exercise_name = we.exercise.name if we.exercise else ""
        next_weight = INITIAL_EXERCISE_WEIGHTS.get(exercise_name, DEFAULT_BASE_WEIGHT)
    else:
        next_weight = last_sets[0].weight or DEFAULT_BASE_WEIGHT

    # 5) RIR-stage set volume modifier (non-finisher, non-reset exercises only)
    # RIR 2 = baseline (feedback drives accumulation)
    # RIR 1 = hold flat — the intensity jump is already an overreach stimulus
    # RIR 0 = peak intensity: -1 set for quality over quantity
    # Wave reset (RIR 4) = sets already at MEV from step 1; no further modifier
    if not is_finisher_exercise and not wave_reset:
        if current_rir == RIR_FAILURE:   # 0 — peak intensity: -1 set
            min_sets, _ = get_exercise_set_bounds(db, we)
            target_sets = max(min_sets, target_sets - 1)

    # 6) check if we should suggest weight increase (informational only)
    suggest_weight = should_suggest_weight_increase(db, we, last_sets)

    # 7) build plan rows with fatigue model
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
