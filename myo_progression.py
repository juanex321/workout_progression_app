"""
Myo-reps progression system.

The app now treats reps as the workload driver:
  - activation reps are used mostly for weight guidance
  - activation + mini-set reps create the session's total-rep workload
  - mini-set count is stored only as a logging detail, not a progression target

Calibration phase (per exercise, CALIBRATION_SESSIONS free sessions):
  - No prescribed target; user accumulates reps until the muscle feels Just Right or
    mini-set reps drop below MIN_REPS_FLOOR.
  - After CALIBRATION_SESSIONS sessions, the average total reps becomes the baseline.

Progression (post-calibration):
  - workload 1-2 (Easy/Light): target += REP_STEP next session
  - workload 3 (Just Right): hold target
  - workload 4 (Hard): hold target, reset strike counter
  - workload 5 (Too Much) OR clearly missed target: strike
      → 2 consecutive strikes → reset to baseline
"""

from typing import Optional
from sqlalchemy.orm import Session as OrmSession
from db import MyoExerciseCalibration

CALIBRATION_SESSIONS = 3
MIN_REPS_FLOOR = 3

WORKLOAD_LIGHT_MAX = 2
WORKLOAD_JUST_RIGHT = 3
WORKLOAD_HARD = 4
WORKLOAD_TOO_MUCH = 5

DELOAD_STRIKE_THRESHOLD = 2
REP_STEP = 5
MIN_TARGET_REPS = 25

DEFAULT_TARGET_REPS = 45
MAJOR_MUSCLE_TARGET_REPS = 45
MINOR_MUSCLE_TARGET_REPS = 55
FINISHER_MUSCLE_TARGET_REPS = 60

MAJOR_MUSCLES = {"Chest", "Lats", "Quads", "Hamstrings", "Glutes"}
MINOR_MUSCLES = {"Biceps", "Triceps", "Shoulders"}


def starting_total_rep_target(muscle_group: str | None, has_finisher: bool = False) -> int:
    if has_finisher:
        return FINISHER_MUSCLE_TARGET_REPS
    if muscle_group in MINOR_MUSCLES:
        return MINOR_MUSCLE_TARGET_REPS
    if muscle_group in MAJOR_MUSCLES:
        return MAJOR_MUSCLE_TARGET_REPS
    return DEFAULT_TARGET_REPS


def allocate_muscle_reps(total_target: int, role: str) -> int:
    """Split a muscle-level rep target between main and finisher exercises."""
    if role == "finisher":
        return max(15, round(total_target * 0.33))
    if role == "main_with_finisher":
        return max(25, total_target - allocate_muscle_reps(total_target, "finisher"))
    return total_target


def _get_or_create_calibration(db: OrmSession, exercise_id: int) -> MyoExerciseCalibration:
    cal = db.query(MyoExerciseCalibration).filter_by(exercise_id=exercise_id).first()
    if not cal:
        cal = MyoExerciseCalibration(exercise_id=exercise_id)
        db.add(cal)
        db.commit()
    return cal


def get_recommendation(
    db: OrmSession,
    exercise_id: int,
    *,
    default_total_reps: int | None = None,
) -> dict:
    """
    Returns the current rep prescription for an exercise.
    {
      "calibrated": bool,
      "target_total_reps": int,
      "target_mini_sets": int | None,
      "calibration_session": int | None,
      "baseline": int | None,
    }
    """
    cal = _get_or_create_calibration(db, exercise_id)
    fallback = default_total_reps or DEFAULT_TARGET_REPS

    if not cal.calibrated:
        return {
            "calibrated": False,
            "target_total_reps": fallback,
            "target_mini_sets": None,
            "calibration_session": cal.calibration_sessions_done + 1,
            "baseline": None,
        }

    current_target = cal.current_target or fallback
    # Backward-compatible guard: older calibrated rows may contain mini-set counts
    # like 3-6. Those are not valid total-rep targets, so reset to the new baseline.
    if current_target < MIN_TARGET_REPS:
        current_target = fallback
        cal.current_target = fallback
        cal.baseline_mini_sets = max(cal.baseline_mini_sets or fallback, fallback)
        cal.consecutive_hard_sessions = 0
        db.commit()

    return {
        "calibrated": True,
        "target_total_reps": current_target,
        "target_mini_sets": None,
        "calibration_session": None,
        "baseline": cal.baseline_mini_sets,
    }


def record_session_result(
    db: OrmSession,
    exercise_id: int,
    total_reps_completed: int,
    target_total_reps: Optional[int],
    workload_feedback: int,
) -> dict:
    """
    Called after an exercise session completes with feedback.
    Updates calibration state / total-rep target.
    Returns {"action": "calibrating"|"progressed"|"held"|"deloaded", "new_target": int|None}
    """
    cal = _get_or_create_calibration(db, exercise_id)

    if not cal.calibrated:
        cal.calibration_sessions_done += 1
        cal.calibration_mini_sets_sum += total_reps_completed

        if cal.calibration_sessions_done >= CALIBRATION_SESSIONS:
            baseline = round(cal.calibration_mini_sets_sum / cal.calibration_sessions_done)
            baseline = max(baseline, MIN_TARGET_REPS)
            cal.calibrated = 1
            cal.baseline_mini_sets = baseline
            cal.current_target = baseline
            db.commit()
            return {"action": "calibrated", "new_target": baseline}

        db.commit()
        return {"action": "calibrating", "new_target": None}

    target = target_total_reps or cal.current_target or DEFAULT_TARGET_REPS
    if target < MIN_TARGET_REPS:
        target = DEFAULT_TARGET_REPS
        cal.current_target = target

    missed_badly = total_reps_completed < max(MIN_TARGET_REPS, target - REP_STEP)
    is_overload = (workload_feedback >= WORKLOAD_TOO_MUCH) or (missed_badly and workload_feedback >= WORKLOAD_HARD)

    if is_overload:
        cal.consecutive_hard_sessions += 1
        if cal.consecutive_hard_sessions >= DELOAD_STRIKE_THRESHOLD:
            cal.current_target = cal.baseline_mini_sets or max(MIN_TARGET_REPS, target - REP_STEP)
            cal.consecutive_hard_sessions = 0
            db.commit()
            return {"action": "deloaded", "new_target": cal.current_target}
        db.commit()
        return {"action": "held", "new_target": cal.current_target}

    if workload_feedback >= WORKLOAD_JUST_RIGHT:
        cal.consecutive_hard_sessions = 0
        db.commit()
        return {"action": "held", "new_target": cal.current_target}

    cal.consecutive_hard_sessions = 0
    cal.current_target = max(MIN_TARGET_REPS, (cal.current_target or target) + REP_STEP)
    db.commit()
    return {"action": "progressed", "new_target": cal.current_target}
