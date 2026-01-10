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
    Return (session_id, [Set, ...]) for the most recent session of this exercise.
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


# ------- main API -------

def recommend_weights_and_reps(
    db: OrmSession, we: WorkoutExercise
) -> list[dict]:
    """
    Main entry used by app.py.

    1. Adjust target_sets based on recent feedback (volume up/down).
    2. Compute next weight based on last session performance.
    3. If deload is indicated → drop weight to ~55%.
    4. Return rows ready for the Streamlit data editor.
    """
    # 1) volume adjustment
    target_sets = adjust_sets_based_on_feedback(db, we)
    target_reps = we.target_reps or 10

    # 2) base load logic from last session
    _, last_sets = get_last_session_sets(db, we.id)

    if not last_sets:
        next_weight = DEFAULT_BASE_WEIGHT
    else:
        all_hit_target = all((s.reps or 0) >= target_reps for s in last_sets)
        last_weight = last_sets[0].weight or DEFAULT_BASE_WEIGHT
        next_weight = last_weight + 5 if all_hit_target else last_weight

    # 3) deload?
    if should_deload(db, we):
        next_weight = max(next_weight * 0.55, 5.0)  # keep some floor

    # 4) build plan rows (checkboxes start unchecked)
    rows: list[dict] = []
    for i in range(1, int(target_sets) + 1):
        rows.append(
            {
                "set_number": i,
                "weight": round(float(next_weight), 1),
                "reps": int(target_reps),
                "done": False,
            }
        )
    return rows
