"""
Acceptance tests for bounded set progression (±1 per session).

Tests verify:
1. If last session was 5 sets, today must be 4, 5, or 6 — never 1 or 10.
2. Slow recovery/high fatigue -> 5 -> 4 (not 5 -> 1).
3. Fast recovery/low fatigue -> 5 -> 6 (not 5 -> 10).
4. First session uses its stored starting prescription.
5. The latest completed session is the direct volume anchor.
6. Secondary exercises receive roughly 30% of muscle-group volume.
"""

import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

# Ensure we can import from the project root
sys.path.insert(0, os.path.dirname(__file__))

from progression import (
    compute_feedback_adjustment,
    adjust_sets_based_on_feedback,
    get_last_n_muscle_group_set_counts,
    MIN_SETS,
    DEFAULT_BASE_WEIGHT,
)
from plan import DEFAULT_TARGET_SETS


# ---- Helpers to build mock objects ----

def make_mock_feedback(soreness, pump, workload, recovery_days=None, session_id=1):
    fb = MagicMock()
    fb.soreness = soreness
    fb.pump = pump
    fb.workload = workload
    fb.recovery_days = recovery_days
    fb.session_id = session_id
    fb.created_at = datetime.now()
    return fb


def make_mock_we(target_sets=4, exercise_name="Bench Press", muscle_group="Chest", is_finisher_name=False):
    we = MagicMock()
    we.id = 1
    we.target_sets = target_sets
    we.target_reps = 10
    we.exercise = MagicMock()
    we.exercise.name = exercise_name
    we.exercise.muscle_group = muscle_group
    return we


# ---- Tests for compute_feedback_adjustment ----
# Today's soreness answer (session 99) describes how the last exposure recovered.

TODAY = 99


def adjustment(today, history):
    mock_db = MagicMock()
    with patch("progression.get_session_soreness_feedback", return_value=today):
        with patch("progression.get_recent_muscle_group_feedback", return_value=history):
            return compute_feedback_adjustment(mock_db, "Chest", TODAY)


def test_still_sore_today_returns_minus_1():
    """Still sore today drops a set today, even after easy history."""
    adj = adjustment(
        make_mock_feedback(4, None, None, recovery_days=2, session_id=TODAY),
        [make_mock_feedback(1, 3, 2, recovery_days=0)],
    )
    assert adj == -1, f"Expected -1 when still sore, got {adj}"
    print("  PASS: Still sore today -> -1")


def test_slow_recovery_today_returns_minus_1():
    """Soreness lasting 3+ days drops a set today."""
    adj = adjustment(
        make_mock_feedback(2, None, None, recovery_days=3, session_id=TODAY),
        [make_mock_feedback(1, 3, 2, recovery_days=0)],
    )
    assert adj == -1, f"Expected -1 for a 3-day recovery, got {adj}"
    print("  PASS: 3-day recovery -> -1")


def test_long_gap_on_time_is_slow():
    """'Healed right on time' after a week means a week of soreness."""
    adj = adjustment(
        make_mock_feedback(3, None, None, recovery_days=7, session_id=TODAY),
        [make_mock_feedback(1, 3, 3, recovery_days=0)],
    )
    assert adj == -1, f"Expected -1 for a 7-day recovery, got {adj}"
    print("  PASS: Healed on time after 7 days -> -1")


def test_two_fast_recoveries_return_plus_1():
    """Fast recovery today and last exposure, manageable workload -> +1."""
    adj = adjustment(
        make_mock_feedback(2, None, None, recovery_days=1, session_id=TODAY),
        [
            make_mock_feedback(1, 4, 3, recovery_days=0),
            make_mock_feedback(2, 3, 3, recovery_days=1),
        ],
    )
    assert adj == +1, f"Expected +1 for two fast recoveries, got {adj}"
    print("  PASS: Two fast recoveries -> +1")


def test_long_gap_healed_early_one_day_returns_plus_1():
    """A long gap no longer hides a 1-day recovery."""
    adj = adjustment(
        make_mock_feedback(2, None, None, recovery_days=1, session_id=TODAY),
        [make_mock_feedback(2, 4, 3, recovery_days=1)],
    )
    assert adj == +1, f"Expected +1, got {adj}"
    print("  PASS: Healed after 1 day, 8 days ago -> +1")


def test_two_day_recovery_holds():
    """A 2-day recovery is the normal dose -> keep sets."""
    adj = adjustment(
        make_mock_feedback(2, None, None, recovery_days=2, session_id=TODAY),
        [make_mock_feedback(1, 3, 3, recovery_days=0)],
    )
    assert adj == 0, f"Expected 0 for a 2-day recovery, got {adj}"
    print("  PASS: 2-day recovery -> 0")


def test_single_fast_recovery_holds():
    """One fast recovery after an unknown legacy answer is not enough to add."""
    adj = adjustment(
        make_mock_feedback(1, None, None, recovery_days=0, session_id=TODAY),
        [make_mock_feedback(2, 4, 3, recovery_days=None)],
    )
    assert adj == 0, f"Expected 0, got {adj}"
    print("  PASS: One fast recovery -> 0")


def test_high_workload_returns_minus_1():
    """Workload 4+ on the last two exposures drops a set."""
    adj = adjustment(
        make_mock_feedback(1, None, None, recovery_days=0, session_id=TODAY),
        [
            make_mock_feedback(1, 3, 5, recovery_days=0),
            make_mock_feedback(1, 3, 4, recovery_days=0),
        ],
    )
    assert adj == -1, f"Expected -1 for high workload, got {adj}"
    print("  PASS: High workload -> -1")


def test_no_soreness_today_cannot_add():
    """Before today's soreness is answered, only cuts can apply."""
    adj = adjustment(
        None,
        [
            make_mock_feedback(1, 3, 2, recovery_days=0),
            make_mock_feedback(1, 3, 2, recovery_days=0),
        ],
    )
    assert adj == 0, f"Expected 0 without today's soreness, got {adj}"
    print("  PASS: No soreness today -> 0")


def test_no_feedback_returns_0():
    """No feedback should return 0."""
    assert adjustment(None, []) == 0
    print("  PASS: No feedback -> 0")


# ---- Acceptance Tests for adjust_sets_based_on_feedback ----

def test_acceptance_5_sets_stays_in_range():
    """ACCEPTANCE: If last session was 5 sets, today must be 4, 5, or 6."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    for adj_val in [-1, 0, +1]:
        with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5]):
            with patch("progression.compute_feedback_adjustment", return_value=adj_val):
                with patch("progression.is_finisher", return_value=False):
                    result = adjust_sets_based_on_feedback(mock_db, we)
                    assert result in (4, 5, 6), \
                        f"Last session=5, adj={adj_val}: got {result}, expected 4/5/6"
    print("  PASS: 5 sets -> only 4, 5, or 6 possible")


def test_acceptance_high_fatigue_drops_by_1_only():
    """ACCEPTANCE: High soreness -> 5 -> 4, NOT 5 -> 1."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5]):
        with patch("progression.compute_feedback_adjustment", return_value=-1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 4, f"Expected 4, got {result}"
    print("  PASS: High fatigue: 5 -> 4 (not 1)")


def test_acceptance_low_fatigue_increases_by_1_only():
    """ACCEPTANCE: Low feedback -> 5 -> 6, NOT 5 -> 10."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5]):
        with patch("progression.compute_feedback_adjustment", return_value=+1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 6, f"Expected 6, got {result}"
    print("  PASS: Low fatigue: 5 -> 6 (not 10)")


def test_acceptance_no_history_uses_default():
    """ACCEPTANCE: No history -> use conservative default."""
    we = make_mock_we(target_sets=4, muscle_group="Glutes")
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[]):
        with patch("progression.is_finisher", return_value=False):
            result = adjust_sets_based_on_feedback(mock_db, we)
            assert result == 4, f"Expected default {DEFAULT_TARGET_SETS}, got {result}"
    print(f"  PASS: No history -> default ({DEFAULT_TARGET_SETS})")


def test_acceptance_latest_session_is_direct_anchor():
    """ACCEPTANCE: The latest actual volume is not averaged with older sessions."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    # Last session: 6 sets, previous: 4 sets -> anchor remains 6.
    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[6, 4]):
        with patch("progression.compute_feedback_adjustment", return_value=0):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 6, f"Expected latest total 6, got {result}"
    print("  PASS: Latest total 6, adj=0 -> 6")


def test_acceptance_latest_session_with_adjustment():
    """ACCEPTANCE: Positive feedback adds one to the latest actual total."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5, 5]):
        with patch("progression.compute_feedback_adjustment", return_value=+1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 6, f"Expected 6, got {result}"
    print("  PASS: Latest total 5, adj=+1 -> 6")


def test_acceptance_positive_feedback_has_no_upper_cap():
    """ACCEPTANCE: Positive feedback can keep progressing above legacy caps."""
    we = make_mock_we(target_sets=9)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[9]):
        with patch("progression.compute_feedback_adjustment", return_value=+1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 10, f"Expected 10, got {result}"
    print("  PASS: 9 sets + positive feedback -> 10 sets")


def test_acceptance_never_below_volume_window():
    """ACCEPTANCE: At low history + negative feedback -> stays at muscle window minimum."""
    we = make_mock_we(target_sets=MIN_SETS, muscle_group="Chest")
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[MIN_SETS]):
        with patch("progression.compute_feedback_adjustment", return_value=-1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 4, f"Expected Chest minimum 4, got {result}"
    print("  PASS: Low history + negative feedback -> stays at Chest minimum (4)")


def test_acceptance_secondary_receives_thirty_percent():
    """ACCEPTANCE: Secondary work receives roughly 30% of feedback-driven volume."""
    we = make_mock_we(target_sets=3, exercise_name="Single-arm Chest Fly")
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[10]):
        with patch("progression.compute_feedback_adjustment", return_value=0):
            with patch("progression._muscle_secondary_count", return_value=1):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 3, f"Expected 3, got {result}"
    print("  PASS: 10 total sets -> 3 secondary sets")


# ---- Run all tests ----

if __name__ == "__main__":
    print("\n=== Feedback Adjustment Tests ===")
    test_still_sore_today_returns_minus_1()
    test_slow_recovery_today_returns_minus_1()
    test_long_gap_on_time_is_slow()
    test_two_fast_recoveries_return_plus_1()
    test_long_gap_healed_early_one_day_returns_plus_1()
    test_two_day_recovery_holds()
    test_single_fast_recovery_holds()
    test_high_workload_returns_minus_1()
    test_no_soreness_today_cannot_add()
    test_no_feedback_returns_0()

    print("\n=== Acceptance Tests: Bounded Set Progression ===")
    test_acceptance_5_sets_stays_in_range()
    test_acceptance_high_fatigue_drops_by_1_only()
    test_acceptance_low_fatigue_increases_by_1_only()
    test_acceptance_no_history_uses_default()
    test_acceptance_latest_session_is_direct_anchor()
    test_acceptance_latest_session_with_adjustment()
    test_acceptance_positive_feedback_has_no_upper_cap()
    test_acceptance_never_below_volume_window()
    test_acceptance_secondary_receives_thirty_percent()

    print("\nOK: All tests passed!")
