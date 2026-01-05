# progression.py
from typing import Dict, List, Tuple, Optional

from sqlalchemy.orm import Session as DBSession

from db import Set, Session, WorkoutExercise

# ----------------- EXERCISE META DATA -----------------

EXERCISE_META: Dict[str, Dict] = {
    # Legs
    "Leg Extension": {
        "type": "isolation",
        "muscle": "quads",
        "rep_range": (10, 15),
        "finisher": False,
    },
    "Leg Curl": {
        "type": "isolation",
        "muscle": "hamstrings",
        "rep_range": (10, 15),
        "finisher": False,
    },
    "Hip Thrust + Glute Lunges": {
        "type": "compound_like",
        "muscle": "glutes",
        "rep_range": (8, 12),
        "finisher": False,
    },
    # NEW quad finisher
    "Sissy Squat": {
        "type": "isolation",
        "muscle": "quads",
        "rep_range": (12, 20),
        "finisher": True,
    },

    # Push
    "Incline DB Bench Press": {
        "type": "compound_like",
        "muscle": "chest",
        "rep_range": (8, 12),
        "finisher": False,
    },
    "Single-arm Chest Fly": {
        "type": "isolation",
        "muscle": "chest",
        "rep_range": (10, 15),
        "finisher": True,   # behaves like a finisher
    },
    "Cable Tricep Pushdown": {
        "type": "isolation",
        "muscle": "triceps",
        "rep_range": (10, 15),
        "finisher": False,
    },
    # NEW triceps finisher
    "Overhead Cable Extension": {
        "type": "isolation",
        "muscle": "triceps",
        "rep_range": (12, 18),
        "finisher": True,
    },

    # Pull
    "Lat Pulldown": {
        "type": "compound_like",
        "muscle": "lats",
        "rep_range": (8, 12),
        "finisher": False,
    },
    "Cable Row": {
        "type": "compound_like",
        "muscle": "mid_back",
        "rep_range": (8, 12),
        "finisher": False,
    },
    # NEW lat finisher
    "Straight-arm Pulldown": {
        "type": "isolation",
        "muscle": "lats",
        "rep_range": (12, 18),
        "finisher": True,
    },

    # Biceps
    "Cable Curl": {
        "type": "isolation",
        "muscle": "biceps",
        "rep_range": (10, 15),
        "finisher": False,
    },
    # NEW biceps finisher
    "Incline DB Curl": {
        "type": "isolation",
        "muscle": "biceps",
        "rep_range": (12, 20),
        "finisher": True,
    },

    # Delts (no finisher needed)
    "Dumbbell Lateral Raise": {
        "type": "isolation",
        "muscle": "delts",
        "rep_range": (12, 20),
        "finisher": False,
    },
}


# ----------------- HELPERS -----------------


def _get_ex_meta(name: str) -> Optional[Dict]:
    """Look up exercise metadata by name (case-sensitive match)."""
    return EXERCISE_META.get(name)


def _get_last_session_sets(
    db: DBSession, workout_exercise_id: int
) -> Tuple[Optional[int], List[Set]]:
    """
    Return (last_session_id, [Set, Set, ...]) for the most recent session
    for this WorkoutExercise, ordered by set_number.
    """
    q = (
        db.query(Set)
        .join(Session, Set.session_id == Session.id)
        .filter(Set.workout_exercise_id == workout_exercise_id)
        .order_by(Session.date.desc(), Set.set_number.asc())
    )
    sets = q.all()
    if not sets:
        return None, []

    sessions: Dict[int, List[Set]] = {}
    for s in sets:
        sessions.setdefault(s.session_id, []).append(s)

    last_sid = list(sessions.keys())[0]
    return last_sid, sessions[last_sid]


# ----------------- PROGRESSION LOGIC -----------------


def recommend_weights_and_reps(
    db: DBSession, we: WorkoutExercise
) -> List[Dict[str, float]]:
    """
    Return a list of dicts for the editor:
    [
        {"set_number": 1, "weight": 50.0, "reps": 10, "done": False},
        ...
    ]

    Uses very conservative progression:
      - isolation/finishers use higher rep ranges
      - finishers get tiny load bumps and no aggressive deload
      - main lifts can get ~5% load increases and real deloads
    """
    meta = _get_ex_meta(we.exercise.name)

    if meta is not None:
        rep_low, rep_high = meta["rep_range"]
        is_finisher = meta.get("finisher", False)
    else:
        # default if an exercise isn't in EXERCISE_META
        rep_low, rep_high = 8, 12
        is_finisher = False

    base_weight = 50.0

    _, last_sets = _get_last_session_sets(db, we.id)
    result: List[Dict[str, float]] = []

    # Cold start: no history yet
    if not last_sets:
        target_sets = int(getattr(we, "target_sets", 4) or 4)
        # if target_reps is not set, fall back to lower bound of range
        target_reps = getattr(we, "target_reps", rep_low) or rep_low
        for s in range(1, target_sets + 1):
            result.append(
                {
                    "set_number": s,
                    "weight": base_weight,
                    "reps": target_reps,
                    "done": False,
                }
            )
        return result

    # We have history
    last_weight = last_sets[0].weight
    reps_list = [s.reps for s in last_sets]
    min_reps = min(reps_list)
    max_reps = max(reps_list)

    weight = last_weight
    target_reps = reps_list[-1]

    # ---------- basic progression ----------

    # If all sets hit or exceed top of range -> bump load
    if min_reps >= rep_high:
        if is_finisher:
            # finishers: small bump, reset to bottom of range
            weight = round(last_weight * 1.025, 1)  # ~2–3%
            target_reps = rep_low
        else:
            # main lifts: ~5% bump
            weight = round(last_weight * 1.05, 1)
            target_reps = rep_low

    # Otherwise, if not yet near the top, try to add reps
    elif max_reps < rep_high:
        target_reps = min(rep_high, max_reps + 1)

    # ---------- simple deload trigger ----------
    # If the reps dropped well below the bottom of the range, treat as deload.
    if max_reps <= rep_low - 2:
        if is_finisher:
            # finishers: keep weight, just aim for low end of range
            weight = last_weight
            target_reps = rep_low
        else:
            # main lifts: real load drop
            weight = round(last_weight * 0.55, 1)
            target_reps = rep_low

    # Number of sets: default to whatever is configured on the WE,
    # or use previous count as a fallback
    target_sets = int(getattr(we, "target_sets", len(last_sets)) or len(last_sets))

    for s in range(1, target_sets + 1):
        result.append(
            {
                "set_number": s,
                "weight": weight,
                "reps": target_reps,
                "done": False,
            }
        )

    return result
