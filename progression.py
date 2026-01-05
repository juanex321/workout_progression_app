from typing import List, Dict, Tuple, Optional

from db import Set, Session, WorkoutExercise

# ---------- basic config ----------

DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10
WEIGHT_STEP = 5.0  # lb/kg step when we bump load

# Explicit finisher list (by name, case-insensitive)
FINISHER_NAMES = {
    "single-arm chest fly",
    "sissy squat",
    "straight-arm pulldown",
    "incline db curl",
    "incline dumbbell curl",
    "overhead cable extension",
}


# ---------- helpers for history ----------


def get_last_session_sets(db, workout_exercise_id: int) -> Tuple[Optional[int], Optional[List[Set]]]:
    """
    Return (session_id, list_of_sets) for the most recent session of this
    workout_exercise_id, or (None, None) if there is no history.
    """
    q = (
        db.query(Set)
        .join(Session, Set.session_id == Session.id)
        .filter(Set.workout_exercise_id == workout_exercise_id)
        .order_by(Session.date.desc(), Set.set_number.asc())
    )
    sets = q.all()
    if not sets:
        return None, None

    # group by session_id
    sessions = {}
    for s in sets:
        sessions.setdefault(s.session_id, []).append(s)

    # take most recent session
    last_sid = list(sessions.keys())[0]
    return last_sid, sessions[last_sid]


# ---------- classification ----------


def _is_finisher(ex_name: str) -> bool:
    return ex_name.lower().strip() in FINISHER_NAMES


def _classify_exercise(ex_name: str) -> str:
    """
    Return "compound", "isolation" or "finisher" based on the name.
    This is heuristic but good enough for our current list.
    """
    n = ex_name.lower()

    if _is_finisher(ex_name):
        return "finisher"

    compound_keywords = [
        "squat",
        "deadlift",
        "hip thrust",
        "bench",
        "press",
        "row",
        "pulldown",
        "pull-down",
        "pull down",
        "lunge",
    ]

    if any(k in n for k in compound_keywords):
        return "compound"

    # everything else defaults to isolation
    return "isolation"


def _rep_range_for_ex(we: WorkoutExercise) -> Tuple[int, int]:
    name = we.exercise.name if getattr(we, "exercise", None) else ""
    typ = _classify_exercise(name)

    if typ == "compound":
        return 8, 12
    elif typ == "finisher":
        return 12, 20
    else:  # isolation
        return 10, 15


def _base_sets_for_ex(we: WorkoutExercise, last_sets: Optional[List[Set]]) -> int:
    """
    How many sets should we show as the starting template for this session?
    - For finishers: 1 set
    - Otherwise: max(target_sets, sets actually done last time, DEFAULT_TARGET_SETS)
    """
    name = we.exercise.name if getattr(we, "exercise", None) else ""
    if _is_finisher(name):
        return max(1, len(last_sets) if last_sets else 1)

    target_sets = int(we.target_sets) if we.target_sets is not None else DEFAULT_TARGET_SETS
    last_n = len(last_sets) if last_sets else 0
    return max(target_sets, last_n, DEFAULT_TARGET_SETS)


# ---------- main progression function ----------


def recommend_weights_and_reps(db, we: WorkoutExercise) -> List[Dict]:
    """
    Core progression logic.

    Strategy:
      - classify exercise as compound / isolation / finisher
      - use a rep range:
          compound  : 8–12
          isolation : 10–15
          finisher  : 12–20
      - look at the *most recent* session for this exercise
      - if no history: start at mid-range reps, default weight 50
      - if history:
          * use last weight
          * if min reps across sets >= top of range -> +weight, reset reps to low end
          * elif min reps >= low end         -> add +1 rep (up to top of range)
          * else (struggling below range)    -> keep weight, keep reps
      - number of sets = max(target_sets, last_n_sets, DEFAULT_TARGET_SETS)
      - always return `done = False` (user controls logging via checkboxes)
    """

    rep_low, rep_high = _rep_range_for_ex(we)
    last_session_id, last_sets = get_last_session_sets(db, we.id)
    rows: List[Dict] = []

    # ---- no history: seed defaults ----
    if not last_sets:
        num_sets = _base_sets_for_ex(we, last_sets=None)
        # use target_reps if it falls in range, otherwise mid-range
        if we.target_reps is not None and rep_low <= we.target_reps <= rep_high:
            base_reps = int(we.target_reps)
        else:
            base_reps = (rep_low + rep_high) // 2

        base_weight = 50.0

        for i in range(1, num_sets + 1):
            rows.append(
                {
                    "set_number": i,
                    "weight": base_weight,
                    "reps": base_reps,
                    "done": False,
                }
            )
        return rows

    # ---- we have history ----
    last_weight = float(last_sets[0].weight)  # assume same weight for all sets
    min_reps = min(int(s.reps) for s in last_sets if s.reps is not None)

    num_sets = _base_sets_for_ex(we, last_sets=last_sets)

    next_weight = last_weight
    next_reps = max(min_reps, rep_low)

    if min_reps >= rep_high:
        # crushed the top of the range -> add weight, drop reps to low end
        next_weight = last_weight + WEIGHT_STEP
        next_reps = rep_low
    elif rep_low <= min_reps < rep_high:
        # within range, try to climb reps
        next_reps = min(min_reps + 1, rep_high)
    else:
        # below the range -> probably heavy; keep same prescription for now
        next_reps = max(min_reps, rep_low)

    for i in range(1, num_sets + 1):
        rows.append(
            {
                "set_number": i,
                "weight": next_weight,
                "reps": next_reps,
                "done": False,
            }
        )

    return rows
