"""
Myo-reps progression system.

Calibration phase (per exercise, CALIBRATION_SESSIONS free sessions):
  - No prescribed target; user does mini-sets until they drop below MIN_REPS_FLOOR.
  - After CALIBRATION_SESSIONS sessions the median count becomes the baseline.

Progression (post-calibration):
  - workload 1-3 (Easy/Light/Just Right): target += 1 next session
  - workload 4 (Hard): hold, reset hard counter
  - workload 5 (Too Much) OR missed target: consecutive_hard += 1
      → 2 consecutive strikes → deload (reset to baseline)
"""

from typing import Optional
from sqlalchemy.orm import Session as OrmSession
from db import Exercise, MyoExerciseCalibration

CALIBRATION_SESSIONS = 3
MIN_REPS_FLOOR = 3

WORKLOAD_EASY_MAX = 3    # 1-3 → progress
WORKLOAD_HARD = 4        # hold
WORKLOAD_TOO_MUCH = 5    # deload strike

DELOAD_STRIKE_THRESHOLD = 2


def _get_or_create_calibration(db: OrmSession, exercise_id: int) -> MyoExerciseCalibration:
    cal = db.query(MyoExerciseCalibration).filter_by(exercise_id=exercise_id).first()
    if not cal:
        cal = MyoExerciseCalibration(exercise_id=exercise_id)
        db.add(cal)
        db.flush()
    return cal


def get_recommendation(db: OrmSession, exercise_id: int) -> dict:
    """
    Returns the current prescription for an exercise.
    {
      "calibrated": bool,
      "target_mini_sets": int | None,   # None during calibration
      "calibration_session": int | None, # which calibration session this is (1-indexed)
      "baseline": int | None,
    }
    """
    cal = _get_or_create_calibration(db, exercise_id)

    if not cal.calibrated:
        return {
            "calibrated": False,
            "target_mini_sets": None,
            "calibration_session": cal.calibration_sessions_done + 1,
            "baseline": None,
        }

    return {
        "calibrated": True,
        "target_mini_sets": cal.current_target,
        "calibration_session": None,
        "baseline": cal.baseline_mini_sets,
    }


def record_session_result(
    db: OrmSession,
    exercise_id: int,
    mini_sets_completed: int,
    target_mini_sets: Optional[int],
    workload_feedback: int,
) -> dict:
    """
    Called after an exercise session completes with feedback.
    Updates calibration state / progression target.
    Returns {"action": "calibrating"|"progressed"|"held"|"deloaded", "new_target": int|None}
    """
    cal = _get_or_create_calibration(db, exercise_id)

    if not cal.calibrated:
        cal.calibration_sessions_done += 1
        cal.calibration_mini_sets_sum += mini_sets_completed

        if cal.calibration_sessions_done >= CALIBRATION_SESSIONS:
            baseline = round(cal.calibration_mini_sets_sum / cal.calibration_sessions_done)
            baseline = max(baseline, 1)
            cal.calibrated = 1
            cal.baseline_mini_sets = baseline
            cal.current_target = baseline
            db.flush()
            return {"action": "calibrated", "new_target": baseline}

        db.flush()
        return {"action": "calibrating", "new_target": None}

    hit_target = (target_mini_sets is None) or (mini_sets_completed >= target_mini_sets)
    is_overload = (workload_feedback >= WORKLOAD_TOO_MUCH) or (not hit_target)

    if is_overload:
        cal.consecutive_hard_sessions += 1
        if cal.consecutive_hard_sessions >= DELOAD_STRIKE_THRESHOLD:
            cal.current_target = cal.baseline_mini_sets
            cal.consecutive_hard_sessions = 0
            db.flush()
            return {"action": "deloaded", "new_target": cal.current_target}
        db.flush()
        return {"action": "held", "new_target": cal.current_target}

    if workload_feedback == WORKLOAD_HARD:
        cal.consecutive_hard_sessions = 0
        db.flush()
        return {"action": "held", "new_target": cal.current_target}

    # workload 1-3: progress
    cal.consecutive_hard_sessions = 0
    cal.current_target += 1
    db.flush()
    return {"action": "progressed", "new_target": cal.current_target}
