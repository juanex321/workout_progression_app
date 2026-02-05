# rir_progression.py
"""
Session-count-based RIR (Reps in Reserve) progression system.

This module implements a linear RIR progression that advances intensity based on
session count, with feedback used for emergency adjustments (deload, slight modifications).

RIR Progression Schedule:
- Weeks 1-2 (sessions 1-6):   RIR 3-4 (building volume, moderate intensity)
- Weeks 3-4 (sessions 7-12):  RIR 2-3 (increasing intensity)
- Weeks 5-6 (sessions 13-18): RIR 1-2 (peak intensity)
- Week 7+ (sessions 19+):     RIR 4+ (deload)
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


def calculate_rir_from_session_count(session_count: int) -> Tuple[int, str]:
    """
    Calculate RIR based on session count (linear progression).

    This is the primary driver for RIR progression, ensuring intensity increases
    on a predictable schedule regardless of feedback (unless emergency override).

    Progression schedule (assuming 3 sessions per week):
    - Sessions 1-6 (Weeks 1-2):   RIR 3-4 → Start with RIR 4, move to RIR 3
    - Sessions 7-12 (Weeks 3-4):  RIR 2-3 → Alternate or transition from 3 to 2
    - Sessions 13-18 (Weeks 5-6): RIR 1-2 → Peak intensity, alternate 2 and 1
    - Sessions 19+ (Week 7+):     RIR 4+  → Deload

    Args:
        session_count: Number of completed sessions for the muscle group

    Returns:
        Tuple of (target_rir, phase_description)
    """
    if session_count <= 3:
        # First 3 sessions: RIR 4 (building baseline, conservative start)
        return RIR_DELOAD, "Week 1 - Building Volume (RIR 4)"
    elif session_count <= 6:
        # Sessions 4-6: RIR 3 (moderate intensity)
        return RIR_MODERATE, "Week 2 - Moderate Intensity (RIR 3)"
    elif session_count <= 9:
        # Sessions 7-9: RIR 3 (continue moderate, building adaptation)
        return RIR_MODERATE, "Week 3 - Progressive Volume (RIR 3)"
    elif session_count <= 12:
        # Sessions 10-12: RIR 2 (increase intensity)
        return RIR_HARD, "Week 4 - Increasing Intensity (RIR 2)"
    elif session_count <= 15:
        # Sessions 13-15: RIR 2 (maintain high intensity)
        return RIR_HARD, "Week 5 - High Intensity (RIR 2)"
    elif session_count <= 18:
        # Sessions 16-18: RIR 1-2 (peak intensity)
        # Alternate between RIR 1 and 2 for peak work
        rir = RIR_VERY_HARD if session_count % 2 == 0 else RIR_HARD
        return rir, f"Week 6 - Peak Intensity (RIR {rir})"
    else:
        # Sessions 19+: Deload (RIR 4+)
        return RIR_DELOAD, "Week 7+ - Deload Phase (RIR 4)"


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

    Uses session count as the primary driver for linear RIR progression,
    with feedback as a secondary factor for emergency adjustments.

    Progression hierarchy:
    1. Calculate base RIR from session count (linear progression)
    2. Check feedback for emergency overrides:
       - Deload if showing signs of overtraining
       - Slight adjustments if extremely under/over-worked
    3. Return the final RIR with phase description

    Args:
        db: Database session
        muscle_group: Name of the muscle group

    Returns:
        Tuple of (target_rir, phase_description, analysis)
    """
    if not muscle_group:
        return RIR_HARD, "Moderate Intensity", {}

    # 1. Get base RIR from session count (primary driver)
    session_count = count_completed_sessions_for_muscle_group(db, muscle_group)
    base_rir, base_phase = calculate_rir_from_session_count(session_count)

    # 2. Check feedback for emergency overrides
    feedback_list = get_recent_muscle_feedback(db, muscle_group, limit=LOOKBACK_SESSIONS)
    analysis = analyze_feedback_trend(feedback_list) if feedback_list else {}

    # Start with base RIR and phase
    target_rir = base_rir
    phase = base_phase

    # 3. Apply feedback overrides (emergency adjustments only)
    if analysis:
        status = analysis.get("status", "maintain")

        # CRITICAL: Force deload if showing severe overtraining signs
        if status == "deload":
            target_rir = RIR_DELOAD
            phase = f"{base_phase} → DELOAD OVERRIDE (high fatigue detected)"

        # Slight adjustments for extreme feedback (but don't override linear progression drastically)
        elif status == "push_harder" and base_rir >= RIR_MODERATE:
            # Only allow push harder if we're still in moderate/deload phase
            # Don't push harder if already at high intensity (RIR 1-2)
            target_rir = max(base_rir - 1, RIR_HARD)
            phase = f"{base_phase} → Pushing slightly harder (low stress detected)"

        elif status == "slight_deload" and base_rir <= RIR_HARD:
            # If at high intensity (RIR 1-2) and showing fatigue, back off slightly
            target_rir = min(base_rir + 1, RIR_MODERATE)
            phase = f"{base_phase} → Backing off slightly (fatigue detected)"

        # For "maintain", "slight_push": keep base_rir (session count drives progression)

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
