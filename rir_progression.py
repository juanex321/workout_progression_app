# rir_progression.py
"""
Session-count-based RIR (Reps in Reserve) progression system with mesocycle tracking.

This module implements a linear RIR progression that advances intensity based on
muscle-specific session count (sessions since last deload), with feedback used to
trigger deloads when overtraining is detected.

RIR Progression Schedule (per muscle group):
- Sessions 1-4:  RIR 2 (building intensity post-deload)
- Sessions 5-8:  RIR 1 (high intensity)
- Sessions 9+:   RIR 0 (peak intensity / max effort)

Deload Trigger:
- When at RIR 0 AND feedback shows overtraining → Deload (RIR 4)
- After deload session, cycle restarts at RIR 2

Key features:
- Each muscle group progresses independently based on its training frequency
- 3-4 sessions per RIR level before progressing
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

# Feedback thresholds
SORENESS_LOW = 2.0
SORENESS_MODERATE = 3.5
SORENESS_HIGH = 4.2

PUMP_LOW = 2.0
PUMP_GOOD = 3.0

WORKLOAD_LOW = 2.2
WORKLOAD_OPTIMAL = 3.0
WORKLOAD_HIGH = 3.8

# Analysis parameters
LOOKBACK_SESSIONS = 3
CONSECUTIVE_HIGH_THRESHOLD = 2
CONSECUTIVE_LOW_THRESHOLD = 3

# Feedback analysis thresholds
HIGH_STRESS_WORKLOAD = 4
HIGH_STRESS_SORENESS = 4
HIGH_STRESS_WORKLOAD_MIN = 3


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
        # High stress: high workload (4+) or (high soreness + high workload)
        is_high_stress = (
            (f.workload or 0) >= HIGH_STRESS_WORKLOAD or
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


def get_rir_for_muscle_group(db: OrmSession, muscle_group: str) -> Tuple[int, str, dict]:
    """
    Main API function to get RIR for a muscle group.

    Uses sessions since last deload as the primary driver for linear RIR progression,
    with feedback as a secondary factor for triggering deloads.

    Progression hierarchy:
    1. Calculate base RIR from sessions in current mesocycle (since last deload)
       - Sessions 1-4: RIR 2 (building)
       - Sessions 5-8: RIR 1 (high intensity)
       - Sessions 9+: RIR 0 (peak intensity - stay here)
    2. Check feedback for deload trigger:
       - When at RIR 0 and showing overtraining → trigger deload (RIR 4)
       - After deload, cycle restarts at RIR 2
    3. Return the final RIR with phase description

    Args:
        db: Database session
        muscle_group: Name of the muscle group

    Returns:
        Tuple of (target_rir, phase_description, analysis)
    """
    if not muscle_group:
        return RIR_HARD, "Moderate Intensity", {}

    # 1. Get base RIR from sessions since last deload (mesocycle position)
    sessions_in_cycle = get_sessions_since_last_deload(db, muscle_group)
    base_rir, base_phase = calculate_rir_from_session_count(sessions_in_cycle)

    # 2. Check feedback for deload trigger (primary use of feedback for RIR)
    feedback_list = get_recent_muscle_feedback(db, muscle_group, limit=LOOKBACK_SESSIONS)
    analysis = analyze_feedback_trend(feedback_list) if feedback_list else {}

    # Start with base RIR and phase
    target_rir = base_rir
    phase = base_phase

    # 3. Apply feedback overrides (deload trigger is the main override)
    if analysis:
        status = analysis.get("status", "maintain")

        # CRITICAL: Trigger deload if showing severe overtraining signs
        # This is especially important when at peak intensity (RIR 0)
        if status == "deload":
            target_rir = RIR_DELOAD
            phase = f"DELOAD (high fatigue detected) - Next session restarts at RIR 2"

        # Minor adjustment: If showing extreme low stress at RIR 2 (early in cycle), can push slightly
        elif status == "push_harder" and base_rir == RIR_HARD and sessions_in_cycle <= 2:
            # Only in first 2 sessions of RIR 2 phase, can skip ahead if severely understimulated
            target_rir = RIR_VERY_HARD
            phase = f"{base_phase} → Advancing early (very low stress detected)"

        # Minor adjustment: If showing fatigue during RIR 1 phase, can back off slightly
        elif status == "slight_deload" and base_rir == RIR_VERY_HARD:
            target_rir = RIR_HARD
            phase = f"{base_phase} → Backing off to RIR 2 (fatigue detected)"

        # For all other cases: keep base_rir (session count drives progression)

    return target_rir, phase, analysis


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
