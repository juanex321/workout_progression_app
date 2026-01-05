# progression.py

from typing import Dict, Any, Tuple, List
from db import Set, Session, WorkoutExercise

# ----------------- EXERCISE META (type, muscle, rep ranges) -----------------

EXERCISE_META: Dict[str, Dict[str, Any]] = {
    # Legs
    "Leg Extension": {
        "type": "isolation",
        "muscle": "quads",
        "rep_range": (10, 15),
    },
    "Leg Curl": {
        "type": "isolation",
        "muscle": "hamstrings",
        "rep_range": (10, 15),
    },
    "Hip Thrust + Glute Lunges": {
        "type": "compound_like",
        "muscle": "glutes",
        "rep_range": (8, 12),
    },

    # Push
    "Incline DB Bench Press": {
        "type": "compound_like",
        "muscle": "chest",
        "rep_range": (8, 12),
    },
    "Single-arm Chest Fly": {
        "type": "isolation",
        "muscle": "chest",
        "rep_range": (10, 15),
    },
    "Cable Tricep Pushdown": {
        "type": "isolation",
        "muscle": "triceps",
        "rep_range": (10, 15),
    },

    # Pull
    "Lat Pulldown": {
        "type": "compound_like",
        "muscle": "lats",
        "rep_range": (8, 12),
    },
    "Cable Row": {
        "type": "compound_like",
        "muscle": "mid_back",
        "rep_range": (8, 12),
    },
    "Cable Curl": {
        "type": "isolation",
        "muscle": "biceps",
        "rep_range": (10, 15),
    },

    # Delts
    "Dumbbell Lateral Raise": {
        "type": "isolation",
        "muscle": "delts",
        "rep_range": (12, 20),  # delts usually like higher reps
    },
}


# ---------- helpers used by progression ----------

def get_last_session_sets(db, workout_exercise_id: int, max_sessions_back: int = 3):
    """
    Return (last_session_id, [Set, Set, ...]) for the most recent session
    where this workout_exercise_id had logged sets. If none, return (None, None).
    """
    q = (
        db.query(Set)
        .join(Session, Set.session_id == Session.id)
        .filter(Set.workout_exercise_id == workout_exercise_id)
        .order_by(Session.date.desc(), Set.set_number.asc())
    )
    sets: List[Set] = q.all()
    if not sets:
        return None, None

    sessions: Dict[int, List[Set]] = {}
    for s in sets:
        sessions.setdefault(s.session_id, []).append(s)

    # take most recent session
    last_sid = list(sessions.keys())[0]
    return last_sid, sessions[last_sid]


# ---------- main progression function ----------

def recommend_weights_and_reps(db, we: WorkoutExercise) -> list[dict]:
    """
    Return a list of dicts: [{set_number, weight, reps, done}, ...].

    Progression philosophy implemented here:

      - Each exercise has a preferred rep range based on its type
        (isolation vs compound-like).
      - We progress reps first, then weight.
      - Simple performance-based deload:
          if reps are significantly below the bottom of the range,
          drop load to ~55% as a technique-focused reset.
      - The number of sets comes from we.target_sets if available;
        we do NOT change volume here yet.
    """

    # --- look up metadata ---
    ex_name = we.exercise.name if hasattr(we, "exercise") else ""
    meta = EXERCISE_META.get(ex_name, None)

    if meta is not None:
        rep_low, rep_high = meta["rep_range"]
        is_isolation = (meta["type"] == "isolation")
    else:
        # fallback defaults if this exercise isn't defined in EXERCISE_META
        rep_low, rep_high = 8, 12
        is_isolation = True

    # slightly different starting weights
    base_weight = 50.0 if is_isolation else 70.0

    # ---- pull most recent performance ----
    last_session_id, last_sets = get_last_session_sets(db, we.id)
    result: list[dict] = []

    if not last_sets:
        # no history: start at bottom of rep range with a base weight
        target_reps = rep_low
        weight = base_weight
    else:
        last_weight = float(last_sets[0].weight)
        reps_list = [int(s.reps) for s in last_sets if s.reps is not None]

        if reps_list:
            avg_reps = sum(reps_list) / len(reps_list)
            min_reps = min(reps_list)
            max_reps = max(reps_list)
        else:
            avg_reps = rep_low
            min_reps = rep_low
            max_reps = rep_low

        # ---- simple performance-based deload ----
        # If even your best set is well below the bottom of the rep range,
        # you're likely too beat up at this weight => drop to ~55% and reset reps.
        if max_reps <= rep_low - 2:
            weight = round(last_weight * 0.55, 1)
            target_reps = rep_low

        else:
            # ---- normal progression ----

            # Case 1: all sets at or above top of range
            # => increase weight slightly, reset reps closer to the bottom
            if min_reps >= rep_high:
                weight = round(last_weight * 1.05, 1)  # ~5% bump
                target_reps = max(rep_low, rep_low + 1)

            # Case 2: average within the range
            # => keep weight, push reps up gradually until top of range
            elif avg_reps >= rep_low:
                weight = last_weight
                target_reps = min(int(round(avg_reps)) + 1, rep_high)

            # Case 3: average below bottom, but not awful
            # => keep weight, use bottom of range as target
            else:
                weight = last_weight
                target_reps = rep_low

    # ---- how many sets? let DB decide; fall back if missing ----
    try:
        num_sets = int(we.target_sets)
    except Exception:
        num_sets = 4  # conservative default

    for i in range(1, num_sets + 1):
        result.append(
            {
                "set_number": i,
                "weight": weight,
                "reps": target_reps,
                "done": False,  # user will tick this in the UI as they perform sets
            }
        )

    return result
