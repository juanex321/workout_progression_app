"""
Myo-reps progression system.

The app now treats reps as the workload driver:
  - activation reps are used mostly for weight guidance
  - activation + mini-set reps create the session's total-rep workload
  - mini-set count is stored only as a logging detail, not a progression target

Calibration phase (per exercise, CALIBRATION_SESSIONS productive sessions):
  - The default rep target stays fixed while the user establishes a baseline.
  - A session counts toward calibration only when workload and pump are good enough
    and soreness is not excessive.
  - After CALIBRATION_SESSIONS qualifying sessions, average total reps becomes baseline.

Progression (post-calibration):
  - soreness, pump, and workload create rep-change pressure
  - normal changes are +/- 5 reps
  - strong aligned feedback can move +/- 10 reps
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

REP_STEP = 5
LARGE_REP_STEP = 10
MIN_TARGET_REPS = 25

DEFAULT_TARGET_REPS = 40
MAJOR_MUSCLE_TARGET_REPS = 40
MINOR_MUSCLE_TARGET_REPS = 40
FINISHER_MUSCLE_TARGET_REPS = 40

MAJOR_MUSCLES = {"Chest", "Lats", "Quads", "Hamstrings", "Glutes"}
MINOR_MUSCLES = {"Biceps", "Triceps", "Shoulders"}


def _target_floor(default_total_reps: int | None = None) -> int:
    """Keep a safety floor without forcing low-rep finisher targets up to 25."""
    return min(MIN_TARGET_REPS, default_total_reps or DEFAULT_TARGET_REPS)


def _good_calibration_session(soreness_feedback: int, pump_feedback: int, workload_feedback: int) -> bool:
    return soreness_feedback <= 3 and pump_feedback >= 3 and workload_feedback >= 3


def feedback_rep_adjustment(soreness_feedback: int, pump_feedback: int, workload_feedback: int) -> int:
    """Translate muscle feedback into a next-session total-rep adjustment."""
    score = 0

    if soreness_feedback <= 1:
        score += 2
    elif soreness_feedback == 2:
        score += 1
    elif soreness_feedback >= 4:
        score -= 3

    if pump_feedback <= 2:
        score += 2
    elif pump_feedback >= 4:
        score -= 1

    if workload_feedback <= 2:
        score += 2
    elif workload_feedback == 4:
        score -= 1
    elif workload_feedback >= 5:
        score -= 3

    if pump_feedback >= 5 and (soreness_feedback >= 4 or workload_feedback >= 5):
        score -= 1

    if score >= 4:
        return LARGE_REP_STEP
    if score >= 1:
        return REP_STEP
    if score <= -4:
        return -LARGE_REP_STEP
    if score <= -2:
        return -REP_STEP
    return 0


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
        return max(10, round(total_target * 0.25))
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
    floor = _target_floor(fallback)
    if current_target < floor:
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
    soreness_feedback: int = 3,
    pump_feedback: int = 3,
) -> dict:
    """
    Called after an exercise session completes with feedback.
    Updates calibration state / total-rep target.
    Returns {"action": "calibrating"|"progressed"|"held"|"deloaded", "new_target": int|None}
    """
    cal = _get_or_create_calibration(db, exercise_id)
    target = target_total_reps or cal.current_target or DEFAULT_TARGET_REPS
    floor = _target_floor(target_total_reps)

    if not cal.calibrated:
        if _good_calibration_session(soreness_feedback, pump_feedback, workload_feedback):
            cal.calibration_sessions_done += 1
            cal.calibration_mini_sets_sum += total_reps_completed

            if cal.calibration_sessions_done >= CALIBRATION_SESSIONS:
                baseline = round(cal.calibration_mini_sets_sum / cal.calibration_sessions_done)
                baseline = max(baseline, floor)
                cal.calibrated = 1
                cal.baseline_mini_sets = baseline
                cal.current_target = baseline
                db.commit()
                return {"action": "calibrated", "new_target": baseline}

        db.commit()
        return {"action": "calibrating", "new_target": None}

    if target < floor:
        target = DEFAULT_TARGET_REPS
        cal.current_target = target

    adjustment = feedback_rep_adjustment(soreness_feedback, pump_feedback, workload_feedback)
    cal.consecutive_hard_sessions = 0
    cal.current_target = max(floor, target + adjustment)
    db.commit()
    if adjustment > 0:
        return {"action": "progressed", "new_target": cal.current_target}
    if adjustment < 0:
        return {"action": "reduced", "new_target": cal.current_target}
    return {"action": "held", "new_target": cal.current_target}
