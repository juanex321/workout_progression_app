# rir_progression.py
"""
Session-count-based RIR (Reps in Reserve) progression system with mesocycle tracking.

This module implements a linear RIR progression that advances intensity based on
muscle-specific session count (sessions since last deload), with feedback used to
trigger deloads when overtraining is detected.

RIR Progression Schedule (per muscle group):
- RIR 2: minimum 4 sessions + feedback readiness gate (can stay longer)
- RIR 1: minimum 3 sessions (session-count driven)
- RIR 0: minimum 2 sessions before deload can trigger
- Deload (RIR 4): 1 recovery session, then cycle restarts at RIR 2

Deload Trigger:
- When at RIR 0 for >= 2 sessions AND feedback shows overtraining → Deload (RIR 4)
- After deload session, cycle restarts at RIR 2

Key features:
- Each muscle group progresses independently based on its training frequency
- Minimum session floors per phase + feedback gates for advancement
- Feedback drives SET progression (via progression.py)
- Feedback triggers DELOAD when at peak intensity with poor recovery
"""

from typing import List, Tuple, Optional
from sqlalchemy.orm import Session as OrmSession
from db import Feedback, Session, Set, Exercise, WorkoutExercise

# ------- RIR CONSTANTS -------

# RIR levels (Reps in Reserve)
RIR_FAILURE = 0      # Train to failure
RIR_VERY_HARD = 1    # 1 rep in reserve
RIR_HARD = 2         # 2 reps in reserve (moderate-high intensity)
RIR_MODERATE = 3     # 3 reps in reserve (moderate intensity)
RIR_DELOAD = 4       # 4 reps in reserve (deload/recovery)

# Soreness scale semantics (1–4):
#   1 = never got sore       → understimulated, increase workload
#   2 = healed a while ago   → mild stimulus, can increase
#   3 = healed right on time → sweet spot; can push for overreach
#   4 = still sore           → overreach signal, reduce workload if unintentional
SORENESS_LOW = 2.0       # <= 2 → understimulated / mild recovery
SORENESS_MODERATE = 3.0  # >= 3 → at recovery limit (sweet spot or above)
SORENESS_HIGH = 3.5      # > 3.5 → consistently at/beyond recovery limit → deload territory

PUMP_LOW = 2.0
PUMP_GOOD = 3.0

WORKLOAD_LOW = 2.2
WORKLOAD_OPTIMAL = 3.0
WORKLOAD_HIGH = 3.8

# Analysis parameters
LOOKBACK_SESSIONS = 3
CONSECUTIVE_HIGH_THRESHOLD = 2
CONSECUTIVE_LOW_THRESHOLD = 3

# Sessions with pump >= 2 AND workload >= 3 required before advancing from RIR 2 → RIR 1
CONSECUTIVE_SESSIONS_TO_ADVANCE = 2

# Minimum sessions at each RIR level before advancing to the next phase
# (feedback gates still apply — these are floors, not the sole trigger)
MIN_SESSIONS_AT_RIR2 = 4   # Must complete at least 4 sessions at RIR 2
MIN_SESSIONS_AT_RIR1 = 3   # Must complete at least 3 sessions at RIR 1
MIN_SESSIONS_AT_RIR0 = 2   # Must complete at least 2 sessions at RIR 0 before deload fires

# Legacy alias kept for clarity in the RIR 1 phase block
RIR1_SESSION_TARGET = MIN_SESSIONS_AT_RIR1

# Readiness thresholds for leaving RIR 2 calibration phase
ADVANCE_PUMP_MIN = 2.0    # Minimum pump to count as "good enough stimulus"
ADVANCE_WORKLOAD_MIN = 3.0  # Minimum workload to count as "sufficient training stress"

# Feedback analysis thresholds
HIGH_STRESS_WORKLOAD = 4
HIGH_STRESS_SORENESS = 4
HIGH_STRESS_WORKLOAD_MIN = 3
HIGH_STRESS_SORENESS_MIN = 3  # Soreness 2 ("healed a while ago") is not a stress signal; need soreness 3+ ("healed right on time") combined with high workload to flag as high-stress


# ------- HELPER FUNCTIONS -------

def get_recent_muscle_feedback(
    db: OrmSession, muscle_group: str, limit: int = 3
) -> List[Feedback]:
    """
    Get recent feedback for a specific muscle group.

    Args:
        db: Database session
        muscle_group: Name of the muscle group
        limit: Number of recent feedback entries to retrieve

    Returns:
        List of Feedback objects, ordered by most recent first
    """
    if not muscle_group:
        return []

    return (
        db.query(Feedback)
        .filter(Feedback.muscle_group == muscle_group)
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .all()
    )


def count_completed_sessions_for_muscle_group(db: OrmSession, muscle_group: str) -> int:
    """
    Count the number of completed sessions for a specific muscle group.

    This is used to determine the linear RIR progression phase.

    Args:
        db: Database session
        muscle_group: Name of the muscle group

    Returns:
        Number of completed sessions for this muscle group
    """
    if not muscle_group:
        return 0

    # Count distinct completed sessions that have exercises from this muscle group
    count = (
        db.query(Session.id)
        .join(Set, Session.id == Set.session_id)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(Exercise.muscle_group == muscle_group)
        .filter(Session.completed == 1)
        .distinct()
        .count()
    )

    return count


def get_sessions_since_last_deload(db: OrmSession, muscle_group: str) -> int:
    """
    Count sessions since the last deload (RIR >= 4) for this muscle group.

    This tracks mesocycle position without requiring schema changes.
    If no deload found in recent history, returns total session count.

    The mesocycle structure:
    - Deload session (RIR 4): Recovery
    - Sessions 1-4: RIR 2 (building intensity)
    - Sessions 5-8: RIR 1 (high intensity)
    - Sessions 9+: RIR 0 (peak intensity until feedback triggers next deload)

    Args:
        db: Database session
        muscle_group: Name of the muscle group

    Returns:
        Number of sessions since last deload (or total if no deload found)
    """
    if not muscle_group:
        return 0

    # Get recent sets for this muscle group with their RIR values
    # Order by session number descending to find most recent deload
    recent_sets = (
        db.query(Set, Session.session_number)
        .join(Session, Set.session_id == Session.id)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(Exercise.muscle_group == muscle_group)
        .filter(Session.completed == 1)
        .filter(Set.rir.isnot(None))
        .order_by(Session.session_number.desc())
        .limit(100)  # Look back up to 100 sets
        .all()
    )

    if not recent_sets:
        return 0

    # Find the most recent deload session (RIR >= 4)
    deload_session_id = None
    for set_obj, _ in recent_sets:
        if set_obj.rir >= RIR_DELOAD:
            deload_session_id = set_obj.session_id
            break

    if deload_session_id:
        # Count distinct sessions AFTER the deload session
        sessions_after_deload = (
            db.query(Session.id)
            .join(Set, Session.id == Set.session_id)
            .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
            .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
            .filter(Exercise.muscle_group == muscle_group)
            .filter(Session.completed == 1)
            .filter(Session.id > deload_session_id)  # Sessions after deload
            .distinct()
            .count()
        )
        return sessions_after_deload
    else:
        # No deload found in recent history - fresh mesocycle
        # Use total session count (user is starting fresh or no deload yet)
        return count_completed_sessions_for_muscle_group(db, muscle_group)


def calculate_rir_from_session_count(sessions_in_cycle: int) -> Tuple[int, str]:
    """
    Calculate RIR based on sessions since last deload (mesocycle position).

    This is the primary driver for RIR progression, ensuring intensity increases
    on a predictable schedule based on muscle-specific session count.

    Progression: 3-4 sessions per RIR level
    - Sessions 1-4:  RIR 2 (building intensity post-deload)
    - Sessions 5-8:  RIR 1 (high intensity)
    - Sessions 9+:   RIR 0 (max effort / peak intensity)

    Stays at RIR 0 until feedback triggers deload, then cycle restarts.

    Args:
        sessions_in_cycle: Number of sessions since last deload

    Returns:
        Tuple of (target_rir, phase_description)
    """
    if sessions_in_cycle == 0:
        # Just completed a deload, starting fresh
        return RIR_HARD, "Post-Deload - Starting Fresh (RIR 2)"
    elif sessions_in_cycle <= 4:
        # Sessions 1-4: RIR 2 (building intensity)
        return RIR_HARD, f"Building Intensity - Session {sessions_in_cycle}/4 (RIR 2)"
    elif sessions_in_cycle <= 8:
        # Sessions 5-8: RIR 1 (high intensity)
        session_in_phase = sessions_in_cycle - 4
        return RIR_VERY_HARD, f"High Intensity - Session {session_in_phase}/4 (RIR 1)"
    else:
        # Sessions 9+: RIR 0 (peak intensity - stay here until deload)
        sessions_at_peak = sessions_in_cycle - 8
        return RIR_FAILURE, f"Peak Intensity - Session {sessions_at_peak} at RIR 0"


def analyze_feedback_trend(feedback_list: List[Feedback]) -> dict:
    """
    Analyze feedback to determine if muscle is overworked, underworked, or optimal.
    
    Args:
        feedback_list: List of recent Feedback objects
        
    Returns:
        dict with:
            - status: "deload", "maintain", "push_harder", "slight_deload", "slight_push"
            - avg_soreness: Average soreness score
            - avg_pump: Average pump score
            - avg_workload: Average workload score
            - consecutive_high: Count of consecutive high-stress sessions
            - consecutive_low: Count of consecutive low-stress sessions
    """
    if not feedback_list:
        return {
            "status": "maintain",
            "avg_soreness": 0,
            "avg_pump": 0,
            "avg_workload": 0,
            "consecutive_high": 0,
            "consecutive_low": 0,
        }
    
    # Calculate averages
    avg_soreness = sum(f.soreness or 0 for f in feedback_list) / len(feedback_list)
    avg_pump = sum(f.pump or 0 for f in feedback_list) / len(feedback_list)
    avg_workload = sum(f.workload or 0 for f in feedback_list) / len(feedback_list)
    
    # Track consecutive high/low stress sessions
    consecutive_high = 0
    consecutive_low = 0
    
    for f in feedback_list:
        # High stress: (high workload + at least some soreness) or (high soreness + moderate workload)
        # Workload alone is not enough — hard effort with no soreness means full recovery, not overtraining
        is_high_stress = (
            ((f.workload or 0) >= HIGH_STRESS_WORKLOAD and (f.soreness or 0) >= HIGH_STRESS_SORENESS_MIN) or
            ((f.soreness or 0) >= HIGH_STRESS_SORENESS and (f.workload or 0) >= HIGH_STRESS_WORKLOAD_MIN)
        )
        
        # Low stress: low workload and low soreness and low pump
        is_low_stress = (
            (f.workload or 0) <= 2 and
            (f.soreness or 0) <= 2 and
            (f.pump or 0) <= 2
        )
        
        if is_high_stress:
            consecutive_high += 1
            consecutive_low = 0  # Reset low counter
        elif is_low_stress:
            consecutive_low += 1
            consecutive_high = 0  # Reset high counter
        else:
            # Moderate session, reset both
            break
    
    # Determine status based on patterns
    status = "maintain"
    
    # Critical deload signals
    if consecutive_high >= CONSECUTIVE_HIGH_THRESHOLD:
        status = "deload"
    # Overtraining signal: high soreness + low pump
    elif avg_soreness >= SORENESS_HIGH and avg_pump <= PUMP_LOW:
        status = "deload"
    # Push harder signal
    elif consecutive_low >= CONSECUTIVE_LOW_THRESHOLD:
        status = "push_harder"
    # Slight adjustments
    elif avg_workload < WORKLOAD_LOW and avg_soreness < SORENESS_LOW:
        status = "slight_push"
    elif avg_workload > WORKLOAD_HIGH or avg_soreness > SORENESS_HIGH:
        status = "slight_deload"
    
    return {
        "status": status,
        "avg_soreness": avg_soreness,
        "avg_pump": avg_pump,
        "avg_workload": avg_workload,
        "consecutive_high": consecutive_high,
        "consecutive_low": consecutive_low,
    }


def calculate_rir_from_feedback(
    db: OrmSession, muscle_group: str, current_rir: Optional[int] = None
) -> Tuple[int, str, dict]:
    """
    Calculate appropriate RIR based on recent feedback.

    NOTE: This function is now used as a SECONDARY check for emergency overrides.
    The PRIMARY driver for RIR is session count (linear progression).
    Use get_rir_for_muscle_group() instead for the full logic.

    Args:
        db: Database session
        muscle_group: Name of the muscle group
        current_rir: Current RIR level (if known)

    Returns:
        Tuple of (target_rir, phase_description, analysis)
    """
    if not muscle_group:
        return RIR_HARD, "Moderate Intensity", {}
    
    # Get recent feedback
    feedback_list = get_recent_muscle_feedback(db, muscle_group, limit=LOOKBACK_SESSIONS)
    
    # If no feedback, use moderate default
    if not feedback_list:
        return RIR_HARD, "Moderate Intensity - Building Baseline", {}
    
    # Analyze feedback trend
    analysis = analyze_feedback_trend(feedback_list)
    status = analysis["status"]
    
    # Use last RIR if current_rir not provided
    if current_rir is None:
        current_rir = get_last_rir_for_muscle(db, muscle_group)
        if current_rir is None:
            current_rir = RIR_HARD  # Default starting point
    
    # Determine target RIR based on status
    if status == "deload":
        target_rir = RIR_DELOAD
        phase = "Recovery Phase - Deload"
    elif status == "push_harder":
        target_rir = max(RIR_VERY_HARD, current_rir - 1)
        phase = "Progressive Overload - Push Harder"
    elif status == "slight_push":
        target_rir = max(RIR_HARD, current_rir - 1)
        phase = "Slight Increase - More Intensity"
    elif status == "slight_deload":
        target_rir = min(RIR_MODERATE, current_rir + 1)
        phase = "Slight Reduction - Manage Fatigue"
    else:  # maintain
        target_rir = current_rir
        phase = "Maintain Current Intensity"
    
    return target_rir, phase, analysis


def get_last_rir_for_muscle(db: OrmSession, muscle_group: str) -> Optional[int]:
    """
    Get the RIR from the most recent session for a muscle group.
    
    Args:
        db: Database session
        muscle_group: Name of the muscle group
        
    Returns:
        RIR value or None if no previous data
    """
    if not muscle_group:
        return None
    
    # Get most recent set for this muscle group
    recent_set = (
        db.query(Set)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(Exercise.muscle_group == muscle_group)
        .filter(Set.rir.isnot(None))
        .order_by(Set.logged_at.desc())
        .first()
    )
    
    if recent_set and recent_set.rir is not None:
        return int(recent_set.rir)
    
    return None


def _ready_to_advance_from_rir2(feedback_list: List[Feedback]) -> bool:
    """
    Check whether the RIR 2 calibration phase has produced sufficient stimulus
    to justify moving into overreach (RIR 1).

    Advance when CONSECUTIVE_SESSIONS_TO_ADVANCE consecutive sessions (most
    recent first) both report:
      - pump    >= ADVANCE_PUMP_MIN    (user is getting a meaningful pump)
      - workload >= ADVANCE_WORKLOAD_MIN (user is feeling adequate training stress)

    If either condition is unmet for any recent session, stay at RIR 2 and let
    the set-volume feedback loop continue calibrating.
    """
    if not feedback_list or len(feedback_list) < CONSECUTIVE_SESSIONS_TO_ADVANCE:
        return False

    consecutive = 0
    for f in feedback_list:  # ordered most-recent first
        if (f.pump or 0) >= ADVANCE_PUMP_MIN and (f.workload or 0) >= ADVANCE_WORKLOAD_MIN:
            consecutive += 1
        else:
            break  # Must be consecutive from the most recent session

    return consecutive >= CONSECUTIVE_SESSIONS_TO_ADVANCE


def count_consecutive_sessions_at_rir(
    db: OrmSession, muscle_group: str, rir_value: int
) -> int:
    """
    Count how many consecutive completed sessions had sets logged at `rir_value`
    for this muscle group (counting backwards from the most recent session).

    Used to track how long the user has been in the RIR 1 or RIR 0 phase.
    """
    if not muscle_group:
        return 0

    recent_data = (
        db.query(Session.id, Set.rir)
        .join(Set, Session.id == Set.session_id)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(Exercise.muscle_group == muscle_group)
        .filter(Session.completed == 1)
        .filter(Set.rir.isnot(None))
        .order_by(Session.session_number.desc(), Set.set_number.asc())
        .all()
    )

    if not recent_data:
        return 0

    # Deduplicate: first occurrence per session gives us that session's RIR
    seen: dict[int, int] = {}
    for session_id, rir in recent_data:
        if session_id not in seen:
            seen[session_id] = rir

    count = 0
    for session_id, rir in seen.items():  # insertion-ordered, most recent first
        if rir == rir_value:
            count += 1
        else:
            break  # Stop at the first session that doesn't match

    return count


def get_days_since_last_session(db: OrmSession, muscle_group: str) -> Optional[int]:
    """
    Return the number of calendar days between the last two completed sessions
    for this muscle group. Returns None if fewer than 2 sessions exist.

    Used to make the deload trigger more sensitive when the user trains on
    consecutive days (less recovery time between sessions).
    """
    recent_dates = (
        db.query(Session.date)
        .join(Set, Session.id == Set.session_id)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(Exercise.muscle_group == muscle_group)
        .filter(Session.completed == 1)
        .distinct()
        .order_by(Session.session_number.desc())
        .limit(2)
        .all()
    )
    if len(recent_dates) < 2:
        return None
    delta = recent_dates[0].date - recent_dates[1].date
    return abs(delta.days)


def get_rir0_performance_trend(db: OrmSession, muscle_group: str, n_sessions: int = 3) -> str:
    """
    Check whether first-set performance is declining across the last n RIR 0 sessions
    for this muscle group (same weight required for a fair comparison).

    Returns:
        "declining"        — reps dropped by >= 2 between the two most recent RIR 0 sessions
        "stable"           — no clear decline, or weight changed between sessions
        "insufficient_data" — fewer than 2 RIR 0 sessions found
    """
    rows = (
        db.query(Set.reps, Set.weight, Session.session_number)
        .join(Session, Set.session_id == Session.id)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(Exercise.muscle_group == muscle_group)
        .filter(Session.completed == 1)
        .filter(Set.set_number == 1)
        .filter(Set.rir == RIR_FAILURE)
        .filter(Set.reps.isnot(None))
        .filter(Set.weight.isnot(None))
        .order_by(Session.session_number.desc())
        .limit(n_sessions)
        .all()
    )
    if len(rows) < 2:
        return "insufficient_data"
    most_recent, previous = rows[0], rows[1]
    if most_recent.weight != previous.weight:
        return "stable"
    if (int(previous.reps) - int(most_recent.reps)) >= 2:
        return "declining"
    return "stable"


def get_rir_for_muscle_group(db: OrmSession, muscle_group: str) -> Tuple[int, str, dict]:
    """
    Main API function to get RIR for a muscle group.

    Phase progression (per muscle group, independent):

    RIR 2 — Calibration (min 4 sessions + feedback-gated)
        Must complete MIN_SESSIONS_AT_RIR2 sessions AND show sufficient stimulus
        (pump >= ADVANCE_PUMP_MIN AND workload >= ADVANCE_WORKLOAD_MIN for
        CONSECUTIVE_SESSIONS_TO_ADVANCE consecutive sessions) before advancing.
        Can stay longer if feedback isn't ready.

    RIR 1 — Slight Overreach (min 3 sessions)
        One extra set layered on top of the RIR 2 baseline.
        Advances to RIR 0 after MIN_SESSIONS_AT_RIR1 sessions.

    RIR 0 — Full Overreach (min 2 sessions before deload can fire)
        Two extra sets over baseline for peak stimulus.
        Deload only triggers after MIN_SESSIONS_AT_RIR0 sessions at this level.

    Deload (RIR 4) — 1 recovery session, then cycle restarts at RIR 2.
        Weight cut to ~55%. No minimum session requirement.

    Args:
        db: Database session
        muscle_group: Name of the muscle group

    Returns:
        Tuple of (target_rir, phase_description, analysis)
    """
    if not muscle_group:
        return RIR_HARD, "Moderate Intensity", {}

    # Fetch recent feedback (used for deload check and RIR 2 advancement gate)
    feedback_list = get_recent_muscle_feedback(db, muscle_group, limit=LOOKBACK_SESSIONS)
    analysis = analyze_feedback_trend(feedback_list) if feedback_list else {}

    # Deload takes priority — but only fires after MIN_SESSIONS_AT_RIR0 at RIR 0.
    # At RIR 2 / RIR 1 the user hasn't reached peak intensity yet, so deload is
    # premature; the feedback-driven set reduction handles fatigue at those phases.

    # Dense training (≤1 day between sessions) lowers the consecutive-high threshold:
    # a single high-stress session is already enough to warrant deload.
    days_between = get_days_since_last_session(db, muscle_group)
    dense_training = days_between is not None and days_between <= 1
    consecutive_high = analysis.get("consecutive_high", 0)
    feedback_says_deload = (
        analysis.get("status") == "deload"
        or (dense_training and consecutive_high >= 1)
    )

    if feedback_says_deload:
        last_rir_early = get_last_rir_for_muscle(db, muscle_group)
        if last_rir_early is not None and last_rir_early == RIR_FAILURE:
            sessions_at_rir0 = count_consecutive_sessions_at_rir(db, muscle_group, RIR_FAILURE)
            if sessions_at_rir0 >= MIN_SESSIONS_AT_RIR0:
                return RIR_DELOAD, "DELOAD (high fatigue detected) - Next session restarts at RIR 2", analysis

    # Objective deload signal: declining first-set reps at RIR 0 corroborates a
    # slight-deload or deload feedback signal. Requires feedback agreement to avoid
    # false positives from normal session-to-session variation.
    if analysis.get("status") in ("deload", "slight_deload"):
        last_rir_obj = get_last_rir_for_muscle(db, muscle_group)
        if last_rir_obj is not None and last_rir_obj == RIR_FAILURE:
            sessions_at_rir0_obj = count_consecutive_sessions_at_rir(db, muscle_group, RIR_FAILURE)
            if sessions_at_rir0_obj >= MIN_SESSIONS_AT_RIR0:
                if get_rir0_performance_trend(db, muscle_group) == "declining":
                    return RIR_DELOAD, "DELOAD (performance declining at peak intensity) - Next session restarts at RIR 2", analysis

    # Use the last logged RIR to determine which phase we are in
    last_rir = get_last_rir_for_muscle(db, muscle_group)

    # No history or coming off a deload → begin calibration at RIR 2
    if last_rir is None or last_rir >= RIR_DELOAD:
        return RIR_HARD, "Calibration Phase - Establishing baseline volume (RIR 2)", analysis

    # --- RIR 2: Calibration / Exploratory Phase ---
    # Must complete MIN_SESSIONS_AT_RIR2 sessions AND pass feedback readiness check.
    # Feedback alone is not enough — the user needs time to build a baseline.
    if last_rir == RIR_HARD:
        sessions_at_rir2 = count_consecutive_sessions_at_rir(db, muscle_group, RIR_HARD)
        has_min_sessions = sessions_at_rir2 >= MIN_SESSIONS_AT_RIR2
        feedback_ready = _ready_to_advance_from_rir2(feedback_list)

        if has_min_sessions and feedback_ready:
            return (
                RIR_VERY_HARD,
                "Baseline established → Starting Overreach Phase (RIR 1)",
                analysis,
            )
        if not has_min_sessions:
            return (
                RIR_HARD,
                f"Calibration Phase - Session {sessions_at_rir2}/{MIN_SESSIONS_AT_RIR2} (RIR 2)",
                analysis,
            )
        return RIR_HARD, "Calibration Phase - Building to sufficient stimulus (RIR 2)", analysis

    # --- RIR 1: Slight Overreach Phase (session-count driven) ---
    # Stay for RIR1_SESSION_TARGET sessions, then advance to RIR 0.
    if last_rir == RIR_VERY_HARD:
        sessions_at_rir1 = count_consecutive_sessions_at_rir(db, muscle_group, RIR_VERY_HARD)
        if sessions_at_rir1 >= RIR1_SESSION_TARGET:
            return RIR_FAILURE, "Peak Overreach Phase - Max stimulus (RIR 0)", analysis
        return (
            RIR_VERY_HARD,
            f"Overreach Phase - Session {sessions_at_rir1}/{RIR1_SESSION_TARGET} (RIR 1)",
            analysis,
        )

    # --- RIR 0: Full Overreach Phase ---
    # Stay until the deload trigger fires (checked at the top of this function).
    if last_rir == RIR_FAILURE:
        sessions_at_rir0 = count_consecutive_sessions_at_rir(db, muscle_group, RIR_FAILURE)
        return (
            RIR_FAILURE,
            f"Peak Overreach - Session {sessions_at_rir0} at max effort (RIR 0)",
            analysis,
        )

    # Fallback for unexpected RIR values (e.g. legacy RIR 3 data)
    return RIR_HARD, "Calibration Phase (RIR 2)", analysis


def get_rir_badge_style(rir: int) -> Tuple[str, str]:
    """
    Get CSS class and emoji for RIR level.
    
    Args:
        rir: RIR value (0-4)
        
    Returns:
        Tuple of (css_class, emoji)
    """
    if rir >= 4:
        return "badge-deload", "🔵"
    elif rir == 3:
        return "badge-moderate", "🟢"
    elif rir == 2:
        return "badge-hard", "🟡"
    elif rir == 1:
        return "badge-very-hard", "🟠"
    else:  # rir == 0
        return "badge-failure", "🔴"


def get_rir_description(rir: int) -> str:
    """
    Get human-readable description of RIR level.
    
    Args:
        rir: RIR value (0-4)
        
    Returns:
        Description string
    """
    descriptions = {
        0: "Train to failure - Max effort",
        1: "1 rep in reserve - Very hard",
        2: "2 reps in reserve - Moderate-hard intensity",
        3: "3 reps in reserve - Moderate intensity",
        4: "4 reps in reserve - Deload/recovery",
    }
    return descriptions.get(rir, "Unknown RIR level")


def get_feedback_summary(db: OrmSession, muscle_group: str) -> str:
    """
    Get text summary of recent feedback for UI display.
    
    Args:
        db: Database session
        muscle_group: Name of the muscle group
        
    Returns:
        Summary string
    """
    if not muscle_group:
        return "No feedback data"
    
    feedback_list = get_recent_muscle_feedback(db, muscle_group, limit=3)
    
    if not feedback_list:
        return "No recent feedback"
    
    analysis = analyze_feedback_trend(feedback_list)
    
    # Build summary
    parts = []
    
    if analysis["avg_soreness"] >= SORENESS_HIGH:
        parts.append("High soreness")
    elif analysis["avg_soreness"] <= SORENESS_LOW:
        parts.append("Low soreness")
    
    if analysis["avg_pump"] >= PUMP_GOOD:
        parts.append("Good pump")
    elif analysis["avg_pump"] <= PUMP_LOW:
        parts.append("Low pump")
    
    if analysis["avg_workload"] >= WORKLOAD_HIGH:
        parts.append("High workload")
    elif analysis["avg_workload"] <= WORKLOAD_LOW:
        parts.append("Low workload")
    
    if not parts:
        parts.append("Moderate levels")
    
    return ", ".join(parts)
